from typing import Optional

from backend.agents.llm_client import GroqAgentFrameworkClient, llm_client, run_sync
from backend.schemas.workflow_state import PatientIntakeRecord, SafetyAssessment
from backend.services.safety_rule_service import SafetyRuleService


class SafetyGateAgent:
    SYSTEM_INSTRUCTIONS = (
        "You are a non-clinical hospital intake safety screening gate. "
        "Review the patient's stated concern ONLY for subtle life-threatening red flags "
        "(such as acute cardiac distress, stroke signs, severe respiratory distress, "
        "anaphylaxis, active severe bleeding, or self-harm risk). "
        "Respect negations carefully (e.g., 'no chest pain' is NOT urgent). "
        "Return ONLY JSON with keys: status ('URGENT', 'UNCERTAIN', or 'CLEAR'), "
        "advisory_message (string), requires_immediate_care (boolean)."
    )

    def __init__(
        self,
        rule_service: Optional[SafetyRuleService] = None,
        client: Optional[GroqAgentFrameworkClient] = None,
        enable_llm_check: bool = True,
    ) -> None:
        self.rule_service = rule_service or SafetyRuleService()
        self.client = client or llm_client
        self.enable_llm_check = enable_llm_check

    @staticmethod
    def _fail_closed_assessment() -> SafetyAssessment:
        return SafetyAssessment(
            status="UNCERTAIN",
            matched_rules=["SAFETY_GATE_ERROR"],
            advisory_message=(
                "Safety check encountered an unexpected error. "
                "Human clinical triage review is required before proceeding."
            ),
            requires_immediate_care=False,
        )

    async def arun(self, intake: PatientIntakeRecord) -> SafetyAssessment:
        try:
            deterministic_result = self.rule_service.evaluate(intake.concern)
            if deterministic_result.status in ("URGENT", "UNCERTAIN"):
                return deterministic_result

            if self.enable_llm_check and self.client.is_configured():
                prompt = (
                    f"Patient concern: {intake.concern}\n"
                    f"Duration: {intake.duration or 'unspecified'}\n"
                    "Respond with JSON only."
                )
                llm_data = await self.client.arun_agent_json(
                    name="SafetyGateAgent",
                    instructions=self.SYSTEM_INSTRUCTIONS,
                    user_prompt=prompt,
                )
                if llm_data and llm_data.get("status") in ("URGENT", "UNCERTAIN"):
                    return SafetyAssessment(
                        status=llm_data["status"],
                        matched_rules=["LLM_SEMANTIC_RED_FLAG"],
                        advisory_message=str(
                            llm_data.get("advisory_message")
                            or "Potential safety concern flagged for prompt clinical review."
                        ),
                        requires_immediate_care=bool(
                            llm_data.get("requires_immediate_care", llm_data["status"] == "URGENT")
                        ),
                    )

            return deterministic_result
        except Exception:
            return self._fail_closed_assessment()

    def run(self, intake: PatientIntakeRecord) -> SafetyAssessment:
        return run_sync(self.arun(intake))