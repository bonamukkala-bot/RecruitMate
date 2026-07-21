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
    <aside className="fixed left-0 top-0 h-screen w-60 bg-white border-r border-gray-200 flex flex-col z-40">

      {/* Logo */}
      <div className="p-5 border-b border-gray-100">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-indigo-600 rounded-xl flex items-center justify-center shadow-sm shadow-indigo-200">
            <Bot size={18} className="text-white" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-gray-900">RecruitMate</h1>
            <p className="text-xs text-gray-400 font-medium">AI Platform</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 p-3 space-y-0.5">
        <p className="section-label px-3 py-2">Main Menu</p>
        {navItems.map(({ label, icon: Icon, path }) => (
          <NavLink
            key={path}
            to={path}
            className={({ isActive }) =>
              clsx(isActive ? "sidebar-item-active" : "sidebar-item")
            }
          >
            <Icon size={17} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="p-3 border-t border-gray-100 space-y-1">
        <div className="px-3 py-2">
          <p className="text-xs font-semibold text-gray-800 truncate">{company?.company_name}</p>
          <p className="text-xs text-gray-400 truncate">{company?.email}</p>
        </div>
        <button
          onClick={() => { logout(); navigate("/login"); }}
          className="sidebar-item w-full text-red-500 hover:text-red-600 hover:bg-red-50"
        >
          <LogOut size={17} />
          <span>Logout</span>
        </button>
      </div>
    </aside>
  );
}