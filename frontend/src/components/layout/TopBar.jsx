import { useLocation } from "react-router-dom";
import { Bell, Search } from "lucide-react";
import { useAuth } from "../../context/AuthContext";

const pageTitles = {
  "/dashboard" : { title: "Dashboard",  subtitle: "Overview of your recruitment pipeline" },
  "/jobs"      : { title: "Jobs",        subtitle: "Manage your job postings"               },
  "/candidates": { title: "Candidates",  subtitle: "View and manage candidates"             },
  "/pipeline"  : { title: "Pipeline",    subtitle: "AI agent pipeline management"           }
};

export default function TopBar() {
  const { pathname } = useLocation();
  const { company }  = useAuth();

  const page = Object.entries(pageTitles).find(([path]) =>
    pathname.startsWith(path)
  )?.[1] || { title: "RecruitMate", subtitle: "" };

  return (
    <header className="fixed top-0 left-60 right-0 h-16 bg-dark-950/80 backdrop-blur-sm border-b border-dark-800 flex items-center justify-between px-6 z-30">

      {/* Left — Page title */}
      <div>
        <h2 className="text-sm font-semibold text-white">{page.title}</h2>
        <p className="text-xs text-dark-400">{page.subtitle}</p>
      </div>

      {/* Right — Actions */}
      <div className="flex items-center gap-3">
        {/* Notification bell */}
        <button className="w-8 h-8 flex items-center justify-center rounded-lg text-dark-400 hover:text-white hover:bg-dark-800 transition-all">
          <Bell size={16} />
        </button>

        {/* Avatar */}
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-primary-600 flex items-center justify-center text-white text-xs font-bold">
            {company?.company_name?.charAt(0).toUpperCase() || "R"}
          </div>
          <span className="text-sm text-dark-300 hidden md:block">
            {company?.company_name}
          </span>
        </div>
      </div>
    </header>
  );
}