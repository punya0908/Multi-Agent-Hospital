from typing import Any, Dict, Optional, Union

from backend.agents.llm_client import run_sync
from backend.agents.supervisor import SupervisorAgent
from backend.database.seed import seed_database
from backend.schemas.workflow_state import WorkflowState


async def run_intake_workflow(
    raw_input: Union[str, Dict[str, Any]],
    patient_id: Optional[str] = None,
    name: Optional[str] = None,
    age: Optional[int] = None,
    duration: Optional[str] = None,
    consent_memory: Optional[bool] = None,
    run_id: Optional[str] = None,
    supervisor: Optional[SupervisorAgent] = None,
) -> WorkflowState:
    seed_database()
    orchestrator = supervisor or SupervisorAgent()
    return await orchestrator.arun(
        raw_input=raw_input,
        patient_id=patient_id,
        name=name,
        age=age,
        duration=duration,
        consent_memory=consent_memory,
        run_id=run_id,
    )


def run_intake_workflow_sync(
    raw_input: Union[str, Dict[str, Any]],
    patient_id: Optional[str] = None,
    name: Optional[str] = None,
    age: Optional[int] = None,
    duration: Optional[str] = None,
    consent_memory: Optional[bool] = None,
    run_id: Optional[str] = None,
    supervisor: Optional[SupervisorAgent] = None,
) -> WorkflowState:
    return run_sync(
        run_intake_workflow(
            raw_input=raw_input,
            patient_id=patient_id,
            name=name,
            age=age,
            duration=duration,
            consent_memory=consent_memory,
            run_id=run_id,
            supervisor=supervisor,
        )
    )