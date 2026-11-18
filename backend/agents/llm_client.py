import asyncio
import inspect
import json
import re
from typing import Any, Coroutine, Dict, Optional, Tuple, TypeVar

from openai import AsyncOpenAI

from backend.config.settings import settings

T = TypeVar("T")


def run_sync(coro: Coroutine[Any, Any, T]) -> T:
    """Safely execute a coroutine from synchronous code."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


class GroqAgentFrameworkClient:
    """
    Wrapper around Microsoft Agent Framework + AsyncOpenAI configured for Groq.
    Gracefully falls back to None when GROQ_API_KEY is missing or network/API fails.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.GROQ_API_KEY
        self.base_url = base_url or settings.LLM_BASE_URL
        self.model = model or settings.LLM_MODEL

    def is_configured(self) -> bool:
        return bool(
            self.api_key
            and self.api_key.strip()
            and self.api_key.strip() != "your_groq_api_key_here"
        )

    def _build_chat_client(
        self, openai_client: Optional[AsyncOpenAI] = None
    ) -> Tuple[Any, Optional[AsyncOpenAI]]:
        from agent_framework.openai import OpenAIChatClient

        owned_client: Optional[AsyncOpenAI] = None
        if openai_client is None:
            openai_client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
            owned_client = openai_client

        sig = inspect.signature(OpenAIChatClient.__init__)
        params = sig.parameters
        kwargs: Dict[str, Any] = {}

        if "model_id" in params:
            kwargs["model_id"] = self.model
        elif "model" in params:
            kwargs["model"] = self.model

        if "async_client" in params:
            kwargs["async_client"] = openai_client
        elif "openai_client" in params:
            kwargs["openai_client"] = openai_client
        else:
            if "api_key" in params:
                kwargs["api_key"] = self.api_key
            if "base_url" in params:
                kwargs["base_url"] = self.base_url

        return OpenAIChatClient(**kwargs), owned_client

    def _create_agent_from_client(
        self, chat_client: Any, name: str, instructions: str
    ) -> Any:
        if hasattr(chat_client, "as_agent"):
            return chat_client.as_agent(name=name, instructions=instructions)
        if hasattr(chat_client, "create_agent"):
            return chat_client.create_agent(name=name, instructions=instructions)

        import agent_framework

        agent_cls = getattr(agent_framework, "ChatAgent", None) or getattr(
            agent_framework, "Agent", None
        )
        if agent_cls is None:
            raise RuntimeError(
                "Could not locate ChatAgent/Agent or as_agent/create_agent in agent_framework."
            )

        sig = inspect.signature(agent_cls.__init__)
        kwargs: Dict[str, Any] = {"name": name, "instructions": instructions}
        if "chat_client" in sig.parameters:
            kwargs["chat_client"] = chat_client
        elif "client" in sig.parameters:
            kwargs["client"] = chat_client
        return agent_cls(**kwargs)

    def create_agent(self, name: str, instructions: str) -> Any:
        chat_client, _ = self._build_chat_client()
        return self._create_agent_from_client(chat_client, name, instructions)

    @staticmethod
    def _extract_text(result: Any) -> str:
        if result is None:
            return ""
        if isinstance(result, str):
            return result
        if hasattr(result, "text") and result.text:
            return str(result.text)
        if hasattr(result, "messages") and result.messages:
            last_msg = result.messages[-1]
            if hasattr(last_msg, "text") and last_msg.text:
                return str(last_msg.text)
            if hasattr(last_msg, "content"):
                return str(last_msg.content)
        return str(result)

    async def arun_agent_text(
        self, name: str, instructions: str, user_prompt: str
    ) -> Optional[str]:
        if not self.is_configured():
            return None

        try:
            async with AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            ) as openai_client:
                chat_client, _ = self._build_chat_client(openai_client=openai_client)
                agent = self._create_agent_from_client(
                    chat_client, name=name, instructions=instructions
                )
                result = await agent.run(user_prompt)
                text = self._extract_text(result).strip()
                return text or None
        except Exception:
            return None

    async def arun_agent_json(
        self, name: str, instructions: str, user_prompt: str
    ) -> Optional[Dict[str, Any]]:
        raw = await self.arun_agent_text(
            name=name, instructions=instructions, user_prompt=user_prompt
        )
        if not raw:
            return None

        cleaned = raw.strip()
        fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
        if fenced:
            cleaned = fenced.group(1).strip()
        else:
            obj_match = re.search(r"\{[\s\S]*\}", cleaned)
            if obj_match:
                cleaned = obj_match.group(0)

        try:
            parsed = json.loads(cleaned)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None

    def run_agent_json(
        self, name: str, instructions: str, user_prompt: str
    ) -> Optional[Dict[str, Any]]:
        return run_sync(self.arun_agent_json(name, instructions, user_prompt))


llm_client = GroqAgentFrameworkClient()