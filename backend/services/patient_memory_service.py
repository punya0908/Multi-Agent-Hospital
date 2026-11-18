from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select

from backend.database.db import PatientHistoryModel, SessionLocal
from backend.schemas.workflow_state import PatientMemoryRecord


class PatientMemoryService:
    def __init__(self, session_factory=SessionLocal) -> None:
        self.session_factory = session_factory

    def get_patient_history(
        self, patient_id: str, consent: bool
    ) -> Optional[PatientMemoryRecord]:
        if not consent or not patient_id:
            return None

        with self.session_factory() as session:
            stmt = (
                select(PatientHistoryModel)
                .where(
                    PatientHistoryModel.patient_id == patient_id,
                    PatientHistoryModel.consent_given.is_(True),
                )
                .order_by(PatientHistoryModel.id.desc())
            )
            row = session.scalars(stmt).first()
            if row is None:
                return None

            return PatientMemoryRecord(
                patient_id=row.patient_id,
                previous_department=row.routed_department,
                previous_concern=row.concern_summary,
                previous_explanation=row.routing_explanation,
                timestamp=row.created_at,
            )

    def save_patient_history(
        self,
        patient_id: str,
        name: str,
        consent: bool,
        routed_department: str,
        concern_summary: str,
        routing_explanation: str,
    ) -> Optional[PatientMemoryRecord]:
        if not consent or not patient_id:
            return None

        created_at = datetime.now(timezone.utc).isoformat()
        with self.session_factory() as session:
            with session.begin():
                record = PatientHistoryModel(
                    patient_id=patient_id,
                    name=name,
                    consent_given=True,
                    routed_department=routed_department,
                    concern_summary=concern_summary,
                    routing_explanation=routing_explanation,
                    created_at=created_at,
                )
                session.add(record)

        return PatientMemoryRecord(
            patient_id=patient_id,
            previous_department=routed_department,
            previous_concern=concern_summary,
            previous_explanation=routing_explanation,
            timestamp=created_at,
        )