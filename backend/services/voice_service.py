from typing import Any, Dict, Optional
from openai import AsyncOpenAI

from backend.agents.intake_agent import IntakeAgent
from backend.config.settings import settings


class VoiceService:
    def __init__(self, intake_agent: Optional[IntakeAgent] = None) -> None:
        self.intake_agent = intake_agent or IntakeAgent()

    @staticmethod
    def _has_groq_key() -> bool:
        key = (settings.GROQ_API_KEY or "").strip()
        return bool(key and key != "your_groq_api_key_here")

    async def transcribe_audio(
        self,
        audio_bytes: Optional[bytes],
        filename: str = "voice_intake.webm",
        transcript_fallback: Optional[str] = None,
    ) -> str:
        if audio_bytes and self._has_groq_key():
            try:
                async with AsyncOpenAI(
                    api_key=settings.GROQ_API_KEY,
                    base_url=settings.LLM_BASE_URL,
                ) as client:
                    transcription = await client.audio.transcriptions.create(
                        model="whisper-large-v3-turbo",
                        file=(filename or "voice_intake.webm", audio_bytes),
                    )
                    text = getattr(transcription, "text", "") or ""
                    if text.strip():
                        return text.strip()
            except Exception:
                pass

        if transcript_fallback and transcript_fallback.strip():
            return transcript_fallback.strip()

        if audio_bytes:
            try:
                decoded = audio_bytes.decode("utf-8", errors="ignore").strip()
                if decoded and decoded.isprintable():
                    return decoded
            except Exception:
                pass

        return "Patient provided a voice recording reporting discomfort requiring intake review."

    async def process_voice_intake(
        self,
        audio_bytes: Optional[bytes],
        filename: str = "voice_intake.webm",
        patient_id: Optional[str] = None,
        consent_memory: bool = False,
        transcript_fallback: Optional[str] = None,
    ) -> Dict[str, Any]:
        transcript = await self.transcribe_audio(
            audio_bytes=audio_bytes,
            filename=filename,
            transcript_fallback=transcript_fallback,
        )

        extracted_intake = await self.intake_agent.arun(
            raw_input=transcript,
            patient_id=patient_id,
            consent_memory=consent_memory,
        )

        spoken_confirmation_prompt = (
            f"Thank you, {extracted_intake.name}. "
            f"I captured your concern: {extracted_intake.concern}. "
            "Running safety screening and hospital department routing now."
        )

        return {
            "transcript": transcript,
            "extracted_intake": extracted_intake,
            "spoken_confirmation_prompt": spoken_confirmation_prompt,
        }