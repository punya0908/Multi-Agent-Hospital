from typing import List, Optional
from sqlalchemy import select

from backend.database.db import AppointmentSlotModel, SessionLocal
from backend.schemas.workflow_state import AppointmentSlot


class AppointmentService:
    def __init__(self, session_factory=SessionLocal) -> None:
        self.session_factory = session_factory

    @staticmethod
    def _to_schema(row: AppointmentSlotModel) -> AppointmentSlot:
        return AppointmentSlot(
            slot_id=row.slot_id,
            department_id=row.department_id,
            provider_name=row.provider_name,
            date=row.date,
            start_time=row.start_time,
            end_time=row.end_time,
            is_available=row.is_available,
        )

    def get_available_slots(self, department_id: str) -> List[AppointmentSlot]:
        with self.session_factory() as session:
            stmt = (
                select(AppointmentSlotModel)
                .where(
                    AppointmentSlotModel.department_id == department_id,
                    AppointmentSlotModel.is_available.is_(True),
                )
                .order_by(AppointmentSlotModel.date, AppointmentSlotModel.start_time)
            )
            rows = session.scalars(stmt).all()
            return [self._to_schema(row) for row in rows]

    def confirm_slot(self, slot_id: str) -> Optional[AppointmentSlot]:
        with self.session_factory() as session:
            with session.begin():
                stmt = select(AppointmentSlotModel).where(
                    AppointmentSlotModel.slot_id == slot_id
                )
                row = session.scalars(stmt).first()
                if row is None or not row.is_available:
                    return None
                row.is_available = False
                session.flush()
                return self._to_schema(row)