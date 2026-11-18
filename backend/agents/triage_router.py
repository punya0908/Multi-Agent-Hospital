from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from backend.agents.llm_client import GroqAgentFrameworkClient, llm_client, run_sync
from backend.config.settings import settings
from backend.schemas.workflow_state import (
    PatientIntakeRecord,
    PatientMemoryRecord,
    RoutingDecision,
)


class TriageRouterAgent:
    SYSTEM_INSTRUCTIONS = (
        "You are a hospital department routing assistant. "
        "Map the patient's concern to the single best matching hospital department from the provided list. "
        "If historical visit context is provided, treat it ONLY as background context and NEVER override current symptoms. "
        "STRICT GUARDRAILS: "
        "1. NEVER diagnose a condition or name any medical disease in your explanation. "
        "2. Explain routing strictly in terms of the reported symptoms and department scope. "
        "3. Return ONLY JSON with keys: department_id (string), department_name (string), "
        "routing_explanation (string), confidence ('HIGH', 'MEDIUM', or 'LOW')."
    )

    def __init__(
        self,
        departments_path: Optional[Path] = None,
        client: Optional[GroqAgentFrameworkClient] = None,
    ) -> None:
        self.departments_path = departments_path or settings.DEPARTMENTS_PATH
        self.client = client or llm_client
        with open(self.departments_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        self.departments: List[Dict[str, Any]] = data.get("departments", [])
        self.dept_map: Dict[str, Dict[str, Any]] = {
            d["id"]: d for d in self.departments
        }

    def _fallback_route(self, intake: PatientIntakeRecord) -> RoutingDecision:
        concern_lower = intake.concern.lower()
        best_dept: Optional[Dict[str, Any]] = None
        best_hits = 0

        for dept in self.departments:
            hits = sum(
                1 for kw in dept.get("keywords", []) if kw.lower() in concern_lower
            )
            if hits > best_hits:
                best_hits = hits
                best_dept = dept

        # Additional token-level hint for broad body-region words
        if best_dept is None:
            region_hints = {
                "ORTHO": ["knee", "back", "joint", "bone", "shoulder", "ankle", "wrist", "hip", "spine"],
                "ENT": ["ear", "nose", "throat", "sinus", "hearing", "tonsil"],
                "DERM": ["skin", "rash", "itch", "scalp", "nail", "acne"],
                "OPHTH": ["eye", "vision", "sight", "eyelid"],
                "CARDIO": ["blood pressure", "heart", "pulse", "palpitation"],
                "GEN_MED": ["fever", "cold", "cough", "headache", "fatigue"],
            }
            for dept_id, hints in region_hints.items():
                if any(h in concern_lower for h in hints):
                    best_dept = self.dept_map.get(dept_id)
                    best_hits = 1
                    break

        if best_dept is None:
            gen = self.dept_map.get("GEN_MED") or self.departments[0]
            return RoutingDecision(
                department_id=gen["id"],
                department_name=gen["name"],
                routing_explanation=(
                    f"Routed to {gen['name']} for general initial evaluation of the reported concern."
                ),
                confidence="LOW",
                requires_human_review=True,
            )

        confidence = "HIGH" if best_hits >= 1 else "MEDIUM"
        return RoutingDecision(
            department_id=best_dept["id"],
            department_name=best_dept["name"],
            routing_explanation=(
                f"Routed to {best_dept['name']} based on the patient's reported concern "
                f"for appropriate specialist evaluation."
            ),
            confidence=confidence,
            requires_human_review=(confidence == "LOW"),
        )

    async def arun(
        self,
        intake: PatientIntakeRecord,
        memory: Optional[PatientMemoryRecord] = None,
    ) -> RoutingDecision:
        dept_catalog = "\n".join(
            f"- {d['id']} ({d['name']}): {d['description']} | Keywords: {', '.join(d.get('keywords', []))}"
            for d in self.departments
        )
        memory_text = "None"
        if memory is not None:
            memory_text = (
                f"Previous department: {memory.previous_department}; "
                f"Previous concern: {memory.previous_concern}"
            )

        prompt = (
            f"Available Departments:\n{dept_catalog}\n\n"
            f"Current Patient Concern: {intake.concern}\n"
            f"Duration: {intake.duration or 'unspecified'}\n"
            f"Historical Context (do not override current concern): {memory_text}\n\n"
            "Return ONLY JSON."
        )

        data = await self.client.arun_agent_json(
            name="TriageRouterAgent",
            instructions=self.SYSTEM_INSTRUCTIONS,
            user_prompt=prompt,
        )
        if data and data.get("department_id") in self.dept_map:
            dept = self.dept_map[data["department_id"]]
            confidence = data.get("confidence", "MEDIUM")
            if confidence not in ("HIGH", "MEDIUM", "LOW"):
                confidence = "MEDIUM"
            explanation = str(
                data.get("routing_explanation")
                or f"Routed to {dept['name']} based on the reported concern."
            ).strip()

            return RoutingDecision(
                department_id=dept["id"],
                department_name=dept["name"],
                routing_explanation=explanation,
                confidence=confidence,
                requires_human_review=(confidence == "LOW"),
            )

        return self._fallback_route(intake)

    def run(
        self,
        intake: PatientIntakeRecord,
        memory: Optional[PatientMemoryRecord] = None,
    ) -> RoutingDecision:
        return run_sync(self.arun(intake=intake, memory=memory))