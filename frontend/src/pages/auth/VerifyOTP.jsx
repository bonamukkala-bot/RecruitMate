import { useState, useRef } from "react";
import { useNavigate, useLocation, Link } from "react-router-dom";
import { Bot, Mail } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import Button from "../../components/ui/Button";
import toast from "react-hot-toast";

export default function VerifyOTP() {
  const [otp, setOtp]         = useState(["", "", "", "", "", ""]);
  const [loading, setLoading] = useState(false);
  const { verifyOTP }         = useAuth();
  const navigate              = useNavigate();
  const location              = useLocation();
  const inputRefs             = useRef([]);

  const email = location.state?.email || "";

  // ── Handle OTP input ─────────────────────────────────────────────────────
  const handleChange = (index, value) => {
    if (!/^\d*$/.test(value)) return;
    const newOtp    = [...otp];
    newOtp[index]   = value.slice(-1);
    setOtp(newOtp);
    if (value && index < 5) {
      inputRefs.current[index + 1]?.focus();
    }
  };

  const handleKeyDown = (index, e) => {
    if (e.key === "Backspace" && !otp[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
  };

  const handlePaste = (e) => {
    e.preventDefault();
    const pasted = e.clipboardData.getData("text").slice(0, 6).split("");
    const newOtp = [...otp];
    pasted.forEach((char, i) => {
      if (/^\d$/.test(char)) newOtp[i] = char;
    });
    setOtp(newOtp);
    inputRefs.current[Math.min(pasted.length, 5)]?.focus();
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const otpString = otp.join("");
    if (otpString.length !== 6) {
      toast.error("Please enter the complete 6-digit OTP");
      return;
    }
    setLoading(true);
    try {
      const data = await verifyOTP(email, otpString);
      if (data.success) {
        toast.success("Email verified! Welcome to RecruitMate AI");
        navigate("/dashboard");
      } else {
        toast.error(data.error || "Invalid OTP");
      }
    } catch (err) {
      toast.error(err.response?.data?.error || "Verification failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-dark-950 flex items-center justify-center p-4">
      {/* Background glow */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-96 h-96 bg-primary-600/10 rounded-full blur-3xl" />
      </div>

      <div className="w-full max-w-md relative">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 bg-primary-600 rounded-2xl mb-4 shadow-lg shadow-primary-600/25">
            <Bot size={28} className="text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white">Verify Your Email</h1>
          <p className="text-dark-400 mt-1 text-sm">
            We sent a 6-digit code to
          </p>
          <div className="flex items-center justify-center gap-2 mt-1">
            <Mail size={14} className="text-primary-400" />
            <p className="text-primary-400 text-sm font-medium">{email}</p>
          </div>
        </div>

        {/* Card */}
        <div className="card border-dark-800 shadow-2xl">
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* OTP inputs */}
            <div className="flex gap-3 justify-center" onPaste={handlePaste}>
              {otp.map((digit, index) => (
                <input
                  key={index}
                  ref={(el) => (inputRefs.current[index] = el)}
                  type="text"
                  inputMode="numeric"
                  maxLength={1}
                  value={digit}
                  onChange={(e) => handleChange(index, e.target.value)}
                  onKeyDown={(e) => handleKeyDown(index, e)}
                  className="w-12 h-12 text-center text-xl font-bold bg-dark-800 border border-dark-700 rounded-xl text-white focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500 transition-all"
                />
              ))}
            </div>

            <Button
              type="submit"
              loading={loading}
              className="w-full justify-center"
            >
              Verify Email
            </Button>
          </form>

          <p className="text-center text-dark-400 text-sm mt-6">
            Wrong email?{" "}
            <Link to="/register" className="text-primary-400 hover:text-primary-300 font-medium">
              Go back
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}