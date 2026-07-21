import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Mail, Lock, Building2, User, Bot } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import Input from "../../components/ui/Input";
import Button from "../../components/ui/Button";
import toast from "react-hot-toast";

export default function Register() {
  const [form, setForm] = useState({ email: "", password: "", company_name: "", full_name: "" });
  const [loading, setLoading] = useState(false);
  const { register } = useAuth();
  const navigate     = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const data = await register(form);
      if (data.success) {
        toast.success("Registration successful! Check your email for OTP.");
        navigate("/verify-otp", { state: { email: form.email } });
      } else {
        toast.error(data.error || "Registration failed");
      }
    } catch (err) {
      toast.error(err.response?.data?.error || "Registration failed");
    } finally {
      setLoading(false);
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
          <p className="text-gray-500 mt-1 text-sm font-medium">Create your company account</p>
        </div>

        <div className="bg-white rounded-2xl border border-gray-200 shadow-card-md p-8">
          <form onSubmit={handleSubmit} className="space-y-4">
            <Input label="Full Name" name="full_name" placeholder="John Doe" icon={User}
              value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required />
            <Input label="Company Name" name="company_name" placeholder="Acme Corp" icon={Building2}
              value={form.company_name} onChange={(e) => setForm({ ...form, company_name: e.target.value })} required />
            <Input label="Work Email" name="email" type="email" placeholder="you@company.com" icon={Mail}
              value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
            <Input label="Password" name="password" type="password" placeholder="••••••••" icon={Lock}
              value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
            <Button type="submit" loading={loading} className="w-full justify-center mt-2">
              Create Account
            </Button>
          </form>
          <p className="text-center text-gray-500 text-sm mt-6">
            Already have an account?{" "}
            <Link to="/login" className="text-indigo-600 hover:text-indigo-700 font-semibold">Sign In</Link>
          </p>
        </div>
      </div>
    </div>
  );
}