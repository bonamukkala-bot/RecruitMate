import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "react-hot-toast";
import { AuthProvider, useAuth } from "./context/AuthContext";

import DashboardLayout from "./components/layout/DashboardLayout";
import Login from "./pages/auth/Login";
import Register from "./pages/auth/Register";
import VerifyOTP from "./pages/auth/VerifyOTP";
import Dashboard from "./pages/dashboard/Dashboard";
import Jobs from "./pages/jobs/Jobs";
import JobDetail from "./pages/jobs/JobDetail";
import Candidates from "./pages/candidates/Candidates";
import CandidateDetail from "./pages/candidates/CandidateDetail";
import CandidateComparison from "./pages/candidates/CandidateComparison";
import Pipeline from "./pages/pipeline/Pipeline";
import InterviewPortal from "./pages/interview/InterviewPortal";
import Analytics from "./pages/analytics/Analytics";
import Heatmap from "./pages/analytics/Heatmap";

// ── Protected Route ───────────────────────────────────────────────────────────
function ProtectedRoute({ children }) {
  const { company, loading } = useAuth();
  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center bg-dark-950">
        <div className="animate-spin h-8 w-8 border-2 border-primary-500 border-t-transparent rounded-full" />
      </div>
    );
  }
  return company ? children : <Navigate to="/login" replace />;
}

// ── Public Route ──────────────────────────────────────────────────────────────
function PublicRoute({ children }) {
  const { company, loading } = useAuth();
  if (loading) return null;
  return company ? <Navigate to="/dashboard" replace /> : children;
}

// ── App ───────────────────────────────────────────────────────────────────────
export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Toaster
          position="top-right"
          toastOptions={{
            style: {
              background: "#1e293b",
              color      : "#fff",
              border     : "1px solid #334155"
            }
          }}
        />
        <Routes>
          {/* Public routes */}
          <Route path="/login"      element={<PublicRoute><Login /></PublicRoute>} />
          <Route path="/register"   element={<PublicRoute><Register /></PublicRoute>} />
          <Route path="/verify-otp" element={<PublicRoute><VerifyOTP /></PublicRoute>} />

          {/* Candidate-facing interview link — no auth required */}
          <Route path="/interview/:token" element={<InterviewPortal />} />

          {/* Protected routes */}
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <DashboardLayout />
              </ProtectedRoute>
            }
          >
            <Route index                  element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard"       element={<Dashboard />} />
            <Route path="jobs"            element={<Jobs />} />
            <Route path="jobs/:id"        element={<JobDetail />} />
            <Route path="candidates"      element={<Candidates />} />
            <Route path="candidates/compare" element={<CandidateComparison />} />
            <Route path="candidates/:id"  element={<CandidateDetail />} />
            <Route path="pipeline" element={<Pipeline />} />
          </Route>

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="heatmap" element={<Heatmap />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}