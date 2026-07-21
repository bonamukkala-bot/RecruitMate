import { useEffect } from "react";
import { useNavigate, Outlet } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";
import LoadingSpinner from "../ui/LoadingSpinner";

export default function DashboardLayout() {
  const { company, loading } = useAuth();
  const navigate             = useNavigate();

  useEffect(() => {
    if (!loading && !company) navigate("/login");
  }, [company, loading, navigate]);

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center bg-surface-50">
        <LoadingSpinner size="lg" text="Loading RecruitMate..." />
      </div>
    );
  }

  if (!company) return null;

  return (
    <div className="min-h-screen bg-surface-50">
      <Sidebar />
      <TopBar />
      <main className="ml-60 pt-14 min-h-screen">
        <div className="p-6 animate-fade-in">
          <Outlet />
        </div>
      </main>
    </div>
  );
}