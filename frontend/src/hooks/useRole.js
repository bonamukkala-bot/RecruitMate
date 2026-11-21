import { useAuth } from "../context/AuthContext";

const ROLE_HIERARCHY = {
  owner: 4,
  admin: 3,
  recruiter: 2,
  viewer: 1
};

export function useRole() {
  const { company } = useAuth();
  const role = (company?.role || "owner").toLowerCase();

  const userLevel = ROLE_HIERARCHY[role] ?? 1;

  const hasMinRole = (minRole) => {
    const requiredLevel = ROLE_HIERARCHY[minRole?.toLowerCase()] ?? 99;
    return userLevel >= requiredLevel;
  };

  return {
    role,
    isOwner: role === "owner",
    isAdmin: role === "admin" || role === "owner",
    isRecruiter: hasMinRole("recruiter"),
    isViewer: role === "viewer",
    hasMinRole
  };
}

export default useRole;
