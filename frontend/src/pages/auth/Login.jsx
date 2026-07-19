import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Mail, Lock, Bot } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import Input from "../../components/ui/Input";
import Button from "../../components/ui/Button";
import toast from "react-hot-toast";

export default function Login() {
  const [form, setForm]       = useState({ email: "", password: "" });
  const [loading, setLoading] = useState(false);
  const { login }             = useAuth();
  const navigate              = useNavigate();

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const data = await login(form.email, form.password);
      if (data.success) {
        toast.success(`Welcome back, ${data.company_name}!`);
        navigate("/dashboard");
      } else {
        toast.error(data.error || "Login failed");
      }
    } catch (err) {
      toast.error(err.response?.data?.error || "Login failed");
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
          <p className="text-dark-400 mt-1 text-sm">Sign in to your account</p>
        </div>

        {/* Card */}
        <div className="card border-dark-800 shadow-2xl">
          <form onSubmit={handleSubmit} className="space-y-4">
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
              Sign In
            </Button>
          </form>

          <p className="text-center text-dark-400 text-sm mt-6">
            Don't have an account?{" "}
            <Link to="/register" className="text-primary-400 hover:text-primary-300 font-medium">
              Register
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}