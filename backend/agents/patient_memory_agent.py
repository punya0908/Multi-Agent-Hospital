from typing import Optional

from backend.schemas.workflow_state import PatientIntakeRecord, PatientMemoryRecord
from backend.services.patient_memory_service import PatientMemoryService


class PatientMemoryAgent:
    def __init__(
        self, memory_service: Optional[PatientMemoryService] = None
    ) -> None:
        self.memory_service = memory_service or PatientMemoryService()

    async def arun(
        self, intake: PatientIntakeRecord
    ) -> Optional[PatientMemoryRecord]:
        return self.run(intake)

    def run(self, intake: PatientIntakeRecord) -> Optional[PatientMemoryRecord]:
        if not intake.patient_id or not intake.consent_memory:
            return None
        return self.memory_service.get_patient_history(
            patient_id=intake.patient_id,
            consent=intake.consent_memory,
        )