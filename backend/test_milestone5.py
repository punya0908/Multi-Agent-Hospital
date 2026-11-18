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


def test_appointment_confirm_triggers_email_service():
    with TestClient(app) as client:
        intake_resp = client.post(
            "/api/intake",
            json={
                "name": "Riya Verma",
                "age": 28,
                "concern": "Right knee pain and stiffness for 4 days",
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
                    "patient_name": "Riya Verma",
                    "department_id": "ORTHO",
                    "run_id": intake_data["run_id"],
                },
            )
            assert confirm_resp.status_code == 200, confirm_resp.text
            data = confirm_resp.json()
            assert data["status"] == "CONFIRMED"
            assert data["email_status"] in ("SENT_TO_GMAIL", "SIMULATED_NO_CREDENTIALS")
            assert bool(data["recipient"])
        finally:
            _restore_slot_availability(slot_id)


def test_twilio_voice_urgent_chest_pain_twiml():
    with TestClient(app) as client:
        resp = client.post(
            "/api/twilio/voice",
            data={
                "SpeechResult": "I have severe chest pain",
                "Caller": "+919999999999",
                "CallSid": "CA_TEST_URGENT",
            },
        )
        assert resp.status_code == 200
        assert "application/xml" in resp.headers["content-type"]
        assert "<Response>" in resp.text and "<Say>" in resp.text
        assert "112" in resp.text


def test_twilio_voice_normal_ortho_twiml():
    with TestClient(app) as client:
        resp = client.post(
            "/api/twilio/voice",
            data={
                "SpeechResult": "My knee hurts for 3 days",
                "Caller": "+919999999999",
                "CallSid": "CA_TEST_ORTHO",
            },
        )
        assert resp.status_code == 200
        assert "application/xml" in resp.headers["content-type"]
        assert "<Response>" in resp.text and "<Say>" in resp.text
        assert "Orthopaedics" in resp.text


def test_voice_transcribe_json_fallback():
    with TestClient(app) as client:
        resp = client.post(
            "/api/voice/transcribe",
            json={
                "transcript": "Hi, I am Riya, 28. My knee hurts for 4 days.",
                "consent_memory": False,
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "knee" in data["transcript"].lower()
        assert data["extracted_intake"]["name"]
        assert "spoken_confirmation_prompt" in data


if __name__ == "__main__":
    tests = [
        test_appointment_confirm_triggers_email_service,
        test_twilio_voice_urgent_chest_pain_twiml,
        test_twilio_voice_normal_ortho_twiml,
        test_voice_transcribe_json_fallback,
    ]
    for test_fn in tests:
        test_fn()
        print(f"PASS: {test_fn.__name__}")
    print("\nAll Milestone 5 verification checks passed!")