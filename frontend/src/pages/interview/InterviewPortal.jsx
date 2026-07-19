import { useState, useEffect, useRef, useCallback } from "react";
import { useParams } from "react-router-dom";
import {
  Mic, MicOff, Volume2, ChevronRight,
  CheckCircle, XCircle, Loader, Bot,
  AlertCircle, Trophy, Clock
} from "lucide-react";
import axios from "axios";

const API = "http://127.0.0.1:5000/api";

// ── Stages ────────────────────────────────────────────────────────────────────
const STAGE = {
  LOADING   : "loading",
  INTRO     : "intro",
  SPEAKING  : "speaking",
  LISTENING : "listening",
  PROCESSING: "processing",
  NEXT      : "next",
  SUBMITTING: "submitting",
  RESULT    : "result",
  ERROR     : "error",
  EXPIRED   : "expired",
  DONE      : "done"
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

  const synthRef   = useRef(window.speechSynthesis);
  const recognRef  = useRef(null);
  const timerRef   = useRef(null);
  const hasSpoken  = useRef(false);

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

    // Start 2-minute timer
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
    // Stop recognition and timer
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
      // All questions done — submit
      submitInterview(newAnswers);
    } else {
      setCurrentQ(nextIndex);
      setStage(STAGE.NEXT);

      // Brief pause then ask next
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
    try {
      const res = await axios.post(
        `${API}/pipeline/interview/public/${token}/submit`,
        { qa_pairs: finalAnswers }
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
  const startInterview = () => {
    askQuestion(0);
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
    };
  }, []);

  // ─────────────────────────────────────────────────────────────────────────
  // RENDER
  // ─────────────────────────────────────────────────────────────────────────

  // Loading
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

  // Error
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

  // Intro screen
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

  // Result screen
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

  // Submitting
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

  // Interview in progress
  const question    = interview?.questions[currentQ];
  const isListening = stage === STAGE.LISTENING;
  const isSpeaking  = stage === STAGE.SPEAKING;
  const progress    = ((currentQ) / (interview?.total || 1)) * 100;
  const mins        = Math.floor(timeLeft / 60);
  const secs        = timeLeft % 60;

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col">
      {/* Top bar */}
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

      {/* Progress bar */}
      <div className="h-1 bg-gray-800">
        <div
          className="h-full bg-blue-600 transition-all duration-500"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col items-center justify-center p-6 max-w-2xl mx-auto w-full">

        {/* AI Avatar */}
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

        {/* Status */}
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

        {/* Waveform */}
        <div className="mb-8">
          <Waveform active={isListening} />
        </div>

        {/* Question card */}
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

        {/* Live transcript */}
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

        {/* Action buttons */}
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

// ── Full screen wrapper ───────────────────────────────────────────────────────
function Screen({ children }) {
  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center p-6">
      {children}
    </div>
  );
}