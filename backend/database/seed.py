from datetime import date, datetime, timedelta, timezone
from sqlalchemy import select

from backend.database.db import (
    AppointmentSlotModel,
    PatientHistoryModel,
    SessionLocal,
    init_db,
)


def seed_database() -> None:
    init_db()

    today = date.today()
    day_1 = (today + timedelta(days=1)).isoformat()
    day_2 = (today + timedelta(days=2)).isoformat()

    seed_slots = [
        # GEN_MED
        AppointmentSlotModel(
            slot_id="SLOT_GEN_01",
            department_id="GEN_MED",
            provider_name="Dr. Meera Nair",
            date=day_1,
            start_time="09:00",
            end_time="09:30",
            is_available=True,
        ),
        AppointmentSlotModel(
            slot_id="SLOT_GEN_02",
            department_id="GEN_MED",
            provider_name="Dr. Rohan Verma",
            date=day_2,
            start_time="11:00",
            end_time="11:30",
            is_available=True,
        ),
        # ORTHO
        AppointmentSlotModel(
            slot_id="SLOT_ORTHO_01",
            department_id="ORTHO",
            provider_name="Dr. Vikram Kulkarni",
            date=day_1,
            start_time="10:00",
            end_time="10:30",
            is_available=True,
        ),
        AppointmentSlotModel(
            slot_id="SLOT_ORTHO_02",
            department_id="ORTHO",
            provider_name="Dr. Ananya Rao",
            date=day_2,
            start_time="14:00",
            end_time="14:30",
            is_available=True,
        ),
        # ENT
        AppointmentSlotModel(
            slot_id="SLOT_ENT_01",
            department_id="ENT",
            provider_name="Dr. Siddharth Menon",
            date=day_1,
            start_time="09:30",
            end_time="10:00",
            is_available=True,
        ),
        AppointmentSlotModel(
            slot_id="SLOT_ENT_02",
            department_id="ENT",
            provider_name="Dr. Kavita Iyer",
            date=day_2,
            start_time="15:00",
            end_time="15:30",
            is_available=True,
        ),
        # DERM
        AppointmentSlotModel(
            slot_id="SLOT_DERM_01",
            department_id="DERM",
            provider_name="Dr. Priya Deshmukh",
            date=day_1,
            start_time="11:30",
            end_time="12:00",
            is_available=True,
        ),
        AppointmentSlotModel(
            slot_id="SLOT_DERM_02",
            department_id="DERM",
            provider_name="Dr. Arjun Kapoor",
            date=day_2,
            start_time="16:00",
            end_time="16:30",
            is_available=True,
        ),
        # OPHTH
        AppointmentSlotModel(
            slot_id="SLOT_OPHTH_01",
            department_id="OPHTH",
            provider_name="Dr. Neha Joshi",
            date=day_1,
            start_time="13:00",
            end_time="13:30",
            is_available=True,
        ),
        AppointmentSlotModel(
            slot_id="SLOT_OPHTH_02",
            department_id="OPHTH",
            provider_name="Dr. Rajeev Bansal",
            date=day_2,
            start_time="10:30",
            end_time="11:00",
            is_available=True,
        ),
        # CARDIO
        AppointmentSlotModel(
            slot_id="SLOT_CARDIO_01",
            department_id="CARDIO",
            provider_name="Dr. Sanjay Chatterjee",
            date=day_1,
            start_time="15:30",
            end_time="16:00",
            is_available=True,
        ),
        AppointmentSlotModel(
            slot_id="SLOT_CARDIO_02",
            department_id="CARDIO",
            provider_name="Dr. Deepa Krishnan",
            date=day_2,
            start_time="09:00",
            end_time="09:30",
            is_available=True,
        ),
    ]

    with SessionLocal() as session:
        existing_slot_ids = set(
            session.scalars(select(AppointmentSlotModel.slot_id)).all()
        )
        for slot in seed_slots:
            if slot.slot_id not in existing_slot_ids:
                session.add(slot)

        existing_patient = session.scalars(
            select(PatientHistoryModel).where(
                PatientHistoryModel.patient_id == "P1001"
            )
        ).first()

        if existing_patient is None:
            session.add(
                PatientHistoryModel(
                    patient_id="P1001",
                    name="Aarav Sharma",
                    consent_given=True,
                    routed_department="ENT",
                    concern_summary="Mild ear ache and ringing",
                    routing_explanation="Routed to ENT for ear-related symptom evaluation.",
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
            )

        session.commit()


if __name__ == "__main__":
    seed_database()
    print("Database seeded successfully.")