import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Mail, Lock, Building2, User, Bot } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import Input from "../../components/ui/Input";
import Button from "../../components/ui/Button";
import toast from "react-hot-toast";

export default function Register() {
  const [form, setForm] = useState({
    email       : "",
    password    : "",
    company_name: "",
    full_name   : ""
  });
  const [loading, setLoading] = useState(false);
  const { register }          = useAuth();
  const navigate              = useNavigate();

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

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
          <h1 className="text-2xl font-bold text-white">RecruitMate AI</h1>
          <p className="text-dark-400 mt-1 text-sm">Create your company account</p>
        </div>

        {/* Card */}
        <div className="card border-dark-800 shadow-2xl">
          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="Full Name"
              name="full_name"
              type="text"
              placeholder="John Doe"
              icon={User}
              value={form.full_name}
              onChange={handleChange}
              required
            />
            <Input
              label="Company Name"
              name="company_name"
              type="text"
              placeholder="Acme Corp"
              icon={Building2}
              value={form.company_name}
              onChange={handleChange}
              required
            />
            <Input
              label="Work Email"
              name="email"
              type="email"
              placeholder="you@company.com"
              icon={Mail}
              value={form.email}
              onChange={handleChange}
              required
            />
            <Input
              label="Password"
              name="password"
              type="password"
              placeholder="••••••••"
              icon={Lock}
              value={form.password}
              onChange={handleChange}
              required
            />

            <Button
              type="submit"
              loading={loading}
              className="w-full justify-center mt-2"
            >
              Create Account
            </Button>
          </form>

          <p className="text-center text-dark-400 text-sm mt-6">
            Already have an account?{" "}
            <Link to="/login" className="text-primary-400 hover:text-primary-300 font-medium">
              Sign In
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}