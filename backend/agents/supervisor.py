import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union

from backend.agents.appointment_agent import AppointmentAgent
from backend.agents.information_agent import InformationAgent
from backend.agents.intake_agent import IntakeAgent
from backend.agents.llm_client import run_sync
from backend.agents.patient_memory_agent import PatientMemoryAgent
from backend.agents.response_aggregator import MANDATORY_DISCLAIMER, ResponseAggregator
from backend.agents.safety_gate import SafetyGateAgent
from backend.agents.triage_router import TriageRouterAgent
from backend.schemas.workflow_state import AgentExecutionEvent, WorkflowState
from backend.services.patient_memory_service import PatientMemoryService


class SupervisorAgent:
    def __init__(
        self,
        intake_agent: Optional[IntakeAgent] = None,
        memory_agent: Optional[PatientMemoryAgent] = None,
        safety_gate: Optional[SafetyGateAgent] = None,
        triage_router: Optional[TriageRouterAgent] = None,
        information_agent: Optional[InformationAgent] = None,
        appointment_agent: Optional[AppointmentAgent] = None,
        response_aggregator: Optional[ResponseAggregator] = None,
        memory_service: Optional[PatientMemoryService] = None,
    ) -> None:
        self.memory_service = memory_service or PatientMemoryService()
        self.intake_agent = intake_agent or IntakeAgent()
        self.memory_agent = memory_agent or PatientMemoryAgent(
            memory_service=self.memory_service
        )
        self.safety_gate = safety_gate or SafetyGateAgent()
        self.triage_router = triage_router or TriageRouterAgent()
        self.information_agent = information_agent or InformationAgent()
        self.appointment_agent = appointment_agent or AppointmentAgent()
        self.response_aggregator = response_aggregator or ResponseAggregator()

    @staticmethod
    def _log_event(
        state: WorkflowState,
        agent_name: str,
        status: str,
        summary: str,
    ) -> None:
        state.trace.append(
            AgentExecutionEvent(
                agent_name=agent_name,
                status=status,
                summary=summary,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        )

    async def arun(
        self,
        raw_input: Union[str, Dict[str, Any]],
        patient_id: Optional[str] = None,
        name: Optional[str] = None,
        age: Optional[int] = None,
        duration: Optional[str] = None,
        consent_memory: Optional[bool] = None,
        run_id: Optional[str] = None,
    ) -> WorkflowState:
        state = WorkflowState(
            run_id=run_id or str(uuid.uuid4()),
            disclaimer=MANDATORY_DISCLAIMER,
        )

        # ------------------------------------------------------------------
        # Node 1: IntakeAgent
        # ------------------------------------------------------------------
        effective_consent = bool(consent_memory) if consent_memory is not None else False
        intake = await self.intake_agent.arun(
            raw_input=raw_input,
            patient_id=patient_id,
            consent_memory=effective_consent,
        )
        if patient_id is not None:
            intake.patient_id = patient_id
        if name is not None:
            intake.name = name
        if age is not None:
            intake.age = age
        if duration is not None:
            intake.duration = duration
        if consent_memory is not None:
            intake.consent_memory = consent_memory

        state.intake = intake
        self._log_event(
            state,
            "IntakeAgent",
            "COMPLETED",
            f"Normalized intake for '{intake.name}' (consent_memory={intake.consent_memory}).",
        )

        # ------------------------------------------------------------------
        # Node 2: PatientMemoryAgent
        # ------------------------------------------------------------------
        if state.intake.patient_id and state.intake.consent_memory:
            memory_record = await self.memory_agent.arun(state.intake)
            state.memory = memory_record
            mem_summary = (
                f"Retrieved prior routing to {memory_record.previous_department}."
                if memory_record is not None
                else "Checked history with consent; no prior record found."
            )
            self._log_event(state, "PatientMemoryAgent", "COMPLETED", mem_summary)
        else:
            state.memory = None
            self._log_event(
                state,
                "PatientMemoryAgent",
                "SKIPPED",
                "Skipped memory lookup (no patient_id or consent_memory=False).",
            )

        # ------------------------------------------------------------------
        # Node 3: SafetyGateAgent (MANDATORY GATE)
        # ------------------------------------------------------------------
        safety_result = await self.safety_gate.arun(state.intake)
        state.safety = safety_result

        if safety_result.status in ("URGENT", "UNCERTAIN"):
            self._log_event(
                state,
                "SafetyGateAgent",
                "STOPPED",
                f"Safety gate triggered {safety_result.status} stop ({safety_result.matched_rules}).",
            )
            self._log_event(
                state,
                "TriageRouterAgent",
                "SKIPPED",
                f"Skipped due to SafetyGateAgent status={safety_result.status}.",
            )
            self._log_event(
                state,
                "InformationAgent",
                "SKIPPED",
                f"Skipped due to SafetyGateAgent status={safety_result.status}.",
            )
            self._log_event(
                state,
                "AppointmentAgent",
                "SKIPPED",
                f"Skipped due to SafetyGateAgent status={safety_result.status}.",
            )

            state = self.response_aggregator.run(state)
            self._log_event(
                state,
                "ResponseAggregator",
                "COMPLETED",
                f"Aggregated {safety_result.status} safety advisory response.",
            )
            return state

        self._log_event(
            state,
            "SafetyGateAgent",
            "COMPLETED",
            "Safety screening passed with status=CLEAR.",
        )

        # ------------------------------------------------------------------
        # Node 4: TriageRouterAgent
        # ------------------------------------------------------------------
        routing_decision = await self.triage_router.arun(
            intake=state.intake,
            memory=state.memory,
        )
        state.routing = routing_decision

        if routing_decision.requires_human_review:
            self._log_event(
                state,
                "TriageRouterAgent",
                "STOPPED",
                f"Low-confidence routing ({routing_decision.department_id}); paused for human review.",
            )
            self._log_event(
                state,
                "InformationAgent",
                "SKIPPED",
                "Skipped because routing requires human review.",
            )
            self._log_event(
                state,
                "AppointmentAgent",
                "SKIPPED",
                "Skipped because routing requires human review.",
            )

            state = self.response_aggregator.run(state)
            self._log_event(
                state,
                "ResponseAggregator",
                "COMPLETED",
                "Aggregated human-review escalation response.",
            )
            return state

        self._log_event(
            state,
            "TriageRouterAgent",
            "COMPLETED",
            f"Routed to {routing_decision.department_id} ({routing_decision.confidence}).",
        )

        # ------------------------------------------------------------------
        # Node 5: Parallel Fan-Out & Fan-In (InformationAgent + AppointmentAgent)
        # ------------------------------------------------------------------
        dept_info, offered_slots = await asyncio.gather(
            self.information_agent.arun(routing_decision, state.intake),
            self.appointment_agent.arun(routing_decision),
        )
        state.department_info = dept_info
        state.offered_slots = offered_slots

        self._log_event(
            state,
            "InformationAgent",
            "COMPLETED",
            f"Retrieved {len(dept_info.citations)} grounded citations for {routing_decision.department_id}.",
        )
        self._log_event(
            state,
            "AppointmentAgent",
            "COMPLETED",
            f"Fetched {len(offered_slots)} available slots for {routing_decision.department_id}.",
        )

        if state.intake.consent_memory and state.intake.patient_id:
            self.memory_service.save_patient_history(
                patient_id=state.intake.patient_id,
                name=state.intake.name,
                consent=True,
                routed_department=routing_decision.department_id,
                concern_summary=state.intake.concern,
                routing_explanation=routing_decision.routing_explanation,
            )

        # ------------------------------------------------------------------
        # Node 6: ResponseAggregator
        # ------------------------------------------------------------------
        state = self.response_aggregator.run(state)
        self._log_event(
            state,
            "ResponseAggregator",
            "COMPLETED",
            "Aggregated complete department routing, instructions, slots, and disclaimer.",
        )
        return state

    def run(self, *args: Any, **kwargs: Any) -> WorkflowState:
        return run_sync(self.arun(*args, **kwargs))