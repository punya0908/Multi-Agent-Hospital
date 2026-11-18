import sys
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import update

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.database.db import AppointmentSlotModel, SessionLocal
from backend.main import app


def _restore_slot_availability(slot_id: str) -> None:
    with SessionLocal() as session:
        with session.begin():
            session.execute(
                update(AppointmentSlotModel)
                .where(AppointmentSlotModel.slot_id == slot_id)
                .values(is_available=True)
            )


def test_health_and_departments():
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}

        depts = client.get("/api/departments")
        assert depts.status_code == 200
        dept_ids = [d["id"] for d in depts.json()["departments"]]
        assert "ORTHO" in dept_ids and len(dept_ids) == 6


def test_post_intake_normal_knee_pain():
    with TestClient(app) as client:
        resp = client.post(
            "/api/intake",
            json={
                "name": "Riya",
                "age": 28,
                "concern": "Right knee pain and stiffness when climbing stairs",
                "duration": "4 days",
                "consent_memory": False,
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["safety"]["status"] == "CLEAR"
        assert data["routing"]["department_id"] == "ORTHO"
        assert len(data["offered_slots"]) >= 1

        trace_resp = client.get(f"/api/intake/{data['run_id']}/trace")
        assert trace_resp.status_code == 200
        assert len(trace_resp.json()["trace"]) == len(data["trace"])


def test_post_intake_urgent_chest_pain():
    with TestClient(app) as client:
        resp = client.post(
            "/api/intake",
            json={
                "name": "Karan",
                "age": 54,
                "concern": "Severe crushing chest pain and shortness of breath",
                "duration": "30 minutes",
                "consent_memory": False,
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["safety"]["status"] == "URGENT"
        assert data["routing"] is None
        assert data["offered_slots"] == []

        trace_map = {e["agent_name"]: e["status"] for e in data["trace"]}
        assert trace_map["SafetyGateAgent"] == "STOPPED"
        assert trace_map["TriageRouterAgent"] == "SKIPPED"
        assert trace_map["InformationAgent"] == "SKIPPED"
        assert trace_map["AppointmentAgent"] == "SKIPPED"


def test_post_confirm_appointment_slot():
    with TestClient(app) as client:
        intake_resp = client.post(
            "/api/intake",
            json={
                "name": "Riya",
                "age": 28,
                "concern": "Right knee pain and stiffness",
                "duration": "4 days",
                "consent_memory": False,
            },
        )
        assert intake_resp.status_code == 200
        intake_data = intake_resp.json()
        slot_id = intake_data["offered_slots"][0]["slot_id"]

        try:
            confirm_resp = client.post(
                "/api/appointments/confirm",
                json={
                    "slot_id": slot_id,
                    "patient_name": "Riya",
                    "department_id": "ORTHO",
                    "run_id": intake_data["run_id"],
                },
            )
            assert confirm_resp.status_code == 200, confirm_resp.text
            confirmed = confirm_resp.json()
            assert confirmed["status"] == "CONFIRMED"
            assert confirmed["booking_reference"].startswith("BK-")
            assert confirmed["slot"]["slot_id"] == slot_id
            assert confirmed["slot"]["is_available"] is False

            # Attempting to book the same slot again must fail (no longer available)
            second_try = client.post(
                "/api/appointments/confirm",
                json={
                    "slot_id": slot_id,
                    "patient_name": "Another Patient",
                    "department_id": "ORTHO",
                },
            )
            assert second_try.status_code == 409
        finally:
            _restore_slot_availability(slot_id)


if __name__ == "__main__":
    tests = [
        test_health_and_departments,
        test_post_intake_normal_knee_pain,
        test_post_intake_urgent_chest_pain,
        test_post_confirm_appointment_slot,
    ]
    for test_fn in tests:
        test_fn()
        print(f"PASS: {test_fn.__name__}")
    print("\nAll Milestone 4 API tests passed!")