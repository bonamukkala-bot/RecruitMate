import { useState, useEffect, useRef, useCallback } from "react";
import { useParams } from "react-router-dom";
import {
  Mic, MicOff, Volume2, ChevronRight,
  CheckCircle, XCircle, Loader, Bot,
  AlertCircle, Trophy, Clock, Camera, ShieldAlert, AlertTriangle, Ban
} from "lucide-react";
import axios from "axios";
import * as faceapi from "@vladmandic/face-api";
import * as tf from "@tensorflow/tfjs";
import * as cocoSsd from "@tensorflow-models/coco-ssd";

const API = process.env.REACT_APP_API_URL || "http://127.0.0.1:5000/api";

// Public CDN hosting pretrained face-api.js model weights — no local files needed
const FACE_MODEL_URL = "https://justadudewhohacks.github.io/face-api.js/models";

// ── Stages ────────────────────────────────────────────────────────────────────
const STAGE = {
  LOADING   : "loading",
  INTRO     : "intro",
  VERIFYING : "verifying",
  SPEAKING  : "speaking",
  LISTENING : "listening",
  PROCESSING: "processing",
  NEXT      : "next",
  SUBMITTING: "submitting",
  RESULT    : "result",
  ERROR     : "error",
  EXPIRED   : "expired",
  TERMINATED: "terminated",
  DONE      : "done"
};

// Stages during which the candidate is actively "in" the interview and
// integrity violations (tab switch, fullscreen exit, phone, identity) should count.
const ACTIVE_STAGES = [STAGE.SPEAKING, STAGE.LISTENING, STAGE.PROCESSING, STAGE.NEXT];

// Minimum time between two counted strikes, so a single switch-away event
// (which can fire both a blur AND a visibilitychange AND a fullscreen-exit
// event almost simultaneously) is only ever counted once.
const STRIKE_COOLDOWN_MS = 4000;

// face-api.js euclidean-distance convention: < 0.6 is generally the same person.
const IDENTITY_MATCH_THRESHOLD = 0.6;

const VIOLATION_LABELS = {
  tab_switch      : "You switched away from this tab.",
  window_blur     : "You switched away from this window.",
  fullscreen_exit : "You exited full-screen mode.",
  phone_detected  : "A phone was detected on camera."
};

// ── Waveform animation ────────────────────────────────────────────────────────
function Waveform({ active }) {
  return (
    <div className="flex items-center justify-center gap-1 h-12">
      {[1,2,3,4,5,6,7].map((i) => (
        <div
          key={i}
          className={`w-1.5 rounded-full transition-all duration-150 ${
            active ? "bg-blue-400" : "bg-gray-600"
          }`}
          style={{
            height: active ? `${Math.random() * 32 + 8}px` : "8px",
            animation: active ? `wave ${0.5 + i * 0.1}s ease-in-out infinite alternate` : "none"
          }}
        />
      ))}
      <style>{`
        @keyframes wave {
          from { height: 8px; }
          to   { height: ${Math.floor(Math.random() * 32 + 16)}px; }
        }
      `}</style>
    </div>
  );
}

// ── Score Ring ────────────────────────────────────────────────────────────────
function ScoreRing({ score }) {
  const color = score >= 70 ? "#22c55e" : score >= 50 ? "#eab308" : "#ef4444";
  const r     = 54;
  const circ  = 2 * Math.PI * r;
  const dash  = (score / 100) * circ;

  return (
    <div className="relative w-36 h-36 flex items-center justify-center mx-auto">
      <svg className="absolute inset-0 -rotate-90" width="144" height="144">
        <circle cx="72" cy="72" r={r} fill="none" stroke="#1e293b" strokeWidth="10" />
        <circle
          cx="72" cy="72" r={r} fill="none"
          stroke={color} strokeWidth="10"
          strokeDasharray={`${dash} ${circ}`}
          strokeLinecap="round"
          style={{ transition: "stroke-dasharray 1s ease" }}
        />
      </svg>
      <div className="text-center">
        <p className="text-4xl font-bold text-white">{score}</p>
        <p className="text-sm text-gray-400">/ 100</p>
      </div>
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────
export default function InterviewPortal() {
  const { token }               = useParams();
  const [stage,     setStage]   = useState(STAGE.LOADING);
  const [interview, setInterview] = useState(null);
  const [currentQ,  setCurrentQ] = useState(0);
  const [answers,   setAnswers]  = useState([]);
  const [transcript, setTranscript] = useState("");
  const [result,    setResult]   = useState(null);
  const [error,     setError]    = useState("");
  const [timeLeft,  setTimeLeft] = useState(120); // 2 min per question

  // ── Integrity monitoring state ────────────────────────────────────────────
  const [cameraReady,    setCameraReady]    = useState(false);
  const [cameraError,    setCameraError]    = useState("");
  const [modelsLoading,  setModelsLoading]  = useState(true);
  const [faceStatus,     setFaceStatus]     = useState("checking"); // checking | ok | no_face | multiple_faces | phone_detected | identity_mismatch
  const [flagCount,      setFlagCount]      = useState(0);

  // ── Identity verification state (runs once, before Q1) ───────────────────
  const [verifyStatus, setVerifyStatus] = useState("waiting"); // waiting | no_face | multiple_faces | verified

  // ── Strike / termination state ────────────────────────────────────────────
  const [warning,          setWarning]          = useState(null); // { message } | null
  const [terminationReason, setTerminationReason] = useState("");

  const cocoModelRef = useRef(null);

  const synthRef      = useRef(window.speechSynthesis);
  const recognRef      = useRef(null);
  const timerRef       = useRef(null);
  const videoRef       = useRef(null);
  const streamRef       = useRef(null);
  const detectionRef    = useRef(null);
  const warningTimeoutRef = useRef(null);
  const integrityLogRef = useRef([]); // { type, at_seconds }
  const interviewStartRef = useRef(null);

  // Identity verification refs
  const referenceDescriptorRef   = useRef(null);
  const verifyIntervalRef        = useRef(null);
  const identityCheckIntervalRef = useRef(null);
  const identityMismatchCountRef = useRef(0);

  // Strike-system refs (avoid stale closures inside event listeners / intervals)
  const stageRef       = useRef(stage);
  const strikeCountRef = useRef(0);
  const lastStrikeAtRef = useRef(0);
  const answersRef     = useRef(answers);
  const currentQRef    = useRef(currentQ);
  const transcriptRef  = useRef(transcript);

  useEffect(() => { stageRef.current = stage; }, [stage]);
  useEffect(() => { answersRef.current = answers; }, [answers]);
  useEffect(() => { currentQRef.current = currentQ; }, [currentQ]);
  useEffect(() => { transcriptRef.current = transcript; }, [transcript]);

  // ── Load face-api + coco-ssd models once on mount ─────────────────────────
  useEffect(() => {
    const loadModels = async () => {
      try {
        await faceapi.nets.tinyFaceDetector.loadFromUri(FACE_MODEL_URL);
        // Needed for identity verification (recognition), not just detection.
        await faceapi.nets.faceLandmark68Net.loadFromUri(FACE_MODEL_URL);
        await faceapi.nets.faceRecognitionNet.loadFromUri(FACE_MODEL_URL);
      } catch (err) {
        console.error("Failed to load face detection/recognition models:", err);
        // don't block the interview if face models fail to load
      }
      try {
        await tf.ready();
        cocoModelRef.current = await cocoSsd.load({ base: "lite_mobilenet_v2" });
      } catch (err) {
        console.error("Failed to load phone detection model:", err);
        // don't block the interview if the object detection model fails to load
      }
      setModelsLoading(false);
    };
    loadModels();
  }, []);

  // ── Load interview data ───────────────────────────────────────────────────
  useEffect(() => {
    const load = async () => {
      try {
        const res = await axios.get(`${API}/pipeline/interview/public/${token}`);
        if (res.data.success) {
          setInterview(res.data);
          setStage(STAGE.INTRO);
        } else {
          setError(res.data.error || "Invalid interview link");
          setStage(STAGE.ERROR);
        }
      } catch (err) {
        setError(err.response?.data?.error || "Failed to load interview");
        setStage(STAGE.ERROR);
      }
    };
    load();
  }, [token]);

  // ── Start camera (called when candidate clicks Start Interview) ──────────
  const startCamera = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 320, height: 240 },
        audio: false
      });
      streamRef.current = stream;
      setCameraReady(true);
      setCameraError("");
      return true;
    } catch (err) {
      setCameraError("Camera access denied or unavailable. The interview will continue without integrity monitoring.");
      setCameraReady(false);
      return false;
    }
  }, []);

  // ── Attach the already-acquired camera stream to the <video> element ─────
  // once it exists in the DOM (Intro screen has none; Verifying/Interview do).
  useEffect(() => {
    if (cameraReady && streamRef.current && videoRef.current) {
      videoRef.current.srcObject = streamRef.current;
      videoRef.current.play().catch(() => {});
    }
  }, [cameraReady, stage]);

  // ── Log an integrity flag (deduped so we don't spam every 2s while ongoing) ─
  const logFlag = useCallback((type) => {
    const elapsedSeconds = interviewStartRef.current
      ? Math.round((Date.now() - interviewStartRef.current) / 1000)
      : 0;
    integrityLogRef.current.push({ type, at_seconds: elapsedSeconds });
    setFlagCount(integrityLogRef.current.length);
    return elapsedSeconds;
  }, []);
// ── Terminate the interview immediately (2nd strike, or identity mismatch) ─
  const terminateInterview = useCallback(async (reason) => {
    if (stageRef.current === STAGE.TERMINATED || stageRef.current === STAGE.RESULT) return;

    // Stop everything
    synthRef.current?.cancel();
    recognRef.current?.stop();
    recognRef.current = null;
    clearInterval(timerRef.current);
    clearInterval(detectionRef.current);
    clearInterval(verifyIntervalRef.current);
    clearInterval(identityCheckIntervalRef.current);
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
    }
    if (document.fullscreenElement) {
      document.exitFullscreen().catch(() => {});
    }

    setTerminationReason(reason);
    setStage(STAGE.TERMINATED);

    try {
      await axios.post(`${API}/pipeline/interview/public/${token}/submit`, {
        qa_pairs: answersRef.current,
        terminated: true,
        termination_reason: reason,
        integrity_log: integrityLogRef.current
      });
    } catch (err) {
      // Swallow — candidate still sees the Terminated screen either way.
    }
  }, [token]);

  // ── Register a strike (phone / tab-switch / fullscreen-exit) ─────────────
  // 1st strike -> warning overlay. 2nd strike -> terminate immediately.
  const registerStrike = useCallback((type) => {
    if (!ACTIVE_STAGES.includes(stageRef.current)) return;

    const now = Date.now();
    if (now - lastStrikeAtRef.current < STRIKE_COOLDOWN_MS) return; // debounce
    lastStrikeAtRef.current = now;

    logFlag(type);
    strikeCountRef.current += 1;

    const label = VIOLATION_LABELS[type] || "A policy violation was detected.";

    if (strikeCountRef.current === 1) {
      clearTimeout(warningTimeoutRef.current);
      setWarning({
        message: `${label} This is your first and final warning — doing this again will end your interview immediately.`
      });
      warningTimeoutRef.current = setTimeout(() => setWarning(null), 6000);
    } else {
      setWarning(null);
      terminateInterview(`${label} (second violation)`);
    }
  }, [logFlag, terminateInterview]);

  // ── Identity verification loop (Verifying screen only, before Q1) ────────
  // Captures a reference face descriptor once a single, stable face is seen
  // for two consecutive reads (~2.4s), then moves on to Question 1.
  useEffect(() => {
    if (stage !== STAGE.VERIFYING || !cameraReady || modelsLoading) return;

    let cancelled = false;
    let stableHits = 0;

    verifyIntervalRef.current = setInterval(async () => {
      if (cancelled || !videoRef.current || videoRef.current.readyState !== 4) return;

      try {
        const allFaces = await faceapi.detectAllFaces(
          videoRef.current,
          new faceapi.TinyFaceDetectorOptions()
        );

        if (allFaces.length > 1) {
          setVerifyStatus("multiple_faces");
          stableHits = 0;
          return;
        }
        if (allFaces.length === 0) {
          setVerifyStatus("no_face");
          stableHits = 0;
          return;
        }

        const detection = await faceapi
          .detectSingleFace(videoRef.current, new faceapi.TinyFaceDetectorOptions())
          .withFaceLandmarks()
          .withFaceDescriptor();

        if (!detection) {
          setVerifyStatus("no_face");
          stableHits = 0;
          return;
        }

        setVerifyStatus("waiting");
        stableHits += 1;

        if (stableHits >= 2) {
          referenceDescriptorRef.current = detection.descriptor;
          cancelled = true;
          clearInterval(verifyIntervalRef.current);
          setVerifyStatus("verified");
          setTimeout(() => {
            askQuestion(0);
          }, 1200);
        }
      } catch (err) {
        // keep retrying silently — camera hiccups shouldn't surface an error here
      }
    }, 1200);

    return () => {
      cancelled = true;
      clearInterval(verifyIntervalRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stage, cameraReady, modelsLoading]);

  // ── Ongoing identity check during the active interview ────────────────────
  // Every 8s, compares the current face against the verified reference.
  // Two consecutive mismatches -> hard termination (more severe than a strike).
  useEffect(() => {
    if (!cameraReady || modelsLoading) return;

    identityCheckIntervalRef.current = setInterval(async () => {
      if (!videoRef.current || videoRef.current.readyState !== 4) return;
      if (!referenceDescriptorRef.current) return;
      if (!ACTIVE_STAGES.includes(stageRef.current)) return;

      try {
        const detection = await faceapi
          .detectSingleFace(videoRef.current, new faceapi.TinyFaceDetectorOptions())
          .withFaceLandmarks()
          .withFaceDescriptor();

        if (!detection) return; // no_face is already handled by the other detection loop

        const distance = faceapi.euclideanDistance(referenceDescriptorRef.current, detection.descriptor);

        if (distance > IDENTITY_MATCH_THRESHOLD) {
          identityMismatchCountRef.current += 1;
          setFaceStatus("identity_mismatch");

          if (identityMismatchCountRef.current >= 2) {
            logFlag("identity_mismatch");
            terminateInterview("Identity verification failed — the person on camera no longer matches the verified identity.");
          }
        } else {
          identityMismatchCountRef.current = 0;
        }
      } catch (err) {
        // ignore — don't let a bad frame kill the interview
      }
    }, 8000);

    return () => clearInterval(identityCheckIntervalRef.current);
  }, [cameraReady, modelsLoading, logFlag, terminateInterview]);

  // ── Face + phone detection loop (runs every 2s once camera + models ready) ─
  useEffect(() => {
    if (!cameraReady || modelsLoading) return;

    let lastStatus = "ok";
    let consecutiveNoFace = 0;

    detectionRef.current = setInterval(async () => {
      if (!videoRef.current || videoRef.current.readyState !== 4) return;
      if (!ACTIVE_STAGES.includes(stageRef.current)) return;

      try {
        if (cocoModelRef.current) {
          const objects = await cocoModelRef.current.detect(videoRef.current);
          const phoneVisible = objects.some(
            (o) => o.class === "cell phone" && o.score > 0.5
          );
          if (phoneVisible) {
            setFaceStatus("phone_detected");
            if (lastStatus !== "phone_detected") {
              registerStrike("phone_detected");
              lastStatus = "phone_detected";
            }
            return;
          }
        }

        const detections = await faceapi.detectAllFaces(
          videoRef.current,
          new faceapi.TinyFaceDetectorOptions()
        );

        if (detections.length === 0) {
          consecutiveNoFace += 1;
          setFaceStatus("no_face");
          if (consecutiveNoFace === 3 && lastStatus !== "no_face_flagged") {
            logFlag("no_face");
            lastStatus = "no_face_flagged";
          }
        } else if (detections.length > 1) {
          consecutiveNoFace = 0;
          setFaceStatus("multiple_faces");
          if (lastStatus !== "multiple_faces") {
            logFlag("multiple_faces");
            lastStatus = "multiple_faces";
          }
        } else {
          consecutiveNoFace = 0;
          setFaceStatus("ok");
          lastStatus = "ok";
        }
      } catch (err) {
        // Detection errors shouldn't interrupt the interview
      }
    }, 2000);

    return () => clearInterval(detectionRef.current);
  }, [cameraReady, modelsLoading, logFlag, registerStrike]);

  // ── Tab-switch / window-blur detection ────────────────────────────────────
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden && ACTIVE_STAGES.includes(stageRef.current)) {
        registerStrike("tab_switch");
      }
    };
    const handleBlur = () => {
      if (ACTIVE_STAGES.includes(stageRef.current)) {
        registerStrike("window_blur");
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    window.addEventListener("blur", handleBlur);

    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      window.removeEventListener("blur", handleBlur);
    };
  }, [registerStrike]);

  // ── Full-screen exit detection ────────────────────────────────────────────
  useEffect(() => {
    const handleFullscreenChange = () => {
      if (!document.fullscreenElement && ACTIVE_STAGES.includes(stageRef.current)) {
        registerStrike("fullscreen_exit");
      }
    };
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", handleFullscreenChange);
  }, [registerStrike]);

  // ── Speech synthesis ──────────────────────────────────────────────────────
  const speak = useCallback((text, onEnd) => {
    synthRef.current.cancel();
    const utt      = new SpeechSynthesisUtterance(text);
    utt.rate       = 0.9;
    utt.pitch      = 1;
    utt.volume     = 1;
    const voices   = synthRef.current.getVoices();
    const preferred = voices.find(v =>
      v.name.includes("Google") || v.name.includes("Natural") || v.lang === "en-US"
    );
    if (preferred) utt.voice = preferred;
    utt.onend = onEnd || (() => {});
    synthRef.current.speak(utt);
  }, []);

  // ── Speech recognition ────────────────────────────────────────────────────
  const startListening = useCallback(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      setError("Your browser doesn't support voice recognition. Please use Chrome.");
      setStage(STAGE.ERROR);
      return;
    }

    const recog          = new SR();
    recog.continuous     = true;
    recog.interimResults = true;
    recog.lang           = "en-US";
    recognRef.current    = recog;

    let finalText = "";

    recog.onresult = (e) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) {
          finalText += e.results[i][0].transcript + " ";
        } else {
          interim = e.results[i][0].transcript;
        }
      }
      setTranscript(finalText + interim);
    };

    recog.onerror = (e) => {
      if (e.error !== "no-speech") {
        console.error("Speech error:", e.error);
      }
    };

    recog.start();
    setStage(STAGE.LISTENING);

    setTimeLeft(120);
    timerRef.current = setInterval(() => {
      setTimeLeft(prev => {
        if (prev <= 1) {
          clearInterval(timerRef.current);
          handleNextQuestion(finalText);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  }, []);

  // ── Ask current question ──────────────────────────────────────────────────
  const askQuestion = useCallback((index) => {
    if (!interview) return;
    const q = interview.questions[index];
    if (!q) return;

    setTranscript("");
    setStage(STAGE.SPEAKING);

    const intro = index === 0
      ? `Hello ${interview.candidate_name}. Welcome to your interview for the ${interview.job_title} position at ${interview.company_name}. I will ask you ${interview.total} questions. Please speak clearly after each question. Let's begin. `
      : "";

    const text = `${intro}Question ${index + 1}. ${q.question}`;

    speak(text, () => {
      startListening();
    });
  }, [interview, speak, startListening]);

  // ── Next question ─────────────────────────────────────────────────────────
  const handleNextQuestion = useCallback((currentTranscript) => {
    if (recognRef.current) {
      recognRef.current.stop();
      recognRef.current = null;
    }
    clearInterval(timerRef.current);
    synthRef.current.cancel();

    const answer = currentTranscript || transcript;
    const q      = interview.questions[currentQ];

    const newAnswers = [...answers, {
      question: q.question,
      answer  : answer.trim() || "(No answer provided)"
    }];
    setAnswers(newAnswers);
    setTranscript("");

    const nextIndex = currentQ + 1;

    if (nextIndex >= interview.questions.length) {
      submitInterview(newAnswers);
    } else {
      setCurrentQ(nextIndex);
      setStage(STAGE.NEXT);

      setTimeout(() => {
        speak(`Good. `, () => {
          askQuestion(nextIndex);
        });
      }, 1000);
    }
  }, [transcript, answers, currentQ, interview, speak, askQuestion]);
// ── Submit interview ──────────────────────────────────────────────────────
  const submitInterview = async (finalAnswers) => {
    setStage(STAGE.SUBMITTING);

    clearInterval(detectionRef.current);
    clearInterval(identityCheckIntervalRef.current);
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
    }
    if (document.fullscreenElement) {
      document.exitFullscreen().catch(() => {});
    }

    try {
      const res = await axios.post(
        `${API}/pipeline/interview/public/${token}/submit`,
        { qa_pairs: finalAnswers, integrity_log: integrityLogRef.current }
      );
      if (res.data.success) {
        setResult(res.data);
        setStage(STAGE.RESULT);
      } else {
        setError(res.data.error || "Submission failed");
        setStage(STAGE.ERROR);
      }
    } catch (err) {
      setError(err.response?.data?.error || "Submission failed");
      setStage(STAGE.ERROR);
    }
  };

  // ── Start interview ───────────────────────────────────────────────────────
  const startInterview = async () => {
    interviewStartRef.current = Date.now();
    strikeCountRef.current = 0;
    lastStrikeAtRef.current = 0;
    identityMismatchCountRef.current = 0;
    referenceDescriptorRef.current = null;

    try {
      if (document.documentElement.requestFullscreen) {
        await document.documentElement.requestFullscreen();
      }
    } catch (err) {
      // Fullscreen denied/unsupported — interview continues without it.
    }

    await startCamera();
    setStage(STAGE.VERIFYING);
  };

  // ── Skip / Next manually ──────────────────────────────────────────────────
  const handleSkip = () => {
    handleNextQuestion(transcript);
  };

  // ── Cleanup ───────────────────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      synthRef.current?.cancel();
      recognRef.current?.stop();
      clearInterval(timerRef.current);
      clearInterval(detectionRef.current);
      clearInterval(verifyIntervalRef.current);
      clearInterval(identityCheckIntervalRef.current);
      clearTimeout(warningTimeoutRef.current);
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(t => t.stop());
      }
    };
  }, []);

  // ─────────────────────────────────────────────────────────────────────────
  // RENDER
  // ─────────────────────────────────────────────────────────────────────────

  if (stage === STAGE.LOADING) {
    return (
      <Screen>
        <div className="flex flex-col items-center gap-4">
          <Loader size={40} className="text-blue-400 animate-spin" />
          <p className="text-gray-400">Loading your interview...</p>
        </div>
      </Screen>
    );
  }

  if (stage === STAGE.ERROR || stage === STAGE.EXPIRED) {
    return (
      <Screen>
        <div className="text-center space-y-4">
          <AlertCircle size={48} className="text-red-400 mx-auto" />
          <h2 className="text-2xl font-bold text-white">Oops!</h2>
          <p className="text-gray-400">{error}</p>
        </div>
      </Screen>
    );
  }

  if (stage === STAGE.TERMINATED) {
    return (
      <Screen>
        <div className="text-center space-y-4 max-w-md">
          <div className="w-20 h-20 bg-red-600 rounded-2xl flex items-center justify-center mx-auto shadow-lg shadow-red-600/30">
            <Ban size={40} className="text-white" />
          </div>
          <h2 className="text-2xl font-bold text-white">Interview Ended</h2>
          <p className="text-gray-400">
            Your interview was ended due to an integrity policy violation.
          </p>
          <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700 text-left">
            <p className="text-gray-500 text-xs mb-1">Reason</p>
            <p className="text-gray-300 text-sm">{terminationReason}</p>
          </div>
          <p className="text-gray-500 text-sm">
            If you believe this was a mistake, please contact the hiring team.
          </p>
        </div>
      </Screen>
    );
  }

  if (stage === STAGE.INTRO) {
    return (
      <Screen>
        <div className="text-center space-y-6 max-w-lg">
          <div className="w-20 h-20 bg-blue-600 rounded-2xl flex items-center justify-center mx-auto shadow-lg shadow-blue-600/30">
            <Bot size={40} className="text-white" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-white">
              Hi, {interview?.candidate_name}! 👋
            </h1>
            <p className="text-gray-400 mt-2">
              You're interviewing for <span className="text-blue-400 font-semibold">{interview?.job_title}</span>
            </p>
            <p className="text-gray-500 text-sm mt-1">at {interview?.company_name}</p>
          </div>

          <div className="bg-gray-800/50 rounded-2xl p-6 border border-gray-700 text-left space-y-3">
            <h3 className="text-white font-semibold">Before you begin:</h3>
            <div className="space-y-2">
              {[
                "Find a quiet place with no background noise",
                `${interview?.total} questions — 2 minutes per question`,
                "Speak clearly when the microphone is active",
                "You can't pause or restart the interview",
                "Use Chrome browser for best experience"
              ].map((tip, i) => (
                <div key={i} className="flex items-start gap-2 text-sm text-gray-400">
                  <CheckCircle size={14} className="text-green-400 mt-0.5 shrink-0" />
                  {tip}
                </div>
              ))}
            </div>
          </div>

          <div className="bg-blue-950/30 rounded-2xl p-5 border border-blue-800/40 text-left space-y-2">
            <div className="flex items-center gap-2">
              <Camera size={16} className="text-blue-400" />
              <h3 className="text-white font-semibold text-sm">Camera-based interview integrity</h3>
            </div>
            <p className="text-gray-400 text-xs leading-relaxed">
              This interview uses your camera to check that you're present, alone,
              and not referencing a phone while answering. Before Question 1, you'll
              also do a quick face check to confirm your identity for the rest of the
              interview. Detection runs entirely in your browser —
              <span className="text-gray-300 font-medium"> no video is recorded, stored, or sent to our servers.</span>
              {" "}You'll be asked to allow camera access when you click Start.
            </p>
          </div>

          <div className="bg-amber-950/20 rounded-2xl p-5 border border-amber-800/30 text-left space-y-2">
            <div className="flex items-center gap-2">
              <AlertTriangle size={16} className="text-amber-400" />
              <h3 className="text-white font-semibold text-sm">Stay on this tab, in full screen</h3>
            </div>
            <p className="text-gray-400 text-xs leading-relaxed">
              The interview will run in full-screen mode. Switching tabs, switching
              windows, exiting full screen, or showing a phone on camera counts as a
              violation. You'll get <span className="text-gray-300 font-medium">one warning</span> —
              a second violation of any kind will <span className="text-gray-300 font-medium">end the interview immediately</span>.
            </p>
          </div>

          <button
            onClick={startInterview}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-4 rounded-xl transition-all text-lg shadow-lg shadow-blue-600/30 flex items-center justify-center gap-2"
          >
            <Mic size={20} />
            Start Interview
          </button>
        </div>
      </Screen>
    );
  }

  // Identity verification screen (runs once, before Q1)
  if (stage === STAGE.VERIFYING) {
    return (
      <Screen>
        <div className="text-center space-y-6 max-w-md w-full">
          <div className="w-20 h-20 bg-blue-600 rounded-2xl flex items-center justify-center mx-auto shadow-lg shadow-blue-600/30">
            <ShieldAlert size={40} className="text-white" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-white">Verifying your identity</h2>
            <p className="text-gray-400 text-sm mt-2">
              Look directly at the camera. This confirms who's answering before we begin.
            </p>
          </div>

          <div className="relative w-full max-w-xs mx-auto aspect-[4/3] bg-gray-900 rounded-2xl overflow-hidden border-2 border-gray-800">
            <video
              ref={videoRef}
              autoPlay
              muted
              playsInline
              className="w-full h-full object-cover scale-x-[-1]"
            />
            {!cameraReady && (
              <div className="absolute inset-0 flex items-center justify-center bg-gray-900/90">
                <Loader size={24} className="text-gray-500 animate-spin" />
              </div>
            )}
          </div>

          <div className={`flex items-center justify-center gap-2 text-sm font-medium rounded-xl py-3 px-4 border ${
            verifyStatus === "verified"
              ? "bg-green-500/10 text-green-400 border-green-500/20"
              : verifyStatus === "no_face"
              ? "bg-amber-500/10 text-amber-400 border-amber-500/20"
              : verifyStatus === "multiple_faces"
              ? "bg-red-500/10 text-red-400 border-red-500/20"
              : "bg-gray-800/50 text-gray-400 border-gray-700"
          }`}>
            {verifyStatus === "verified" && (<><CheckCircle size={16} /> Identity verified — starting now</>)}
            {verifyStatus === "no_face" && (<><ShieldAlert size={16} /> No face detected — center yourself in frame</>)}
            {verifyStatus === "multiple_faces" && (<><ShieldAlert size={16} /> Only one person should be visible</>)}
            {verifyStatus === "waiting" && (<><Loader size={16} className="animate-spin" /> Hold still, checking...</>)}
          </div>

          {cameraError && (
            <p className="text-red-400 text-xs">{cameraError}</p>
          )}
        </div>
      </Screen>
    );
  }

  if (stage === STAGE.RESULT) {
    const passed = result?.decision === "advance";
    return (
      <Screen>
        <div className="text-center space-y-6 max-w-lg w-full">
          <div className={`w-20 h-20 rounded-2xl flex items-center justify-center mx-auto shadow-lg ${
            passed ? "bg-green-600 shadow-green-600/30" : "bg-red-600 shadow-red-600/30"
          }`}>
            {passed
              ? <Trophy size={40} className="text-white" />
              : <XCircle size={40} className="text-white" />
            }
          </div>

          <div>
            <h1 className="text-3xl font-bold text-white">
              {passed ? "Congratulations! 🎉" : "Thank you for interviewing"}
            </h1>
            <p className="text-gray-400 mt-2">
              {passed
                ? "You've been shortlisted for the next round!"
                : "We appreciate your time and effort."
              }
            </p>
          </div>

          <ScoreRing score={result?.overall_score || 0} />

          <div className="bg-gray-800/50 rounded-2xl p-6 border border-gray-700 space-y-3">
            <div className="flex justify-between text-sm">
              <span className="text-gray-400">Overall Score</span>
              <span className="text-white font-bold">{result?.overall_score}/100</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-400">Recommendation</span>
              <span className={`font-semibold ${passed ? "text-green-400" : "text-red-400"}`}>
                {result?.hiring_recommendation}
              </span>
            </div>
            {passed && (
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Next Step</span>
                <span className="text-blue-400 font-semibold">{result?.next_step}</span>
              </div>
            )}
          </div>

          <div className="bg-gray-800/30 rounded-xl p-4 border border-gray-800">
            <p className="text-gray-400 text-sm">{result?.summary}</p>
          </div>

          <p className="text-gray-500 text-sm">
            {passed
              ? "You'll receive an email with interview details soon."
              : "You'll receive a follow-up email shortly. Keep improving!"
            }
          </p>
        </div>
      </Screen>
    );
  }

  if (stage === STAGE.SUBMITTING) {
    return (
      <Screen>
        <div className="text-center space-y-4">
          <Loader size={40} className="text-blue-400 animate-spin mx-auto" />
          <h2 className="text-xl font-bold text-white">Evaluating your answers...</h2>
          <p className="text-gray-400">Our AI is analyzing your responses</p>
        </div>
      </Screen>
    );
  }

  const question    = interview?.questions[currentQ];
  const isListening = stage === STAGE.LISTENING;
  const isSpeaking  = stage === STAGE.SPEAKING;
  const progress    = ((currentQ) / (interview?.total || 1)) * 100;
  const mins        = Math.floor(timeLeft / 60);
  const secs        = timeLeft % 60;

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col">
      {warning && (
        <div className="bg-amber-600 text-white px-6 py-3 flex items-center gap-2 justify-center text-sm font-medium">
          <AlertTriangle size={16} className="shrink-0" />
          <span>{warning.message}</span>
        </div>
      )}

      <div className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
            <Bot size={16} className="text-white" />
          </div>
          <div>
            <p className="text-white text-sm font-semibold">AI Interviewer</p>
            <p className="text-gray-500 text-xs">{interview?.company_name}</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          {isListening && (
            <div className="flex items-center gap-2 text-sm">
              <Clock size={14} className="text-yellow-400" />
              <span className={`font-mono font-bold ${timeLeft < 30 ? "text-red-400" : "text-yellow-400"}`}>
                {mins}:{secs.toString().padStart(2, "0")}
              </span>
            </div>
          )}
          <span className="text-gray-400 text-sm">
            {currentQ + 1} / {interview?.total}
          </span>
        </div>
      </div>

      <div className="h-1 bg-gray-800">
        <div
          className="h-full bg-blue-600 transition-all duration-500"
          style={{ width: `${progress}%` }}
        />
      </div>

      <div className="flex-1 flex flex-col items-center justify-center p-6 max-w-2xl mx-auto w-full relative">

        <div className="absolute top-0 right-0 md:right-6">
          <div className="relative w-32 h-24 bg-gray-900 rounded-xl overflow-hidden border-2 border-gray-800">
            <video
              ref={videoRef}
              autoPlay
              muted
              playsInline
              className="w-full h-full object-cover scale-x-[-1]"
            />
            {!cameraReady && (
              <div className="absolute inset-0 flex items-center justify-center bg-gray-900/90">
                <Camera size={18} className="text-gray-600" />
              </div>
            )}
          </div>
          {cameraReady && (
            <div className={`mt-1.5 flex items-center gap-1 text-xs px-2 py-1 rounded-full justify-center ${
              faceStatus === "ok"
                ? "bg-green-500/10 text-green-400 border border-green-500/20"
                : faceStatus === "checking"
                ? "bg-gray-500/10 text-gray-400 border border-gray-500/20"
                : "bg-red-500/10 text-red-400 border border-red-500/20"
            }`}>
              {faceStatus === "ok" && (<><CheckCircle size={11} /> Monitoring</>)}
              {faceStatus === "checking" && (<><Loader size={11} className="animate-spin" /> Starting camera...</>)}
              {faceStatus === "no_face" && (<><ShieldAlert size={11} /> No face detected</>)}
              {faceStatus === "multiple_faces" && (<><ShieldAlert size={11} /> Multiple faces</>)}
              {faceStatus === "phone_detected" && (<><ShieldAlert size={11} /> Phone detected</>)}
              {faceStatus === "identity_mismatch" && (<><ShieldAlert size={11} /> Identity mismatch</>)}
            </div>
          )}
          {cameraError && (
            <p className="text-red-400 text-[10px] mt-1 max-w-[130px] text-center leading-tight">
              {cameraError}
            </p>
          )}
        </div>

        <div className={`w-24 h-24 rounded-full flex items-center justify-center mb-8 transition-all duration-300 ${
          isSpeaking
            ? "bg-blue-600 shadow-2xl shadow-blue-600/50 scale-110"
            : isListening
            ? "bg-green-600 shadow-2xl shadow-green-600/50"
            : "bg-gray-800"
        }`}>
          {isSpeaking
            ? <Volume2 size={40} className="text-white" />
            : isListening
            ? <Mic size={40} className="text-white" />
            : <Bot size={40} className="text-gray-400" />
          }
        </div>

        <div className="text-center mb-6">
          {isSpeaking && (
            <div className="flex items-center gap-2 text-blue-400 text-sm font-medium justify-center mb-2">
              <div className="w-2 h-2 bg-blue-400 rounded-full animate-pulse" />
              AI is speaking...
            </div>
          )}
          {isListening && (
            <div className="flex items-center gap-2 text-green-400 text-sm font-medium justify-center mb-2">
              <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
              Listening... speak now
            </div>
          )}
        </div>

        <div className="mb-8">
          <Waveform active={isListening} />
        </div>

        {question && (
          <div className="w-full bg-gray-900 border border-gray-800 rounded-2xl p-6 mb-6">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-xs font-medium text-blue-400 bg-blue-400/10 px-2 py-0.5 rounded-full border border-blue-400/20">
                Q{currentQ + 1}
              </span>
              <span className="text-xs text-gray-500">
                {question.id <= 3 ? "Technical" : question.id <= 6 ? "Behavioral" : "Gap-focused"}
              </span>
            </div>
            <p className="text-white font-medium leading-relaxed">{question.question}</p>
          </div>
        )}

        {isListening && (
          <div className="w-full bg-gray-900/50 border border-gray-800 rounded-xl p-4 mb-6 min-h-[80px]">
            <p className="text-xs text-gray-500 mb-2">Your answer (live transcript):</p>
            <p className="text-gray-300 text-sm leading-relaxed">
              {transcript || (
                <span className="text-gray-600 italic">Start speaking...</span>
              )}
            </p>
          </div>
        )}

        {isListening && (
          <div className="flex gap-3 w-full">
            <button
              onClick={handleSkip}
              className="flex-1 bg-gray-800 hover:bg-gray-700 text-white font-medium py-3 rounded-xl transition-all border border-gray-700 text-sm"
            >
              Skip Question
            </button>
            <button
              onClick={() => handleNextQuestion(transcript)}
              className="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-xl transition-all flex items-center justify-center gap-2 shadow-lg shadow-blue-600/30"
            >
              Next Question <ChevronRight size={18} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function Screen({ children }) {
  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center p-6">
      {children}
    </div>
  );
}