import re
from typing import List

from backend.schemas.workflow_state import WorkflowState

MANDATORY_DISCLAIMER = (
    "DISCLAIMER: This assistant is an administrative hospital department routing "
    "and information tool. It does not provide medical diagnoses, treatment "
    "recommendations, or replace consultation with a qualified healthcare professional."
)


class ResponseAggregator:
    DIAGNOSTIC_PATTERNS = [
        r"\bdiagnosed with\b",
        r"\bdiagnosis\s*(?:is|:)\b",
        r"\byou (?:likely |probably )?have (?:an? )?(?:infection|disease|disorder|syndrome|arthritis|fracture|asthma|migraine|dermatitis|conjunctivitis|angina)\b",
    ]

    def _sanitize_non_diagnostic(self, text: str) -> str:
        sanitized = text
        for pattern in self.DIAGNOSTIC_PATTERNS:
            sanitized = re.sub(
                pattern,
                "reported symptoms requiring clinician evaluation",
                sanitized,
                flags=re.IGNORECASE,
            )
        return sanitized

    def run(self, state: WorkflowState) -> WorkflowState:
        state.disclaimer = MANDATORY_DISCLAIMER
        sections: List[str] = []

        # Path 1: URGENT safety stop
        if state.safety is not None and state.safety.status == "URGENT":
            state.routing = None
            state.department_info = None
            state.offered_slots = []

            sections.append(
                "URGENT SAFETY ADVISORY: Based on your description, do NOT wait for a "
                "routine outpatient appointment."
            )
            sections.append(
                "Please seek immediate in-person emergency care at the nearest Emergency "
                "Department or call emergency services (112 / your local emergency number) right away."
            )
            if state.safety.advisory_message:
                sections.append(f"Details: {state.safety.advisory_message}")

        # Path 2: UNCERTAIN safety status or LOW-confidence human review escalation
        elif (
            state.safety is None
            or state.safety.status == "UNCERTAIN"
            or (state.routing is not None and state.routing.requires_human_review)
        ):
            state.department_info = None
            state.offered_slots = []

            sections.append(
                "HUMAN REVIEW REQUIRED: Automated routing has been paused to ensure your "
                "concern is reviewed safely."
            )
            sections.append(
                "Hospital intake staff will review your concern directly and assist you "
                "with the appropriate next steps."
            )
            if state.safety and state.safety.advisory_message:
                sections.append(f"Safety Note: {state.safety.advisory_message}")

        # Path 3: CLEAR safety status & successful routing
        elif state.safety.status == "CLEAR" and state.routing is not None:
            if state.memory is not None:
                sections.append(
                    f"Historical Context Note: Records show a previous visit routed to "
                    f"{state.memory.previous_department} (for '{state.memory.previous_concern}'). "
                    f"This is included for historical context only and did not override your current concern."
                )

            sections.append(
                f"Recommended Department: {state.routing.department_name} ({state.routing.department_id})"
            )
            sections.append(f"Routing Explanation: {state.routing.routing_explanation}")

            if state.department_info is not None:
                sections.append(f"Department Location: {state.department_info.location}")
                if state.department_info.instructions:
                    instr_lines = "\n".join(
                        f"- {item}" for item in state.department_info.instructions
                    )
                    sections.append(f"Pre-Visit & Registration Instructions:\n{instr_lines}")
                if state.department_info.documents_to_bring:
                    docs_lines = "\n".join(
                        f"- {item}" for item in state.department_info.documents_to_bring
                    )
                    sections.append(f"What to Bring:\n{docs_lines}")
                if state.department_info.citations:
                    sources = sorted(
                        {c.source_file for c in state.department_info.citations}
                    )
                    sections.append(f"Information Sources: {', '.join(sources)}")

            if state.offered_slots:
                slot_lines = "\n".join(
                    f"- [{s.slot_id}] {s.date} {s.start_time}-{s.end_time} with {s.provider_name}"
                    for s in state.offered_slots
                )
                sections.append(
                    "Available Appointment Options (unbooked — confirmation is required to book a slot):\n"
                    f"{slot_lines}"
                )
            else:
                sections.append(
                    "Appointment Availability: No open slots were found right now. "
                    "Please contact the department desk for scheduling assistance."
                )

        body = self._sanitize_non_diagnostic("\n\n".join(sections).strip())
        state.final_response_text = f"{body}\n\n{MANDATORY_DISCLAIMER}".strip()
        return state