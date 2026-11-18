import asyncio
import sys
from pathlib import Path

from sqlalchemy import delete

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.db import PatientHistoryModel, SessionLocal
from backend.database.seed import seed_database
from backend.workflows.hospital_workflow import run_intake_workflow


def _trace_status_map(state) -> dict:
    return {event.agent_name: event.status for event in state.trace}


def _reset_p1001_seed_state() -> None:
    """Keep seeded P1001 ENT history clean so tests remain idempotent across runs."""
    seed_database()
    with SessionLocal() as session:
        with session.begin():
            session.execute(
                delete(PatientHistoryModel).where(
                    PatientHistoryModel.patient_id == "P1001",
                    PatientHistoryModel.routed_department != "ENT",
                )
            )


def test_journey_1_normal_new_patient():
    state = asyncio.run(
        run_intake_workflow(
            "I have had pain and stiffness in my right knee for 5 days.",
            name="Riya",
            age=28,
        )
    )
    assert state.safety is not None and state.safety.status == "CLEAR"
    assert state.routing is not None and state.routing.department_id == "ORTHO"
    assert state.department_info is not None
    assert any(c.source_file == "ortho.md" for c in state.department_info.citations)
    assert len(state.offered_slots) > 0

    statuses = _trace_status_map(state)
    for agent_name in [
        "IntakeAgent",
        "SafetyGateAgent",
        "TriageRouterAgent",
        "InformationAgent",
        "AppointmentAgent",
        "ResponseAggregator",
    ]:
        assert statuses.get(agent_name) == "COMPLETED", (
            f"Expected {agent_name}=COMPLETED, got {statuses}"
        )
    assert "DISCLAIMER" in state.final_response_text


def test_journey_2_urgent_safety_stop():
    state = asyncio.run(
        run_intake_workflow(
            "I am having severe crushing chest pain radiating to my left arm and shortness of breath.",
            name="Karan",
            age=52,
        )
    )
    assert state.safety is not None and state.safety.status == "URGENT"
    assert state.routing is None
    assert state.department_info is None
    assert state.offered_slots == []

    statuses = _trace_status_map(state)
    assert statuses.get("SafetyGateAgent") == "STOPPED"
    assert statuses.get("TriageRouterAgent") == "SKIPPED"
    assert statuses.get("InformationAgent") == "SKIPPED"
    assert statuses.get("AppointmentAgent") == "SKIPPED"
    assert statuses.get("ResponseAggregator") == "COMPLETED"
    assert "emergency" in state.final_response_text.lower()
    assert "DISCLAIMER" in state.final_response_text


def test_journey_3_returning_patient_with_consent_new_symptom():
    _reset_p1001_seed_state()
    try:
        state = asyncio.run(
            run_intake_workflow(
                "Itchy red skin rash on my forearms for 3 days.",
                patient_id="P1001",
                name="Aarav Sharma",
                consent_memory=True,
            )
        )
        assert state.memory is not None
        assert state.memory.previous_department == "ENT"
        assert state.safety is not None and state.safety.status == "CLEAR"
        assert state.routing is not None and state.routing.department_id == "DERM"

        statuses = _trace_status_map(state)
        assert statuses.get("PatientMemoryAgent") == "COMPLETED"
        assert statuses.get("SafetyGateAgent") == "COMPLETED"
        assert statuses.get("TriageRouterAgent") == "COMPLETED"

        assert "ENT" in state.final_response_text
        assert (
            "Dermatology" in state.final_response_text
            or "DERM" in state.final_response_text
        )
        assert "DISCLAIMER" in state.final_response_text
    finally:
        _reset_p1001_seed_state()


def test_journey_4_returning_patient_without_consent():
    _reset_p1001_seed_state()
    state = asyncio.run(
        run_intake_workflow(
            "Blurry vision when reading for a week.",
            patient_id="P1001",
            name="Aarav Sharma",
            consent_memory=False,
        )
    )
    assert state.memory is None
    assert state.safety is not None and state.safety.status == "CLEAR"
    assert state.routing is not None and state.routing.department_id == "OPHTH"

    statuses = _trace_status_map(state)
    assert statuses.get("PatientMemoryAgent") == "SKIPPED"
    assert statuses.get("TriageRouterAgent") == "COMPLETED"
    assert "DISCLAIMER" in state.final_response_text


if __name__ == "__main__":
    tests = [
        test_journey_1_normal_new_patient,
        test_journey_2_urgent_safety_stop,
        test_journey_3_returning_patient_with_consent_new_symptom,
        test_journey_4_returning_patient_without_consent,
    ]
    for test_fn in tests:
        test_fn()
        print(f"PASS: {test_fn.__name__}")
    print("\nAll Milestone 3 end-to-end journey checks passed!")