from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class PatientIntakeRecord(BaseModel):
    patient_id: Optional[str] = None
    name: str
    age: Optional[int] = None
    concern: str
    duration: Optional[str] = None
    consent_memory: bool = False


class PatientMemoryRecord(BaseModel):
    patient_id: str
    previous_department: str
    previous_concern: str
    previous_explanation: str
    timestamp: str


class SafetyAssessment(BaseModel):
    status: Literal["URGENT", "UNCERTAIN", "CLEAR"]
    matched_rules: List[str] = Field(default_factory=list)
    advisory_message: str
    requires_immediate_care: bool


class RoutingDecision(BaseModel):
    department_id: str
    department_name: str
    routing_explanation: str
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    requires_human_review: bool = False


class RetrievedDocument(BaseModel):
    source_file: str
    department_id: str
    content_snippet: str


class DepartmentInformation(BaseModel):
    department_id: str
    instructions: List[str] = Field(default_factory=list)
    documents_to_bring: List[str] = Field(default_factory=list)
    location: str
    citations: List[RetrievedDocument] = Field(default_factory=list)


class AppointmentSlot(BaseModel):
    slot_id: str
    department_id: str
    provider_name: str
    date: str
    start_time: str
    end_time: str
    is_available: bool


class AgentExecutionEvent(BaseModel):
    agent_name: str
    status: Literal["COMPLETED", "STOPPED", "SKIPPED", "FAILED"]
    summary: str
    timestamp: str


class WorkflowState(BaseModel):
    run_id: str
    intake: Optional[PatientIntakeRecord] = None
    memory: Optional[PatientMemoryRecord] = None
    safety: Optional[SafetyAssessment] = None
    routing: Optional[RoutingDecision] = None
    department_info: Optional[DepartmentInformation] = None
    offered_slots: List[AppointmentSlot] = Field(default_factory=list)
    trace: List[AgentExecutionEvent] = Field(default_factory=list)
    final_response_text: str = ""
    disclaimer: str = (
        "This assistant is a non-clinical demonstration tool for hospital intake "
        "and department routing only. It does not provide medical advice or diagnosis."
    )