import sys
from pathlib import Path

# Ensure project root is on sys.path when executed directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.seed import seed_database
from backend.services.appointment_service import AppointmentService
from backend.services.patient_memory_service import PatientMemoryService
from backend.services.safety_rule_service import SafetyRuleService


def test_database_seeding():
    seed_database()
    # Call a second time to verify idempotency
    seed_database()
    appt_service = AppointmentService()
    for dept in ["GEN_MED", "ORTHO", "ENT", "DERM", "OPHTH", "CARDIO"]:
        slots = appt_service.get_available_slots(dept)
        assert len(slots) >= 2, f"Expected >=2 slots for {dept}, got {len(slots)}"


def test_safety_urgent_chest_pain():
    safety_service = SafetyRuleService()
    result = safety_service.evaluate("I have crushing chest pain")
    assert result.status == "URGENT", f"Expected URGENT, got {result.status}"
    assert result.requires_immediate_care is True
    assert len(result.matched_rules) >= 1


def test_safety_negation_clear():
    safety_service = SafetyRuleService()
    result = safety_service.evaluate("I have knee pain, no chest pain")
    assert result.status == "CLEAR", f"Expected CLEAR, got {result.status}"
    assert result.requires_immediate_care is False
    assert result.matched_rules == []


def test_memory_service_consent():
    seed_database()
    memory_service = PatientMemoryService()

    # With consent=True -> returns P1001 ENT history
    history_with_consent = memory_service.get_patient_history("P1001", consent=True)
    assert history_with_consent is not None, "Expected P1001 history when consent=True"
    assert history_with_consent.patient_id == "P1001"
    assert history_with_consent.previous_department == "ENT"

    # With consent=False -> returns None
    history_without_consent = memory_service.get_patient_history("P1001", consent=False)
    assert history_without_consent is None, "Expected None when consent=False"


def test_appointment_service_ortho():
    seed_database()
    appt_service = AppointmentService()
    ortho_slots = appt_service.get_available_slots("ORTHO")
    assert len(ortho_slots) >= 2, f"Expected >=2 ORTHO slots, got {len(ortho_slots)}"
    assert all(slot.department_id == "ORTHO" and slot.is_available for slot in ortho_slots)


if __name__ == "__main__":
    tests = [
        test_database_seeding,
        test_safety_urgent_chest_pain,
        test_safety_negation_clear,
        test_memory_service_consent,
        test_appointment_service_ortho,
    ]
    for test_fn in tests:
        test_fn()
        print(f"PASS: {test_fn.__name__}")
    print("\nAll Milestone 1 checks passed!")