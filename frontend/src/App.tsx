import {
  Activity,
  AlertTriangle,
  Calendar,
  CheckCircle2,
  Clock,
  Cpu,
  FileText,
  History,
  Lock,
  Mail,
  MapPin,
  Mic,
  MicOff,
  PhoneCall,
  Send,
  ShieldAlert,
  Sparkles,
  UserCheck,
  Volume2,
  VolumeX,
} from "lucide-react";
import { FormEvent, useRef, useState } from "react";
import {
  confirmAppointmentSlot,
  submitIntakeWorkflow,
  transcribeVoiceIntake,
} from "./api";
import type {
  AgentExecutionEvent,
  AppointmentConfirmResponse,
  AppointmentSlot,
  BrowserSpeechRecognition,
  WorkflowState,
} from "./types";

interface DemoPreset {
  badge: string;
  title: string;
  subtitle: string;
  patient_id: string;
  name: string;
  age: string;
  concern: string;
  duration: string;
  consent_memory: boolean;
}

const DEMO_PRESETS: DemoPreset[] = [
  {
    badge: "🟢 Normal Case",
    title: "Knee Pain ➔ Orthopaedics",
    subtitle: "Standard routing + FAISS RAG + SQLite slots",
    patient_id: "",
    name: "Riya Verma",
    age: "28",
    concern: "My right knee has been painful and stiff when climbing stairs.",
    duration: "4 days",
    consent_memory: false,
  },
  {
    badge: "🔴 Urgent Stop",
    title: "Crushing Chest Pain ➔ 112 Advisory",
    subtitle: "Mandatory Safety Gate blocks downstream agents",
    patient_id: "",
    name: "Karan Mehta",
    age: "54",
    concern:
      "I am having severe crushing chest pain radiating to my left arm and shortness of breath.",
    duration: "30 minutes",
    consent_memory: false,
  },
  {
    badge: "🟣 Returning P1001 + Consent",
    title: "Prior ENT ➔ New Skin Rash",
    subtitle: "Recalls ENT history without overriding DERM triage",
    patient_id: "P1001",
    name: "Aarav Sharma",
    age: "34",
    concern: "Itchy red skin rash on my forearms.",
    duration: "3 days",
    consent_memory: true,
  },
  {
    badge: "⚪ Returning P1001 No Consent",
    title: "Blurry Vision ➔ Ophthalmology",
    subtitle: "Privacy consent off; PatientMemoryAgent skipped",
    patient_id: "P1001",
    name: "Aarav Sharma",
    age: "34",
    concern: "Blurry vision and eye strain when reading.",
    duration: "1 week",
    consent_memory: false,
  },
];

function getPillClass(status: AgentExecutionEvent["status"]): string {
  switch (status) {
    case "COMPLETED":
      return "pill pill-emerald";
    case "STOPPED":
      return "pill pill-crimson";
    case "SKIPPED":
      return "pill pill-slate";
    case "FAILED":
      return "pill pill-amber";
  }
}

export default function App() {
  const [patientId, setPatientId] = useState("");
  const [name, setName] = useState("");
  const [age, setAge] = useState("");
  const [concern, setConcern] = useState("");
  const [duration, setDuration] = useState("");
  const [consentMemory, setConsentMemory] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [workflowState, setWorkflowState] = useState<WorkflowState | null>(null);
  const [bookingMap, setBookingMap] = useState<Record<string, AppointmentConfirmResponse>>({});
  const [bookingBusySlot, setBookingBusySlot] = useState<string | null>(null);

  // Voice Call Console State
  const [isListening, setIsListening] = useState(false);
  const [voiceProcessing, setVoiceProcessing] = useState(false);
  const [liveTranscript, setLiveTranscript] = useState("");
  const [ttsEnabled, setTtsEnabled] = useState(true);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const recognitionRef = useRef<BrowserSpeechRecognition | null>(null);
  const liveTranscriptRef = useRef<string>("");

  const speakText = (text: string) => {
    if (!ttsEnabled || typeof window === "undefined" || !("speechSynthesis" in window)) {
      return;
    }
    try {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.02;
      window.speechSynthesis.speak(utterance);
    } catch {
      // Ignore speech synthesis errors in restricted environments
    }
  };

  const announceWorkflowResult = (result: WorkflowState) => {
    if (result.safety?.status === "URGENT") {
      speakText(
        "Urgent warning signs detected. Automated routing has been stopped. Please seek immediate in-person emergency care or dial 112."
      );
    } else if (
      result.safety?.status === "UNCERTAIN" ||
      result.routing?.requires_human_review
    ) {
      speakText(
        "Automated routing has paused for safety review. Hospital intake staff will review your concern directly."
      );
    } else if (result.routing) {
      speakText(
        `Thank you. Based on your concern, I have routed you to ${result.routing.department_name}. Please select one of the available appointment slots on your screen to confirm your booking.`
      );
    }
  };

  const executeWorkflow = async (payload: {
    patient_id: string | null;
    name: string;
    age: number | null;
    concern: string;
    duration: string | null;
    consent_memory: boolean;
  }) => {
    setLoading(true);
    setError(null);
    setBookingMap({});
    try {
      const result = await submitIntakeWorkflow(payload);
      setWorkflowState(result);
      announceWorkflowResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run intake workflow.");
    } finally {
      setLoading(false);
    }
  };

  const applyPreset = (preset: DemoPreset) => {
    setPatientId(preset.patient_id);
    setName(preset.name);
    setAge(preset.age);
    setConcern(preset.concern);
    setDuration(preset.duration);
    setConsentMemory(preset.consent_memory);
    setError(null);
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !concern.trim()) {
      setError("Please enter both Full Name and Described Concern.");
      return;
    }
    const parsedAge = age.trim() ? Number.parseInt(age.trim(), 10) : null;
    await executeWorkflow({
      patient_id: patientId.trim() || null,
      name: name.trim(),
      age: parsedAge !== null && !Number.isNaN(parsedAge) ? parsedAge : null,
      concern: concern.trim(),
      duration: duration.trim() || null,
      consent_memory: consentMemory,
    });
  };

  const startVoiceCall = async () => {
    setError(null);
    setLiveTranscript("");
    liveTranscriptRef.current = "";
    audioChunksRef.current = [];

    const speechWindow = window as unknown as {
      SpeechRecognition?: new () => BrowserSpeechRecognition;
      webkitSpeechRecognition?: new () => BrowserSpeechRecognition;
    };
    const SpeechRecCtor =
      speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition;

    if (SpeechRecCtor) {
      try {
        const rec = new SpeechRecCtor();
        rec.continuous = true;
        rec.interimResults = true;
        rec.lang = "en-US";
        rec.onresult = (evt) => {
          let combined = "";
          for (let i = 0; i < evt.results.length; i += 1) {
            combined += `${evt.results[i][0].transcript} `;
          }
          const clean = combined.trim();
          liveTranscriptRef.current = clean;
          setLiveTranscript(clean);
        };
        rec.onerror = () => {
          // SpeechRecognition fallback silently handled by MediaRecorder + Whisper
        };
        rec.start();
        recognitionRef.current = rec;
      } catch {
        recognitionRef.current = null;
      }
    }

    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const recorder = new MediaRecorder(stream);
        recorder.ondataavailable = (ev) => {
          if (ev.data.size > 0) {
            audioChunksRef.current.push(ev.data);
          }
        };
        recorder.onstop = async () => {
          stream.getTracks().forEach((t) => t.stop());
          const blob = new Blob(audioChunksRef.current, { type: "audio/webm" });
          await finalizeVoiceCall(blob);
        };
        recorder.start();
        mediaRecorderRef.current = recorder;
        setIsListening(true);
        return;
      } catch {
        // Fall through to browser speech / transcript simulation
      }
    }

    if (recognitionRef.current) {
      setIsListening(true);
    } else {
      setError(
        "Microphone capture is unavailable in this browser. Type your concern in the form or select a quick scenario."
      );
    }
  };

  const stopVoiceCall = async () => {
    setIsListening(false);
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // Ignore stop errors
      }
      recognitionRef.current = null;
    }

    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current = null;
    } else {
      await finalizeVoiceCall(null);
    }
  };

  const finalizeVoiceCall = async (audioBlob: Blob | null) => {
    const fallbackText = liveTranscriptRef.current || concern;
    if (!audioBlob && !fallbackText.trim()) {
      return;
    }

    setVoiceProcessing(true);
    setError(null);
    try {
      const res = await transcribeVoiceIntake({
        audioBlob,
        transcriptFallback: fallbackText,
        patientId,
        consentMemory,
      });

      setLiveTranscript(res.transcript);
      const extracted = res.extracted_intake;
      const finalName = extracted.name || name || "Voice Caller";
      const finalConcern = extracted.concern || res.transcript;

      setName(finalName);
      if (extracted.age !== null && extracted.age !== undefined) {
        setAge(String(extracted.age));
      }
      setConcern(finalConcern);
      if (extracted.duration) {
        setDuration(extracted.duration);
      }

      await executeWorkflow({
        patient_id: patientId.trim() || null,
        name: finalName,
        age: extracted.age ?? (age.trim() ? Number.parseInt(age.trim(), 10) : null),
        concern: finalConcern,
        duration: extracted.duration || (duration.trim() || null),
        consent_memory: consentMemory,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Voice transcription failed.");
    } finally {
      setVoiceProcessing(false);
    }
  };

  const handleConfirmSlot = async (slot: AppointmentSlot) => {
    if (!workflowState || !workflowState.routing) return;
    setBookingBusySlot(slot.slot_id);
    setError(null);

    try {
      const confirmation = await confirmAppointmentSlot({
        slot_id: slot.slot_id,
        patient_name: workflowState.intake?.name || name || "Patient",
        patient_id: workflowState.intake?.patient_id || null,
        department_id: workflowState.routing.department_id,
        run_id: workflowState.run_id,
      });

      setBookingMap((prev) => ({ ...prev, [slot.slot_id]: confirmation }));
      setWorkflowState((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          offered_slots: prev.offered_slots.map((s) =>
            s.slot_id === slot.slot_id ? { ...s, is_available: false } : s
          ),
        };
      });

      speakText(
        `Your appointment with ${confirmation.slot.provider_name} is confirmed. A confirmation email has been sent to your Gmail.`
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to confirm slot.");
    } finally {
      setBookingBusySlot(null);
    }
  };

  const isUrgent = workflowState?.safety?.status === "URGENT";
  const isHumanEscalation =
    workflowState !== null &&
    !isUrgent &&
    (workflowState.safety?.status === "UNCERTAIN" ||
      workflowState.routing?.requires_human_review === true);
  const isClearRouted =
    workflowState !== null &&
    workflowState.safety?.status === "CLEAR" &&
    workflowState.routing !== null &&
    !workflowState.routing.requires_human_review;

  const traceEvents = workflowState?.trace || [];
  const parallelAgents = new Set(["InformationAgent", "AppointmentAgent"]);
  const parallelEvents = traceEvents.filter((e) => parallelAgents.has(e.agent_name));
  const nonParallelEvents = traceEvents.filter((e) => !parallelAgents.has(e.agent_name));

  return (
    <div className="cmd-shell">
      {/* Header & Live Telemetry */}
      <header className="cmd-header">
        <div className="brand-wrap">
          <div className="brand-icon">
            <Activity size={24} />
          </div>
          <div>
            <h1 className="brand-title">
              AegisHealth AI — Multi-Agent Intake &amp; Triage Command Center
            </h1>
            <p className="brand-sub">
              Hierarchical Supervisor • Deterministic Safety Gate • Non-Diagnostic Hospital Routing
            </p>
          </div>
        </div>

        <div className="telemetry-bar">
          <span className="telemetry-pill">⚡ Groq Llama-3.3 + Whisper</span>
          <span className="telemetry-pill">📚 FAISS Vector RAG</span>
          <span className="telemetry-pill">🗄️ SQLite Memory</span>
          <span className="telemetry-pill armed">
            <ShieldAlert size={14} /> Safety Gate Armed
          </span>
        </div>
      </header>

      {/* 4 One-Click Demo Scenario Cards */}
      <section className="scenario-grid">
        {DEMO_PRESETS.map((preset) => (
          <button
            key={preset.title}
            type="button"
            className="scenario-card"
            onClick={() => applyPreset(preset)}
          >
            <div className="scenario-title">{preset.badge}</div>
            <div style={{ fontSize: "0.86rem", fontWeight: 700, marginBottom: 3 }}>
              {preset.title}
            </div>
            <div className="scenario-desc">{preset.subtitle}</div>
          </button>
        ))}
      </section>

      {/* 3-Column Bento Grid */}
      <main className="bento-grid">
        {/* LEFT COLUMN: Voice Console + Patient Intake Form */}
        <section className="glass-panel">
          <div className="panel-header">
            <h2>
              <PhoneCall size={18} color="#a78bfa" /> Automated Hospital Call Console
            </h2>
          </div>

          <div className="voice-console">
            <div className="voice-top-row">
              <span className="voice-badge">
                <Sparkles size={12} /> Groq Whisper-Large-v3-Turbo
              </span>
              <button
                type="button"
                className="tts-toggle-btn"
                style={{ marginTop: 0 }}
                onClick={() => setTtsEnabled((v) => !v)}
              >
                {ttsEnabled ? <Volume2 size={14} /> : <VolumeX size={14} />}
                {ttsEnabled ? "Voice Receptionist (TTS): ON" : "TTS: OFF"}
              </button>
            </div>

            <div className="voice-disclaimer">
              Non-Emergency Automated Intake Call — For Emergencies Dial 112
            </div>

            <button
              type="button"
              className={`call-btn ${isListening ? "active" : ""}`}
              disabled={voiceProcessing}
              onClick={isListening ? stopVoiceCall : startVoiceCall}
            >
              {isListening ? <MicOff size={18} /> : <Mic size={18} />}
              {voiceProcessing
                ? "Transcribing & Extracting Fields..."
                : isListening
                ? "Stop & Process Voice Intake"
                : "Start Voice Intake Call / Speak Your Concern"}
            </button>

            {isListening && (
              <div className="waveform" aria-label="Listening waveform">
                <div className="wave-bar" />
                <div className="wave-bar" />
                <div className="wave-bar" />
                <div className="wave-bar" />
                <div className="wave-bar" />
                <div className="wave-bar" />
              </div>
            )}

            {liveTranscript && (
              <div className="transcript-box">
                <strong style={{ color: "#c4b5fd" }}>Live Transcript:</strong>{" "}
                {liveTranscript}
              </div>
            )}
          </div>

          <div className="panel-header">
            <h2>
              <UserCheck size={18} color="#34d399" /> Structured Patient Intake
            </h2>
          </div>

          <form onSubmit={handleSubmit}>
            <div className="field">
              <label htmlFor="patientId">Patient ID (optional, e.g., P1001)</label>
              <input
                id="patientId"
                type="text"
                value={patientId}
                onChange={(e) => setPatientId(e.target.value)}
                placeholder="Leave blank for new patient"
              />
            </div>

            <div className="field-row">
              <div className="field">
                <label htmlFor="fullName">Full Name *</label>
                <input
                  id="fullName"
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Riya Verma"
                  required
                />
              </div>

              <div className="field">
                <label htmlFor="age">Age</label>
                <input
                  id="age"
                  type="number"
                  min={0}
                  max={120}
                  value={age}
                  onChange={(e) => setAge(e.target.value)}
                  placeholder="28"
                />
              </div>
            </div>

            <div className="field">
              <label htmlFor="concern">Described Concern *</label>
              <textarea
                id="concern"
                value={concern}
                onChange={(e) => setConcern(e.target.value)}
                placeholder="Describe current symptoms or reason for visit..."
                required
              />
            </div>

            <div className="field">
              <label htmlFor="duration">Duration of Concern</label>
              <input
                id="duration"
                type="text"
                value={duration}
                onChange={(e) => setDuration(e.target.value)}
                placeholder="e.g., 4 days"
              />
            </div>

            <label className="toggle-row">
              <span className="toggle-text">
                Consent to store &amp; recall prior hospital routing history
              </span>
              <span className="switch">
                <input
                  type="checkbox"
                  checked={consentMemory}
                  onChange={(e) => setConsentMemory(e.target.checked)}
                />
                <span className="slider" />
              </span>
            </label>

            <button type="submit" className="primary-btn" disabled={loading}>
              <Send size={16} />
              {loading ? "Executing Multi-Agent Graph..." : "Run Multi-Agent Intake Workflow"}
            </button>
          </form>
        </section>

        {/* CENTER COLUMN: Triage Decision, RAG Instructions & Gmail Booking */}
        <section className="glass-panel">
          <div className="panel-header">
            <h2>
              <Cpu size={18} color="#6ee7b7" /> Clinical Intake Routing &amp; Booking Hub
            </h2>
            {workflowState?.safety && (
              <span
                className={
                  workflowState.safety.status === "CLEAR"
                    ? "pill pill-emerald"
                    : workflowState.safety.status === "URGENT"
                    ? "pill pill-crimson"
                    : "pill pill-amber"
                }
              >
                Safety: {workflowState.safety.status}
              </span>
            )}
          </div>

          {error && <div className="error-alert">{error}</div>}

          {!workflowState && !loading && (
            <div className="empty-center">
              Select a Quick Demo Scenario card above, speak into the Automated Hospital Call
              Console, or submit the Structured Patient Intake form.
            </div>
          )}

          {loading && (
            <div className="empty-center">
              Orchestrating Intake, Patient Memory, Safety Gate, Triage Router, Parallel FAISS RAG
              + SQLite Slots, and Response Aggregator...
            </div>
          )}

          {workflowState && (
            <>
              {/* Urgent Emergency Stop Card */}
              {isUrgent && workflowState.safety && (
                <div className="result-card urgent-glow">
                  <h3 style={{ color: "#fda4af" }}>
                    <ShieldAlert size={20} /> URGENT SAFETY STOP — IMMEDIATE CARE ADVISED (112)
                  </h3>
                  <p style={{ margin: "6px 0" }}>{workflowState.safety.advisory_message}</p>
                  <p style={{ margin: "6px 0", fontSize: "0.88rem" }}>
                    <strong>Action Required:</strong> Do NOT wait for a routine outpatient
                    appointment. Go to the nearest Emergency Department or dial <strong>112</strong>{" "}
                    immediately.
                  </p>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 10 }}>
                    {workflowState.safety.matched_rules.map((rule) => (
                      <span key={rule} className="pill pill-crimson">
                        Rule: {rule}
                      </span>
                    ))}
                    <span className="pill pill-crimson">
                      <Lock size={12} /> Downstream Routing &amp; Booking Blocked
                    </span>
                  </div>
                </div>
              )}

              {/* Amber Escalation Card */}
              {isHumanEscalation && (
                <div className="result-card amber-glow">
                  <h3 style={{ color: "#fcd34d" }}>
                    <AlertTriangle size={20} /> Human Triage Review Escalation
                  </h3>
                  <p style={{ margin: "6px 0", fontSize: "0.9rem" }}>
                    Automated routing has paused so hospital intake staff can evaluate this concern
                    directly.
                  </p>
                  {workflowState.safety?.advisory_message && (
                    <p style={{ margin: 0, fontSize: "0.84rem", color: "#fde68a" }}>
                      {workflowState.safety.advisory_message}
                    </p>
                  )}
                </div>
              )}

              {/* CLEAR Path Cards */}
              {isClearRouted && workflowState.routing && (
                <>
                  {workflowState.memory && (
                    <div className="result-card violet-glow">
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          gap: 8,
                          flexWrap: "wrap",
                        }}
                      >
                        <h3 style={{ margin: 0, color: "#ddd6fe" }}>
                          <History size={18} /> Returning Patient History
                        </h3>
                        <span className="pill pill-violet">
                          Historical Context Only — Did Not Override Current Triage
                        </span>
                      </div>
                      <p style={{ margin: "8px 0 4px", fontSize: "0.88rem" }}>
                        <strong>Previous Department:</strong> {workflowState.memory.previous_department}
                        {" • "}
                        <strong>Prior Concern:</strong> {workflowState.memory.previous_concern}
                      </p>
                      <p style={{ margin: 0, fontSize: "0.78rem", color: "var(--text-muted)" }}>
                        {workflowState.memory.previous_explanation} ({workflowState.memory.timestamp})
                      </p>
                    </div>
                  )}

                  {/* Routed Department Hero Card */}
                  <div className="result-card emerald-glow">
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        gap: 8,
                        flexWrap: "wrap",
                      }}
                    >
                      <h3 style={{ margin: 0, color: "#6ee7b7" }}>
                        <CheckCircle2 size={19} /> {workflowState.routing.department_name} (
                        {workflowState.routing.department_id})
                      </h3>
                      <span className="pill pill-emerald">
                        Confidence: {workflowState.routing.confidence}
                      </span>
                    </div>
                    <p style={{ margin: "8px 0 0", fontSize: "0.9rem", color: "#e2e8f0" }}>
                      {workflowState.routing.routing_explanation}
                    </p>
                  </div>

                  {/* FAISS RAG Grounded Instructions Card */}
                  {workflowState.department_info && (
                    <div className="result-card">
                      <h3>
                        <FileText size={18} color="#818cf8" /> FAISS RAG Grounded Preparation
                      </h3>
                      <div style={{ marginBottom: 10 }}>
                        <span className="pill pill-violet">
                          <MapPin size={12} /> {workflowState.department_info.location}
                        </span>
                      </div>

                      {workflowState.department_info.instructions.length > 0 && (
                        <>
                          <strong style={{ fontSize: "0.82rem", color: "#cbd5e1" }}>
                            Preparation &amp; Check-In Steps:
                          </strong>
                          <ul className="dark-list">
                            {workflowState.department_info.instructions.map((item, idx) => (
                              <li key={idx}>{item}</li>
                            ))}
                          </ul>
                        </>
                      )}

                      {workflowState.department_info.documents_to_bring.length > 0 && (
                        <>
                          <strong style={{ fontSize: "0.82rem", color: "#cbd5e1" }}>
                            Documents to Bring:
                          </strong>
                          <ul className="dark-list">
                            {workflowState.department_info.documents_to_bring.map((item, idx) => (
                              <li key={idx}>{item}</li>
                            ))}
                          </ul>
                        </>
                      )}

                      {workflowState.department_info.citations.length > 0 && (
                        <div className="citation-row">
                          {Array.from(
                            new Set(
                              workflowState.department_info.citations.map((c) => c.source_file)
                            )
                          ).map((file) => (
                            <span key={file} className="citation-chip">
                              📄 {file}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Available Slots & Boarding Pass */}
                  <div className="result-card">
                    <h3>
                      <Calendar size={18} color="#34d399" /> Available Appointment Slots
                    </h3>
                    {workflowState.offered_slots.length === 0 ? (
                      <p style={{ margin: 0, fontSize: "0.86rem", color: "var(--text-muted)" }}>
                        No open appointment slots available right now.
                      </p>
                    ) : (
                      workflowState.offered_slots.map((slot) => {
                        const confirmed = bookingMap[slot.slot_id];
                        return (
                          <div key={slot.slot_id}>
                            <div className="slot-card">
                              <div style={{ fontSize: "0.85rem" }}>
                                <strong>{slot.provider_name}</strong>{" "}
                                <span style={{ color: "var(--text-muted)" }}>({slot.slot_id})</span>
                                <div style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>
                                  {slot.date} • {slot.start_time} – {slot.end_time}
                                </div>
                              </div>

                              {confirmed ? (
                                <span className="pill pill-emerald">
                                  Confirmed • {confirmed.booking_reference}
                                </span>
                              ) : (
                                <button
                                  type="button"
                                  className="slot-btn"
                                  disabled={!slot.is_available || bookingBusySlot === slot.slot_id}
                                  onClick={() => handleConfirmSlot(slot)}
                                >
                                  <Mail size={13} />
                                  {bookingBusySlot === slot.slot_id
                                    ? "Confirming..."
                                    : slot.is_available
                                    ? "Confirm & Notify Gmail"
                                    : "Booked"}
                                </button>
                              )}
                            </div>

                            {confirmed && (
                              <div className="boarding-pass">
                                <div
                                  style={{
                                    display: "flex",
                                    justifyContent: "space-between",
                                    alignItems: "center",
                                    gap: 8,
                                    flexWrap: "wrap",
                                    marginBottom: 6,
                                  }}
                                >
                                  <strong style={{ color: "#6ee7b7" }}>
                                    🎫 CONFIRMED APPOINTMENT TICKET • {confirmed.booking_reference}
                                  </strong>
                                  <span className="pill pill-emerald">
                                    <Mail size={12} /> {confirmed.email_status} ({confirmed.recipient})
                                  </span>
                                </div>
                                <div style={{ color: "#e2e8f0", fontSize: "0.8rem" }}>
                                  Patient: <strong>{confirmed.patient_name}</strong> • Provider:{" "}
                                  <strong>{confirmed.slot.provider_name}</strong> •{" "}
                                  {confirmed.slot.date} ({confirmed.slot.start_time}–
                                  {confirmed.slot.end_time})
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      })
                    )}
                  </div>
                </>
              )}

              <div className="disclaimer-box">{workflowState.disclaimer}</div>
            </>
          )}
        </section>

        {/* RIGHT COLUMN: Visual Multi-Agent Pipeline Graph */}
        <section className="glass-panel">
          <div className="panel-header">
            <h2>
              <Clock size={18} color="#a78bfa" /> Visual Multi-Agent Pipeline
            </h2>
          </div>

          {!workflowState ? (
            <div className="empty-center">
              Execute a workflow to inspect the live hierarchical execution graph across all 7
              agents (`IntakeAgent` ➔ `PatientMemoryAgent` ➔ `SafetyGateAgent` ➔
              `TriageRouterAgent` ➔ Parallel Fan-Out ➔ `ResponseAggregator`).
            </div>
          ) : (
            <div className="pipeline-graph">
              <div style={{ fontSize: "0.74rem", color: "var(--text-muted)", marginBottom: 12 }}>
                Run ID: <code>{workflowState.run_id}</code>
              </div>

              {nonParallelEvents
                .filter((e) => e.agent_name !== "ResponseAggregator")
                .map((event, idx) => (
                  <div key={`${event.agent_name}-${idx}`} className="pipeline-node-wrap">
                    <div className={`pipeline-dot dot-${event.status}`} />
                    <div className="node-card">
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          gap: 8,
                        }}
                      >
                        <strong style={{ fontSize: "0.84rem" }}>{event.agent_name}</strong>
                        <span className={getPillClass(event.status)}>{event.status}</span>
                      </div>
                      <div style={{ fontSize: "0.79rem", color: "#cbd5e1", marginTop: 5 }}>
                        {event.summary}
                      </div>
                      <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginTop: 4 }}>
                        {event.timestamp}
                      </div>
                    </div>
                  </div>
                ))}

              {parallelEvents.length > 0 && (
                <div className="fanout-box">
                  <div className="fanout-label">Parallel Fan-Out (asyncio.gather)</div>
                  {parallelEvents.map((event, idx) => (
                    <div
                      key={`${event.agent_name}-${idx}`}
                      className="node-card"
                      style={{ marginBottom: idx === 0 ? 8 : 0 }}
                    >
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          gap: 8,
                        }}
                      >
                        <strong style={{ fontSize: "0.82rem" }}>{event.agent_name}</strong>
                        <span className={getPillClass(event.status)}>{event.status}</span>
                      </div>
                      <div style={{ fontSize: "0.78rem", color: "#cbd5e1", marginTop: 4 }}>
                        {event.summary}
                      </div>
                      <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", marginTop: 3 }}>
                        {event.timestamp}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {nonParallelEvents
                .filter((e) => e.agent_name === "ResponseAggregator")
                .map((event, idx) => (
                  <div key={`${event.agent_name}-${idx}`} className="pipeline-node-wrap">
                    <div className={`pipeline-dot dot-${event.status}`} />
                    <div className="node-card">
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          gap: 8,
                        }}
                      >
                        <strong style={{ fontSize: "0.84rem" }}>{event.agent_name}</strong>
                        <span className={getPillClass(event.status)}>{event.status}</span>
                      </div>
                      <div style={{ fontSize: "0.79rem", color: "#cbd5e1", marginTop: 5 }}>
                        {event.summary}
                      </div>
                      <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginTop: 4 }}>
                        {event.timestamp}
                      </div>
                    </div>
                  </div>
                ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}