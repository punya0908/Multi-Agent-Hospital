import re
from typing import List, Optional

from backend.agents.llm_client import GroqAgentFrameworkClient, llm_client, run_sync
from backend.schemas.workflow_state import (
    DepartmentInformation,
    PatientIntakeRecord,
    RetrievedDocument,
    RoutingDecision,
)
from backend.services.rag_service import RAGService


class InformationAgent:
    SYSTEM_INSTRUCTIONS = (
        "You are a hospital department information assistant. "
        "Using ONLY the retrieved department knowledge base snippets provided, "
        "extract clear pre-visit instructions, documents/items to bring, and the clinic location. "
        "STRICT RULE: Do NOT invent facts outside the provided snippets. "
        "Return ONLY JSON with keys: instructions (list of strings), "
        "documents_to_bring (list of strings), location (string)."
    )

    def __init__(
        self,
        rag_service: Optional[RAGService] = None,
        client: Optional[GroqAgentFrameworkClient] = None,
    ) -> None:
        self.rag_service = rag_service or RAGService()
        self.client = client or llm_client

    @staticmethod
    def _parse_bullets(section_text: str) -> List[str]:
        items: List[str] = []
        for line in section_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("- "):
                items.append(stripped[2:].strip())
        return items

    def _fallback_from_docs(
        self, department_id: str, docs: List[RetrievedDocument]
    ) -> DepartmentInformation:
        instructions: List[str] = []
        documents_to_bring: List[str] = []
        location = "Main Hospital Reception (Check front desk for suite details)"

        for doc in docs:
            snippet = doc.content_snippet
            loc_match = re.search(r"Location:\s*(.+)", snippet)
            if loc_match:
                location = loc_match.group(1).strip()

            lower = snippet.lower()
            bullets = self._parse_bullets(snippet)
            if "what to bring" in lower:
                documents_to_bring.extend(bullets)
            elif "pre-visit instructions" in lower or "registration steps" in lower:
                instructions.extend(bullets)

        if not instructions and docs:
            instructions = [
                line.strip("- ").strip()
                for doc in docs
                for line in doc.content_snippet.splitlines()
                if line.strip() and not line.strip().startswith("#")
            ][:4]

        return DepartmentInformation(
            department_id=department_id,
            instructions=instructions,
            documents_to_bring=documents_to_bring,
            location=location,
            citations=docs,
        )

    async def arun(
        self, routing: RoutingDecision, intake: PatientIntakeRecord
    ) -> DepartmentInformation:
        query = f"{intake.concern} location pre-visit instructions what to bring registration"
        docs = self.rag_service.retrieve_department_docs(
            department_id=routing.department_id,
            query=query,
            top_k=4,
        )

        if not docs:
            return DepartmentInformation(
                department_id=routing.department_id,
                instructions=["Please check in at the main hospital reception 15 minutes early."],
                documents_to_bring=["Valid photo ID"],
                location="Main Reception",
                citations=[],
            )

        snippets_text = "\n\n---\n\n".join(
            f"[Source: {d.source_file} | Dept: {d.department_id}]\n{d.content_snippet}"
            for d in docs
        )
        prompt = (
            f"Department: {routing.department_id} ({routing.department_name})\n"
            f"Patient Concern: {intake.concern}\n\n"
            f"Retrieved Knowledge Base Snippets:\n{snippets_text}\n\n"
            "Return ONLY JSON with keys: instructions, documents_to_bring, location."
        )

        data = await self.client.arun_agent_json(
            name="InformationAgent",
            instructions=self.SYSTEM_INSTRUCTIONS,
            user_prompt=prompt,
        )
        if data:
            instructions = [str(x) for x in data.get("instructions", []) if str(x).strip()]
            docs_to_bring = [
                str(x) for x in data.get("documents_to_bring", []) if str(x).strip()
            ]
            location = str(data.get("location") or "").strip()
            if instructions and location:
                return DepartmentInformation(
                    department_id=routing.department_id,
                    instructions=instructions,
                    documents_to_bring=docs_to_bring,
                    location=location,
                    citations=docs,
                )

        return self._fallback_from_docs(routing.department_id, docs)

    def run(
        self, routing: RoutingDecision, intake: PatientIntakeRecord
    ) -> DepartmentInformation:
        return run_sync(self.arun(routing=routing, intake=intake))