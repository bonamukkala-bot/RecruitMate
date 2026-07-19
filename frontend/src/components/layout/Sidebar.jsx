import { NavLink, useNavigate } from "react-router-dom";
import { LayoutDashboard, Briefcase, Users, GitBranch, BarChart2, Flame, LogOut, Bot } from "lucide-react"
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

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <aside className="fixed left-0 top-0 h-screen w-60 bg-dark-950 border-r border-dark-800 flex flex-col z-40">

      {/* Logo */}
      <div className="p-6 border-b border-dark-800">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
            <Bot size={18} className="text-white" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-white">RecruitMate</h1>
            <p className="text-xs text-dark-400">AI Platform</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-1">
        {navItems.map(({ label, icon: Icon, path }) => (
          <NavLink
            key={path}
            to={path}
            className={({ isActive }) =>
              clsx(isActive ? "sidebar-item-active" : "sidebar-item")
            }
          >
            <Icon size={18} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Company info + Logout */}
      <div className="p-4 border-t border-dark-800">
        <div className="mb-3 px-3">
          <p className="text-xs font-medium text-white truncate">
            {company?.company_name}
          </p>
          <p className="text-xs text-dark-400 truncate">{company?.email}</p>
        </div>
        <button
          onClick={handleLogout}
          className="sidebar-item w-full text-red-400 hover:text-red-300 hover:bg-red-500/10"
        >
          <LogOut size={18} />
          <span>Logout</span>
        </button>
      </div>
    </aside>
  );
}