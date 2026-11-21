import { useState, useEffect } from "react";
import { useSearchParams, useNavigate, Link } from "react-router-dom";
import { Bot, User, Lock, CheckCircle2, AlertCircle } from "lucide-react";
import { authAPI } from "../../api/auth";
import Input from "../../components/ui/Input";
import Button from "../../components/ui/Button";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import toast from "react-hot-toast";

export default function AcceptInvite() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const navigate = useNavigate();

  const [verifying, setVerifying] = useState(true);
  const [inviteData, setInviteData] = useState(null);
  const [verifyError, setVerifyError] = useState("");

  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");

  useEffect(() => {
    if (!token) {
      setVerifying(false);
      setVerifyError("No invitation token provided. Please check your invitation link.");
      return;
    }

    const checkToken = async () => {
      try {
        const res = await authAPI.verifyInvite(token);
        if (res.data?.success) {
          setInviteData(res.data);
          if (res.data.name) setName(res.data.name);
        } else {
          setVerifyError(res.data?.error || "This invitation link is invalid or has expired.");
        }
      } catch (err) {
        setVerifyError(
          err.response?.data?.error ||
          "This invitation link is invalid or has expired. Please ask your administrator to send a new invite."
        );
      } finally {
        setVerifying(false);
      }
    };

    checkToken();
  }, [token]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitError("");

    if (!name.trim()) {
      setSubmitError("Please enter your full name.");
      return;
    }

    if (password.length < 8) {
      setSubmitError("Password must be at least 8 characters long.");
      return;
    }

    if (password !== confirmPassword) {
      setSubmitError("Passwords do not match.");
      return;
    }

    setSubmitting(true);
    try {
      const res = await authAPI.acceptInvite({
        token,
        name: name.trim(),
        password
      });

      if (res.data?.success) {
        toast.success("Account activated successfully! Please sign in.");
        navigate("/login");
      } else {
        setSubmitError(res.data?.error || "Failed to accept invitation.");
        toast.error(res.data?.error || "Failed to accept invitation.");
      }
    } catch (err) {
      const msg = err.response?.data?.error || "Failed to accept invitation. The link may have expired.";
      setSubmitError(msg);
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-surface-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 right-0 w-96 h-96 bg-indigo-100 rounded-full blur-3xl opacity-40 -translate-y-1/2 translate-x-1/2" />
        <div className="absolute bottom-0 left-0 w-80 h-80 bg-violet-100 rounded-full blur-3xl opacity-30 translate-y-1/2 -translate-x-1/2" />
      </div>

      <div className="w-full max-w-md relative">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 bg-indigo-600 rounded-2xl mb-4 shadow-lg shadow-indigo-200">
            <Bot size={28} className="text-white" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">RecruitMate AI</h1>
          <p className="text-gray-500 mt-1 text-sm font-medium">
            Team Member Invitation
          </p>
        </div>

        <div className="bg-white rounded-2xl border border-gray-200 shadow-card-md p-8">
          {verifying ? (
            <div className="py-12 flex flex-col items-center justify-center text-center space-y-3">
              <LoadingSpinner size="lg" />
              <p className="text-sm text-stone-500">Verifying invitation link...</p>
            </div>
          ) : verifyError ? (
            <div className="space-y-6 text-center py-4">
              <div className="w-12 h-12 rounded-full bg-rose-50 text-rose-600 mx-auto flex items-center justify-center">
                <AlertCircle size={24} />
              </div>
              <div className="space-y-2">
                <h3 className="text-base font-semibold text-gray-900">Invalid or Expired Link</h3>
                <p className="text-sm text-gray-500 leading-relaxed">
                  {verifyError}
                </p>
              </div>
              <Link to="/login">
                <Button variant="secondary" className="w-full justify-center">
                  Back to Sign In
                </Button>
              </Link>
            </div>
          ) : (
            <div>
              <div className="mb-6 p-4 bg-indigo-50/70 border border-indigo-100 rounded-xl space-y-1">
                <div className="flex items-center gap-2 text-indigo-900 font-semibold text-sm">
                  <CheckCircle2 size={16} className="text-indigo-600" />
                  <span>Join {inviteData?.company_name}</span>
                </div>
                <p className="text-xs text-indigo-700">
                  You are accepting an invitation for <strong className="font-semibold">{inviteData?.email}</strong> with role <span className="uppercase font-semibold tracking-wider text-[11px] bg-indigo-100 text-indigo-800 px-1.5 py-0.5 rounded">{inviteData?.role}</span>.
                </p>
              </div>

              {submitError && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl">
                  {submitError}
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                <Input
                  label="Your Full Name"
                  name="name"
                  type="text"
                  placeholder="Jane Doe"
                  icon={User}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />

                <Input
                  label="Create Password"
                  name="password"
                  type="password"
                  placeholder="Min. 8 characters"
                  icon={Lock}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />

                <Input
                  label="Confirm Password"
                  name="confirmPassword"
                  type="password"
                  placeholder="Re-enter password"
                  icon={Lock}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                />

                <Button
                  type="submit"
                  loading={submitting}
                  className="w-full justify-center mt-2"
                >
                  Activate Account
                </Button>
              </form>

              <div className="mt-6 text-center">
                <Link to="/login" className="text-xs text-stone-500 hover:text-ink-500 font-medium transition-colors">
                  Already have an account? Sign In
                </Link>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
