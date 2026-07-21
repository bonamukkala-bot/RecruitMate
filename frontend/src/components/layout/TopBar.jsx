// TopBar.jsx
import { useLocation } from "react-router-dom";
import { Bell } from "lucide-react";
import { useAuth } from "../../context/AuthContext";

const pageTitles = {
  "/dashboard" : { title: "Dashboard",  subtitle: "Overview of your recruitment pipeline" },
  "/jobs"      : { title: "Jobs",        subtitle: "Manage your job postings"               },
  "/candidates": { title: "Candidates",  subtitle: "View and manage all candidates"         },
  "/pipeline"  : { title: "Pipeline",    subtitle: "AI agent pipeline management"           },
  "/analytics" : { title: "Analytics",   subtitle: "Recruitment performance insights"       },
  "/heatmap"   : { title: "Heatmap",     subtitle: "Interview performance analysis"         }
};

export default function TopBar() {
  const { pathname } = useLocation();
  const { company }  = useAuth();

  const page = Object.entries(pageTitles).find(([p]) =>
    pathname.startsWith(p)
  )?.[1] || { title: "RecruitMate", subtitle: "" };

  return (
    <header className="fixed top-0 left-60 right-0 h-14 bg-white/80 backdrop-blur-md border-b border-stone-200 flex items-center justify-between px-6 z-30">
      <div>
        <h2 className="text-sm font-bold text-ink-500 font-display">{page.title}</h2>
        <p className="text-xs text-stone-500">{page.subtitle}</p>
      </div>
      <div className="flex items-center gap-3">
        <button className="w-8 h-8 flex items-center justify-center rounded-lg text-stone-500 hover:text-ink-500 hover:bg-stone-100 transition-all">
          <Bell size={16} />
        </button>
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-full bg-ledger-500 flex items-center justify-center text-white text-xs font-bold shadow-card">
            {company?.company_name?.charAt(0).toUpperCase() || "R"}
          </div>
          <span className="text-sm font-medium text-ink-400 hidden md:block">
            {company?.company_name}
          </span>
        </div>
      </div>
    </header>
  );
}