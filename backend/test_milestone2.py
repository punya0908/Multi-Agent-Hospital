import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.agents.appointment_agent import AppointmentAgent
from backend.agents.information_agent import InformationAgent
from backend.agents.intake_agent import IntakeAgent
from backend.agents.safety_gate import SafetyGateAgent
from backend.agents.triage_router import TriageRouterAgent
from backend.database.seed import seed_database
from backend.schemas.workflow_state import PatientIntakeRecord
from backend.services.rag_service import RAGService


def test_rag_service_department_isolation():
    rag = RAGService()
    docs = rag.retrieve_department_docs(
        department_id="ORTHO",
        query="knee pain x-rays clothing location",
        top_k=3,
    )
    assert len(docs) >= 1, "Expected at least 1 retrieved doc for ORTHO"
    assert all(d.department_id == "ORTHO" for d in docs), "Leaked non-ORTHO department docs"
    assert all(d.source_file == "ortho.md" for d in docs), "Expected only ortho.md chunks"
    assert all(d.source_file != "ent.md" for d in docs), "ent.md must never leak into ORTHO query"


def test_intake_agent_normalization():
    intake_agent = IntakeAgent()
    raw_msg = "Hi, I am Riya, 28. My right knee has been hurting for 4 days when climbing stairs"
    record = intake_agent.run(raw_msg)
    assert isinstance(record, PatientIntakeRecord)
    assert "riya" in record.name.lower(), f"Expected name Riya, got {record.name}"
    assert record.age == 28, f"Expected age 28, got {record.age}"
    assert "knee" in record.concern.lower(), f"Expected knee in concern, got {record.concern}"
    assert record.duration is not None and "4 day" in record.duration.lower(), (
        f"Expected 4 days duration, got {record.duration}"
    )


def test_safety_gate_clear_and_urgent():
    safety_gate = SafetyGateAgent()

    knee_record = PatientIntakeRecord(
        name="Riya",
        age=28,
        concern="My right knee has been hurting for 4 days when climbing stairs",
        duration="4 days",
    )
    clear_res = safety_gate.run(knee_record)
    assert clear_res.status == "CLEAR", f"Expected CLEAR, got {clear_res.status}"
    assert clear_res.requires_immediate_care is False

    chest_record = PatientIntakeRecord(
        name="Test Patient",
        age=50,
        concern="I am having crushing chest pain and sweating",
    )
    urgent_res = safety_gate.run(chest_record)
    assert urgent_res.status == "URGENT", f"Expected URGENT, got {urgent_res.status}"
    assert urgent_res.requires_immediate_care is True


def test_triage_router_ortho_no_diagnosis():
    router = TriageRouterAgent()
    knee_record = PatientIntakeRecord(
        name="Riya",
        age=28,
        concern="My right knee has been hurting for 4 days when climbing stairs",
        duration="4 days",
    )
    decision = router.run(knee_record)
    assert decision.department_id == "ORTHO", f"Expected ORTHO, got {decision.department_id}"
    assert decision.department_name == "Orthopaedics"

    explanation_lower = decision.routing_explanation.lower()
    forbidden_diagnostic_terms = [
        "osteoarthritis",
        "meniscus tear",
        "arthritis",
        "tendinitis",
        "tendonitis",
        "bursitis",
        "diagnosed with",
    ]
    for term in forbidden_diagnostic_terms:
        assert term not in explanation_lower, f"Diagnostic term '{term}' found in explanation"


def test_information_agent_grounded_ortho():
    rag = RAGService()
    info_agent = InformationAgent(rag_service=rag)
    router = TriageRouterAgent()

    knee_record = PatientIntakeRecord(
        name="Riya",
        age=28,
        concern="My right knee has been hurting for 4 days when climbing stairs",
        duration="4 days",
    )
    decision = router.run(knee_record)
    dept_info = info_agent.run(decision, knee_record)

    assert dept_info.department_id == "ORTHO"
    assert len(dept_info.instructions) >= 1
    assert "Block B" in dept_info.location
    citation_files = [c.source_file for c in dept_info.citations]
    assert "ortho.md" in citation_files, f"Expected ortho.md in citations, got {citation_files}"


def test_appointment_agent_ortho_slots():
    seed_database()
    appt_agent = AppointmentAgent()
    router = TriageRouterAgent()

    knee_record = PatientIntakeRecord(
        name="Riya",
        age=28,
        concern="My right knee has been hurting for 4 days when climbing stairs",
        duration="4 days",
    )
    decision = router.run(knee_record)
    slots = appt_agent.run(decision)

    assert len(slots) >= 2, f"Expected >=2 ORTHO slots from SQLite, got {len(slots)}"
    assert all(s.department_id == "ORTHO" and s.is_available for s in slots)


if __name__ == "__main__":
    tests = [
        test_rag_service_department_isolation,
        test_intake_agent_normalization,
        test_safety_gate_clear_and_urgent,
        test_triage_router_ortho_no_diagnosis,
        test_information_agent_grounded_ortho,
        test_appointment_agent_ortho_slots,
    ]
    for test_fn in tests:
        test_fn()
        print(f"PASS: {test_fn.__name__}")
    print("\nAll Milestone 2 checks passed!")