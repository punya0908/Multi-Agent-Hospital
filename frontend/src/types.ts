export interface IntakeRequestPayload {
  patient_id?: string | null;
  name: string;
  age?: number | null;
  concern: string;
  duration?: string | null;
  consent_memory: boolean;
}

export interface PatientIntakeRecord {
  patient_id?: string | null;
  name: string;
  age?: number | null;
  concern: string;
  duration?: string | null;
  consent_memory: boolean;
}

export interface PatientMemoryRecord {
  patient_id: string;
  previous_department: string;
  previous_concern: string;
  previous_explanation: string;
  timestamp: string;
}

export interface SafetyAssessment {
  status: "URGENT" | "UNCERTAIN" | "CLEAR";
  matched_rules: string[];
  advisory_message: string;
  requires_immediate_care: boolean;
}

export interface RoutingDecision {
  department_id: string;
  department_name: string;
  routing_explanation: string;
  confidence: "HIGH" | "MEDIUM" | "LOW";
  requires_human_review: boolean;
}

export interface RetrievedDocument {
  source_file: string;
  department_id: string;
  content_snippet: string;
}

export interface DepartmentInformation {
  department_id: string;
  instructions: string[];
  documents_to_bring: string[];
  location: string;
  citations: RetrievedDocument[];
}

export interface AppointmentSlot {
  slot_id: string;
  department_id: string;
  provider_name: string;
  date: string;
  start_time: string;
  end_time: string;
  is_available: boolean;
}

export interface AgentExecutionEvent {
  agent_name: string;
  status: "COMPLETED" | "STOPPED" | "SKIPPED" | "FAILED";
  summary: string;
  timestamp: string;
}

export interface WorkflowState {
  run_id: string;
  intake: PatientIntakeRecord | null;
  memory: PatientMemoryRecord | null;
  safety: SafetyAssessment | null;
  routing: RoutingDecision | null;
  department_info: DepartmentInformation | null;
  offered_slots: AppointmentSlot[];
  trace: AgentExecutionEvent[];
  final_response_text: string;
  disclaimer: string;
}

export interface AppointmentConfirmPayload {
  slot_id: string;
  patient_name: string;
  patient_id?: string | null;
  department_id: string;
  run_id?: string | null;
}

export interface AppointmentConfirmResponse {
  status: string;
  booking_reference: string;
  slot: AppointmentSlot;
  patient_name: string;
  patient_id?: string | null;
  department_id: string;
  email_status: string;
  recipient: string;
  email_preview?: string | null;
}

export interface VoiceTranscribeResponse {
  transcript: string;
  extracted_intake: PatientIntakeRecord;
  spoken_confirmation_prompt: string;
}

export interface BrowserSpeechRecognitionEvent {
  results: {
    length: number;
    [index: number]: {
      isFinal: boolean;
      [altIndex: number]: {
        transcript: string;
      };
    };
  };
}

export interface BrowserSpeechRecognition {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: BrowserSpeechRecognitionEvent) => void) | null;
  onerror: (() => void) | null;
  start: () => void;
  stop: () => void;
}