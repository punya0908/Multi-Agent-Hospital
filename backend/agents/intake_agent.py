import json
import re
from typing import Any, Dict, Optional, Union

from backend.agents.llm_client import GroqAgentFrameworkClient, llm_client, run_sync
from backend.schemas.workflow_state import PatientIntakeRecord


class IntakeAgent:
    SYSTEM_INSTRUCTIONS = (
        "You are a hospital patient intake normalization assistant. "
        "Extract and normalize patient intake fields from the user's message into valid JSON ONLY "
        "with keys: name (string), age (integer or null), concern (string), duration (string or null). "
        "STRICT RULE: Never diagnose, never convert symptoms into medical disease names, "
        "and never add clinical assumptions. Preserve the patient's own symptom description neutrally."
    )

    def __init__(self, client: Optional[GroqAgentFrameworkClient] = None) -> None:
        self.client = client or llm_client

    @staticmethod
    def _fallback_extract(
        raw_input: Union[str, Dict[str, Any]],
        patient_id: Optional[str],
        consent_memory: bool,
    ) -> PatientIntakeRecord:
        if isinstance(raw_input, dict):
            return PatientIntakeRecord(
                patient_id=patient_id or raw_input.get("patient_id"),
                name=str(raw_input.get("name") or "Unknown Patient"),
                age=raw_input.get("age"),
                concern=str(raw_input.get("concern") or "").strip(),
                duration=raw_input.get("duration"),
                consent_memory=bool(
                    raw_input.get("consent_memory", consent_memory)
                ),
            )

        text = raw_input.strip()
        name = "Unknown Patient"
        age: Optional[int] = None
        duration: Optional[str] = None

        name_age_match = re.search(
            r"(?:i am|i'm|my name is)\s+([A-Za-z][A-Za-z\s'-]{0,30}?)(?:\s*,\s*(\d{1,3}))?(?:[.,]|$)",
            text,
            re.IGNORECASE,
        )
        if name_age_match:
            name = name_age_match.group(1).strip()
            if name_age_match.group(2):
                age = int(name_age_match.group(2))

        if age is None:
            age_match = re.search(
                r"\b(\d{1,3})\s*(?:years?\s*old|yrs?\s*old|yo)\b", text, re.IGNORECASE
            )
            if age_match:
                age = int(age_match.group(1))

        dur_match = re.search(
            r"\bfor\s+(\d+\s+(?:hour|hours|day|days|week|weeks|month|months|year|years))\b",
            text,
            re.IGNORECASE,
        )
        if dur_match:
            duration = dur_match.group(1).strip()

        concern = re.sub(
            r"^(?:hi|hello|hey)[,!\s]*(?:i am|i'm|my name is)\s+[A-Za-z\s'-]+?(?:,\s*\d{1,3})?[.,!\s]*",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()
        if not concern:
            concern = text

        return PatientIntakeRecord(
            patient_id=patient_id,
            name=name,
            age=age,
            concern=concern,
            duration=duration,
            consent_memory=consent_memory,
        )

    async def arun(
        self,
        raw_input: Union[str, Dict[str, Any]],
        patient_id: Optional[str] = None,
        consent_memory: bool = False,
    ) -> PatientIntakeRecord:
        payload_str = (
            json.dumps(raw_input) if isinstance(raw_input, dict) else str(raw_input)
        )
        prompt = (
            f"Normalize this patient intake input into JSON:\n{payload_str}\n"
            "Return ONLY a JSON object with keys: name, age, concern, duration."
        )

        data = await self.client.arun_agent_json(
            name="IntakeAgent",
            instructions=self.SYSTEM_INSTRUCTIONS,
            user_prompt=prompt,
        )
        if data:
            try:
                raw_dict = raw_input if isinstance(raw_input, dict) else {}
                return PatientIntakeRecord(
                    patient_id=patient_id or raw_dict.get("patient_id"),
                    name=str(data.get("name") or raw_dict.get("name") or "Unknown Patient"),
                    age=data.get("age") if data.get("age") is not None else raw_dict.get("age"),
                    concern=str(data.get("concern") or payload_str).strip(),
                    duration=data.get("duration") or raw_dict.get("duration"),
                    consent_memory=bool(raw_dict.get("consent_memory", consent_memory)),
                )
            except Exception:
                pass

        return self._fallback_extract(raw_input, patient_id, consent_memory)

    def run(
        self,
        raw_input: Union[str, Dict[str, Any]],
        patient_id: Optional[str] = None,
        consent_memory: bool = False,
    ) -> PatientIntakeRecord:
        return run_sync(
            self.arun(
                raw_input=raw_input,
                patient_id=patient_id,
                consent_memory=consent_memory,
            )
        )