from typing import List, Optional

from backend.schemas.workflow_state import AppointmentSlot, RoutingDecision
from backend.services.appointment_service import AppointmentService


class AppointmentAgent:
    def __init__(
        self, appointment_service: Optional[AppointmentService] = None
    ) -> None:
        self.appointment_service = appointment_service or AppointmentService()

    async def arun(self, routing: RoutingDecision) -> List[AppointmentSlot]:
        return self.run(routing)

    def run(self, routing: RoutingDecision) -> List[AppointmentSlot]:
        return self.appointment_service.get_available_slots(routing.department_id)