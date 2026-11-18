import type {
  AppointmentConfirmPayload,
  AppointmentConfirmResponse,
  IntakeRequestPayload,
  VoiceTranscribeResponse,
  WorkflowState,
} from "./types";

const API_BASE_URL = "http://localhost:8000/api";

export async function submitIntakeWorkflow(
  payload: IntakeRequestPayload
): Promise<WorkflowState> {
  const response = await fetch(`${API_BASE_URL}/intake`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errText = await response.text();
    throw new Error(errText || `Intake request failed (${response.status})`);
  }
  return response.json() as Promise<WorkflowState>;
}

export async function confirmAppointmentSlot(
  payload: AppointmentConfirmPayload
): Promise<AppointmentConfirmResponse> {
  const response = await fetch(`${API_BASE_URL}/appointments/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errText = await response.text();
    throw new Error(errText || `Appointment confirmation failed (${response.status})`);
  }
  return response.json() as Promise<AppointmentConfirmResponse>;
}

export async function transcribeVoiceIntake(params: {
  audioBlob?: Blob | null;
  transcriptFallback?: string;
  patientId?: string;
  consentMemory?: boolean;
}): Promise<VoiceTranscribeResponse> {
  if (params.audioBlob && params.audioBlob.size > 0) {
    const formData = new FormData();
    formData.append("file", params.audioBlob, "voice_intake.webm");
    if (params.patientId?.trim()) {
      formData.append("patient_id", params.patientId.trim());
    }
    formData.append("consent_memory", String(Boolean(params.consentMemory)));
    if (params.transcriptFallback?.trim()) {
      formData.append("transcript", params.transcriptFallback.trim());
    }

    const response = await fetch(`${API_BASE_URL}/voice/transcribe`, {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      throw new Error(await response.text());
    }
    return response.json() as Promise<VoiceTranscribeResponse>;
  }

  const response = await fetch(`${API_BASE_URL}/voice/transcribe`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      transcript: params.transcriptFallback || "",
      patient_id: params.patientId?.trim() || null,
      consent_memory: Boolean(params.consentMemory),
    }),
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<VoiceTranscribeResponse>;
}