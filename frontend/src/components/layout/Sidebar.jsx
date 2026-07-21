import { NavLink, useNavigate } from "react-router-dom";
import {
  LayoutDashboard, Briefcase, Users,
  GitBranch, BarChart2, Flame, LogOut, Bot
} from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import clsx from "clsx";

const navItems = [
  { label: "Dashboard",  icon: LayoutDashboard, path: "/dashboard"  },
  { label: "Jobs",       icon: Briefcase,        path: "/jobs"       },
  { label: "Candidates", icon: Users,            path: "/candidates" },
  { label: "Pipeline",   icon: GitBranch,        path: "/pipeline"   },
  { label: "Analytics",  icon: BarChart2,        path: "/analytics"  },
  { label: "Heatmap",    icon: Flame,            path: "/heatmap"    }
];

export default function Sidebar() {
  const { company, logout } = useAuth();
  const navigate            = useNavigate();

  return (
    <aside className="fixed left-0 top-0 h-screen w-60 bg-ink-500 border-r border-ink-600 flex flex-col z-40">

      {/* Logo */}
      <div className="p-5 border-b border-ink-400/40">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-gold-500 rounded-xl flex items-center justify-center shadow-card">
            <Bot size={18} className="text-ink-700" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-white font-display">RecruitMate</h1>
            <p className="text-xs text-ink-200 font-medium">AI Platform</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 p-3 space-y-0.5">
        <p className="text-xs font-semibold uppercase tracking-widest text-ink-200 px-3 py-2">Main Menu</p>
        {navItems.map(({ label, icon: Icon, path }) => (
          <NavLink
            key={path}
            to={path}
            className={({ isActive }) =>
              clsx(
                "flex items-center gap-3 px-3 py-2.5 rounded-r-xl rounded-l-none text-sm transition-all duration-150",
                isActive
                  ? "text-gold-200 bg-white/[0.06] border-l-2 border-gold-500 font-semibold"
                  : "text-ink-100 hover:text-white hover:bg-white/[0.04] border-l-2 border-transparent font-medium"
              )
            }
          >
            <Icon size={17} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="p-3 border-t border-ink-400/40 space-y-1">
        <div className="px-3 py-2">
          <p className="text-xs font-semibold text-white truncate">{company?.company_name}</p>
          <p className="text-xs text-ink-200 truncate">{company?.email}</p>
        </div>
        <button
          onClick={() => { logout(); navigate("/login"); }}
          className="flex items-center gap-3 px-3 py-2.5 rounded-xl w-full text-sm font-medium
                     text-brick-300 hover:text-brick-100 hover:bg-brick-900/40 transition-all duration-150"
        >
          <LogOut size={17} />
          <span>Logout</span>
        </button>
      </div>
    </aside>
  );
}