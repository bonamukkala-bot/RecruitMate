import { useState, useEffect } from "react";
import { ShieldCheck, ShieldOff } from "lucide-react";
import { authAPI } from "../../api/auth";
import Input from "../../components/ui/Input";
import Button from "../../components/ui/Button";
import toast from "react-hot-toast";

export default function Settings() {
  const [qrCode, setQrCode]     = useState(null);
  const [secret, setSecret]     = useState(null);
  const [code, setCode]         = useState("");
  const [enabled, setEnabled]   = useState(false);
  const [loading, setLoading]         = useState(false);
  const [statusLoading, setStatusLoading] = useState(true);
  const [showDisableForm, setShowDisableForm] = useState(false);
  const [disablePassword, setDisablePassword] = useState("");

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await authAPI.get2FAStatus();
        setEnabled(res.data.enabled);
      } catch (err) {
        toast.error(err.response?.data?.error || "Could not fetch 2FA status");
      } finally {
        setStatusLoading(false);
      }
    };
    fetchStatus();
  }, []);

  // Step A: recruiter clicks "Enable 2FA" — fetch QR code
  const handleStartSetup = async () => {
    setLoading(true);
    try {
      const res = await authAPI.setup2FA();
      if (res.data.success) {
        setQrCode(res.data.qr_code);
        setSecret(res.data.secret);
      } else {
        toast.error(res.data.error || "Could not start 2FA setup");
      }
    } catch (err) {
      toast.error(err.response?.data?.error || "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  // Step B: recruiter scans QR, types the 6-digit code back to confirm
  const handleConfirm = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await authAPI.enable2FA(code);
      if (res.data.success) {
        toast.success("2FA enabled successfully!");
        setEnabled(true);
        setQrCode(null);
      } else {
        toast.error(res.data.error || "Invalid code");
      }
    } catch (err) {
      toast.error(err.response?.data?.error || "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  const handleDisable = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await authAPI.disable2FA(disablePassword);
      if (res.data.success) {
        toast.success("2FA disabled successfully");
        setEnabled(false);
        setShowDisableForm(false);
        setDisablePassword("");
        setQrCode(null);
      } else {
        toast.error(res.data.error || "Failed to disable 2FA");
      }
    } catch (err) {
      toast.error(err.response?.data?.error || "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-xl mx-auto p-6">
      <h1 className="text-2xl font-bold text-gray-900 mb-1">Security Settings</h1>
      <p className="text-gray-500 text-sm mb-6">Manage two-factor authentication for your account</p>

      <div className="bg-white rounded-2xl border border-gray-200 shadow-card-md p-6">
        {statusLoading ? (
          <p className="text-gray-500">Loading 2FA status...</p>
        ) : enabled ? (
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3 text-green-700">
              <ShieldCheck size={24} />
              <div>
                <p className="font-semibold">2FA is enabled</p>
                <p className="text-sm text-gray-500">Your account requires a code at every login.</p>
              </div>
            </div>
            {!showDisableForm ? (
              <Button onClick={() => setShowDisableForm(true)} variant="danger" loading={loading}>
                Disable 2FA
              </Button>
            ) : (
              <form onSubmit={handleDisable} className="space-y-3">
                <Input
                  label="Enter your current password"
                  name="password"
                  type="password"
                  value={disablePassword}
                  onChange={(e) => setDisablePassword(e.target.value)}
                  required
                />
                <div className="flex gap-2">
                  <Button type="submit" loading={loading} className="flex-1 justify-center">
                    Confirm Disable
                  </Button>
                  <Button type="button" onClick={() => { setShowDisableForm(false); setDisablePassword(""); }} variant="secondary">
                    Cancel
                  </Button>
                </div>
              </form>
            )}
          </div>
        ) : !qrCode ? (
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <ShieldOff size={24} className="text-gray-400" />
              <div>
                <p className="font-semibold text-gray-900">2FA is off</p>
                <p className="text-sm text-gray-500">Add an extra layer of protection to your login.</p>
              </div>
            </div>
            <Button onClick={handleStartSetup} loading={loading}>
              Enable 2FA
            </Button>
          </div>
        ) : (
          <div className="space-y-4">
            <p className="text-sm text-gray-600">
              Scan this QR code with Google Authenticator, Authy, or any TOTP app:
            </p>
            <img src={qrCode} alt="2FA QR code" className="mx-auto border rounded-lg" />
            <p className="text-xs text-gray-400 text-center">
              Can't scan? Enter this code manually: <span className="font-mono">{secret}</span>
            </p>

            <form onSubmit={handleConfirm} className="space-y-3">
              <Input
                label="Enter the 6-digit code from your app"
                name="code"
                type="text"
                placeholder="000000"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                maxLength={6}
                required
              />
              <Button type="submit" loading={loading} className="w-full justify-center">
                Confirm & Enable
              </Button>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}