import urllib.parse
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape as xml_escape

import yaml
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import delete

from backend.config.settings import settings
from backend.database.db import PatientHistoryModel, SessionLocal, init_db
from backend.database.seed import seed_database
from backend.schemas.workflow_state import (
    AgentExecutionEvent,
    AppointmentSlot,
    PatientIntakeRecord,
    PatientMemoryRecord,
    WorkflowState,
)
from backend.services.appointment_service import AppointmentService
from backend.services.email_service import send_booking_confirmation_email
from backend.services.patient_memory_service import PatientMemoryService
from backend.services.voice_service import VoiceService
from backend.workflows.hospital_workflow import run_intake_workflow

WORKFLOW_RUNS: Dict[str, WorkflowState] = {}

appointment_service = AppointmentService()
patient_memory_service = PatientMemoryService()
voice_service = VoiceService()


def _load_department_map() -> Dict[str, str]:
    with open(settings.DEPARTMENTS_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return {
        d["id"]: d["name"]
        for d in data.get("departments", [])
        if "id" in d and "name" in d
    }


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    seed_database()
    yield


app = FastAPI(
    title="AegisHealth AI — Hospital Patient Intake & Department Routing API",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class IntakeRequest(BaseModel):
    patient_id: Optional[str] = None
    name: str
    age: Optional[int] = None
    concern: str
    duration: Optional[str] = None
    consent_memory: bool = False


class AppointmentConfirmRequest(BaseModel):
    slot_id: str
    patient_name: str
    patient_id: Optional[str] = None
    department_id: str
    run_id: Optional[str] = None


class AppointmentConfirmResponse(BaseModel):
    status: str
    booking_reference: str
    slot: AppointmentSlot
    patient_name: str
    patient_id: Optional[str] = None
    department_id: str
    email_status: str
    recipient: str
    email_preview: Optional[str] = None


class PatientHistoryResponse(BaseModel):
    patient_id: str
    consent: bool
    history: Optional[PatientMemoryRecord] = None


class WorkflowTraceResponse(BaseModel):
    run_id: str
    trace: List[AgentExecutionEvent]


class VoiceTranscribeResponse(BaseModel):
    transcript: str
    extracted_intake: PatientIntakeRecord
    spoken_confirmation_prompt: str


@app.get("/api/health")
def health_check() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/departments")
def list_departments() -> Dict[str, List[Dict[str, Any]]]:
    with open(settings.DEPARTMENTS_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return {"departments": data.get("departments", [])}


@app.get("/api/patients/{patient_id}/history", response_model=PatientHistoryResponse)
def get_patient_history(
    patient_id: str,
    consent: bool = Query(default=False),
) -> PatientHistoryResponse:
    history = patient_memory_service.get_patient_history(
        patient_id=patient_id,
        consent=consent,
    )
    return PatientHistoryResponse(
        patient_id=patient_id,
        consent=consent,
        history=history,
    )


@app.post("/api/intake", response_model=WorkflowState)
async def submit_intake(payload: IntakeRequest) -> WorkflowState:
    clean_patient_id = (
        payload.patient_id.strip() if payload.patient_id and payload.patient_id.strip() else None
    )
    clean_duration = (
        payload.duration.strip() if payload.duration and payload.duration.strip() else None
    )

    state = await run_intake_workflow(
        raw_input={
            "patient_id": clean_patient_id,
            "name": payload.name.strip(),
            "age": payload.age,
            "concern": payload.concern.strip(),
            "duration": clean_duration,
            "consent_memory": payload.consent_memory,
        },
        patient_id=clean_patient_id,
        name=payload.name.strip(),
        age=payload.age,
        duration=clean_duration,
        consent_memory=payload.consent_memory,
    )
    WORKFLOW_RUNS[state.run_id] = state
    return state


@app.get("/api/intake/{run_id}/trace", response_model=WorkflowTraceResponse)
def get_workflow_trace(run_id: str) -> WorkflowTraceResponse:
    state = WORKFLOW_RUNS.get(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Workflow run not found.")
    return WorkflowTraceResponse(run_id=run_id, trace=state.trace)


@app.post("/api/appointments/confirm", response_model=AppointmentConfirmResponse)
def confirm_appointment(
    payload: AppointmentConfirmRequest,
) -> AppointmentConfirmResponse:
    confirmed_slot = appointment_service.confirm_slot(payload.slot_id)
    if confirmed_slot is None:
        raise HTTPException(
            status_code=409,
            detail=f"Appointment slot '{payload.slot_id}' was not found or is already booked.",
        )

    if payload.run_id and payload.run_id in WORKFLOW_RUNS:
        run_state = WORKFLOW_RUNS[payload.run_id]
        for s in run_state.offered_slots:
            if s.slot_id == confirmed_slot.slot_id:
                s.is_available = False

    booking_ref = f"BK-{uuid.uuid4().hex[:6].upper()}"
    dept_map = _load_department_map()
    department_name = dept_map.get(payload.department_id, payload.department_id)

    email_result = send_booking_confirmation_email(
        booking_reference=booking_ref,
        patient_name=payload.patient_name,
        department_id=payload.department_id,
        department_name=department_name,
        provider_name=confirmed_slot.provider_name,
        date=confirmed_slot.date,
        start_time=confirmed_slot.start_time,
        end_time=confirmed_slot.end_time,
        run_id=payload.run_id,
    )

    return AppointmentConfirmResponse(
        status="CONFIRMED",
        booking_reference=booking_ref,
        slot=confirmed_slot,
        patient_name=payload.patient_name,
        patient_id=payload.patient_id,
        department_id=payload.department_id,
        email_status=email_result["email_status"],
        recipient=email_result["recipient"],
        email_preview=email_result.get("preview"),
    )


@app.delete("/api/patients/{patient_id}/memory")
def delete_patient_memory(patient_id: str) -> Dict[str, Any]:
    with SessionLocal() as session:
        with session.begin():
            result = session.execute(
                delete(PatientHistoryModel).where(
                    PatientHistoryModel.patient_id == patient_id
                )
            )
            deleted_count = result.rowcount or 0
    return {
        "status": "DELETED",
        "patient_id": patient_id,
        "deleted_records": deleted_count,
    }


@app.post("/api/voice/transcribe", response_model=VoiceTranscribeResponse)
async def transcribe_voice_intake(request: Request) -> VoiceTranscribeResponse:
    content_type = (request.headers.get("content-type") or "").lower()
    audio_bytes: Optional[bytes] = None
    filename = "voice_intake.webm"
    patient_id: Optional[str] = None
    consent_memory = False
    transcript_fallback: Optional[str] = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        upload = form.get("file") or form.get("audio")
        if upload is not None and hasattr(upload, "read"):
            audio_bytes = await upload.read()
            filename = getattr(upload, "filename", None) or filename
        raw_pid = form.get("patient_id")
        patient_id = str(raw_pid).strip() or None if raw_pid else None
        consent_memory = str(form.get("consent_memory", "false")).lower() == "true"
        raw_fallback = form.get("transcript") or form.get("transcript_fallback")
        transcript_fallback = str(raw_fallback).strip() if raw_fallback else None
    else:
        try:
            body = await request.json()
        except Exception:
            body = {}
        if isinstance(body, dict):
            transcript_fallback = body.get("transcript") or body.get("text")
            raw_pid = body.get("patient_id")
            patient_id = str(raw_pid).strip() or None if raw_pid else None
            consent_memory = bool(body.get("consent_memory", False))

    result = await voice_service.process_voice_intake(
        audio_bytes=audio_bytes,
        filename=filename,
        patient_id=patient_id,
        consent_memory=consent_memory,
        transcript_fallback=transcript_fallback,
    )
    return VoiceTranscribeResponse(**result)


@app.post("/api/twilio/voice")
async def twilio_voice_webhook(request: Request) -> Response:
    speech_result = ""
    caller = "Voice Caller"

    try:
        form = await request.form()
        speech_result = str(form.get("SpeechResult") or "").strip()
        if form.get("Caller"):
            caller = f"Caller {form.get('Caller')}"
    except Exception:
        raw_body = (await request.body()).decode("utf-8", errors="ignore")
        parsed = urllib.parse.parse_qs(raw_body)
        speech_result = (parsed.get("SpeechResult") or [""])[0].strip()
        if parsed.get("Caller"):
            caller = f"Caller {parsed['Caller'][0]}"

    if not speech_result:
        twiml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Response><Say>No speech input was detected. Please describe your symptoms after the tone or dial 112 for emergencies.</Say></Response>"
        )
        return Response(content=twiml, media_type="application/xml")

    state = await run_intake_workflow(
        raw_input=speech_result,
        name=caller,
        consent_memory=False,
    )
    WORKFLOW_RUNS[state.run_id] = state

    if state.safety and state.safety.status == "URGENT":
        spoken = (
            "Urgent safety warning detected. Do not wait for a routine appointment. "
            "Please seek immediate in-person emergency care or dial 112 right away."
        )
    elif (
        (state.safety and state.safety.status == "UNCERTAIN")
        or (state.routing and state.routing.requires_human_review)
    ):
        spoken = (
            "Automated routing has paused for safety review. "
            "A hospital intake staff member will review your concern directly."
        )
    elif state.routing:
        dept_name = state.routing.department_name
        if state.offered_slots:
            first_slot = state.offered_slots[0]
            spoken = (
                f"Thank you. Based on your concern, you have been routed to {dept_name}. "
                f"The next available slot is with {first_slot.provider_name} on {first_slot.date} "
                f"at {first_slot.start_time}. This is not a medical diagnosis."
            )
        else:
            spoken = (
                f"Thank you. Based on your concern, you have been routed to {dept_name}. "
                "Please speak with reception for upcoming slot availability."
            )
    else:
        spoken = "Thank you for calling AegisHealth. Please hold for a hospital intake coordinator."

    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f"<Response><Say>{xml_escape(spoken)}</Say></Response>"
    )
    return Response(content=twiml, media_type="application/xml")