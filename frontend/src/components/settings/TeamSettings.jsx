import { useState, useEffect, useCallback } from "react";
import {
  Users, UserPlus, Mail, Shield, ShieldAlert, CheckCircle2,
  Clock, Trash2, RotateCcw, AlertTriangle, Activity, Edit2, UserX, UserCheck
} from "lucide-react";
import { settingsAPI } from "../../api/settings";
import useRole from "../../hooks/useRole";
import SettingsSection from "./SettingsSection";
import Button from "../../components/ui/Button";
import Input from "../../components/ui/Input";
import Modal from "../../components/ui/Modal";
import LoadingSpinner from "../../components/ui/LoadingSpinner";
import toast from "react-hot-toast";
import clsx from "clsx";

const ROLE_CONFIGS = {
  owner: {
    label: "Owner",
    color: "bg-purple-50 text-purple-700 border-purple-200",
    description: "Full control over organization, data deletion, billing, and team."
  },
  admin: {
    label: "Admin",
    color: "bg-blue-50 text-blue-700 border-blue-200",
    description: "Manage settings, team invites, reviews, and recruitment workflow."
  },
  recruiter: {
    label: "Recruiter",
    color: "bg-emerald-50 text-emerald-700 border-emerald-200",
    description: "Create jobs, screen candidates, schedule and conduct interviews."
  },
  viewer: {
    label: "Viewer",
    color: "bg-slate-100 text-slate-700 border-slate-200",
    description: "Read-only access to jobs, candidates, pipeline, and analytics."
  }
};

export default function TeamSettings() {
  const { isAdmin } = useRole();
  const [activeSubTab, setActiveSubTab] = useState("members"); // "members" | "activity"

  // ── Team Members State ─────────────────────────────────────────────────────
  const [members, setMembers] = useState([]);
  const [owner, setOwner] = useState(null);
  const [loadingMembers, setLoadingMembers] = useState(true);

  // ── Invite Modal State ─────────────────────────────────────────────────────
  const [inviteModalOpen, setInviteModalOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("recruiter");
  const [inviting, setInviting] = useState(false);

  // ── Change Role Modal State ────────────────────────────────────────────────
  const [roleModalOpen, setRoleModalOpen] = useState(false);
  const [selectedMember, setSelectedMember] = useState(null);
  const [newRole, setNewRole] = useState("recruiter");
  const [savingRole, setSavingRole] = useState(false);

  // ── Remove Confirmation Modal State ────────────────────────────────────────
  const [removeModalOpen, setRemoveModalOpen] = useState(false);
  const [memberToRemove, setMemberToRemove] = useState(null);
  const [removing, setRemoving] = useState(false);

  // ── Activity Log State ─────────────────────────────────────────────────────
  const [activityLogs, setActivityLogs] = useState([]);
  const [loadingActivity, setLoadingActivity] = useState(false);
  const [actionLoadingId, setActionLoadingId] = useState(null);

  // ── Fetch Members ──────────────────────────────────────────────────────────
  const fetchMembers = useCallback(async () => {
    try {
      const res = await settingsAPI.getTeamMembers();
      if (res.data?.success) {
        setMembers(res.data.members || []);
        setOwner(res.data.owner || null);
      }
    } catch (err) {
      toast.error(err.response?.data?.error || "Failed to load team members");
    } finally {
      setLoadingMembers(false);
    }
  }, []);

  // ── Fetch Activity Logs ────────────────────────────────────────────────────
  const fetchActivity = useCallback(async () => {
    if (!isAdmin) return;
    setLoadingActivity(true);
    try {
      const res = await settingsAPI.getAuditLogs(1, 100);
      if (res.data?.success) {
        setActivityLogs(res.data.logs || []);
      }
    } catch (err) {
      toast.error(err.response?.data?.error || "Failed to load activity logs");
    } finally {
      setLoadingActivity(false);
    }
  }, [isAdmin]);

  useEffect(() => {
    fetchMembers();
  }, [fetchMembers]);

  useEffect(() => {
    if (activeSubTab === "activity" && isAdmin) {
      fetchActivity();
    }
  }, [activeSubTab, isAdmin, fetchActivity]);

  // ── Invite Member ──────────────────────────────────────────────────────────
  const handleInvite = async (e) => {
    e.preventDefault();
    if (!inviteEmail.trim()) {
      toast.error("Please enter an email address");
      return;
    }
    setInviting(true);
    try {
      const res = await settingsAPI.inviteMember({
        email: inviteEmail.trim().toLowerCase(),
        role: inviteRole
      });
      if (res.data?.success) {
        toast.success(res.data.message || `Invitation sent to ${inviteEmail}`);
        setInviteModalOpen(false);
        setInviteEmail("");
        setInviteRole("recruiter");
        fetchMembers();
      } else {
        toast.error(res.data?.error || "Failed to send invitation");
      }
    } catch (err) {
      toast.error(err.response?.data?.error || "Failed to send invitation");
    } finally {
      setInviting(false);
    }
  };

  // ── Resend Invite ──────────────────────────────────────────────────────────
  const handleResendInvite = async (memberId) => {
    setActionLoadingId(memberId);
    try {
      const res = await settingsAPI.resendInvite(memberId);
      if (res.data?.success) {
        toast.success(res.data.message || "Invitation resent successfully");
        fetchMembers();
      } else {
        toast.error(res.data?.error || "Failed to resend invite");
      }
    } catch (err) {
      toast.error(err.response?.data?.error || "Failed to resend invite");
    } finally {
      setActionLoadingId(null);
    }
  };

  // ── Change Role ────────────────────────────────────────────────────────────
  const openRoleModal = (member) => {
    setSelectedMember(member);
    setNewRole(member.role);
    setRoleModalOpen(true);
  };

  const handleSaveRole = async (e) => {
    e.preventDefault();
    if (!selectedMember) return;
    setSavingRole(true);
    try {
      const res = await settingsAPI.updateMemberRole(selectedMember._id, newRole);
      if (res.data?.success) {
        toast.success(`Role updated to ${ROLE_CONFIGS[newRole]?.label || newRole}`);
        setRoleModalOpen(false);
        fetchMembers();
      } else {
        toast.error(res.data?.error || "Failed to update role");
      }
    } catch (err) {
      toast.error(err.response?.data?.error || "Failed to update role");
    } finally {
      setSavingRole(false);
    }
  };

  // ── Toggle Status (Enable/Disable) ─────────────────────────────────────────
  const handleToggleStatus = async (member) => {
    const newStatus = member.status === "active" ? "disabled" : "active";
    setActionLoadingId(member._id);
    try {
      const res = await settingsAPI.updateMemberStatus(member._id, newStatus);
      if (res.data?.success) {
        toast.success(
          newStatus === "active"
            ? "Team member activated"
            : "Team member disabled"
        );
        fetchMembers();
      } else {
        toast.error(res.data?.error || "Failed to change status");
      }
    } catch (err) {
      toast.error(err.response?.data?.error || "Failed to change status");
    } finally {
      setActionLoadingId(null);
    }
  };

  // ── Remove Member ──────────────────────────────────────────────────────────
  const openRemoveModal = (member) => {
    setMemberToRemove(member);
    setRemoveModalOpen(true);
  };

  const handleConfirmRemove = async () => {
    if (!memberToRemove) return;
    setRemoving(true);
    try {
      const res = await settingsAPI.removeMember(memberToRemove._id);
      if (res.data?.success) {
        toast.success("Team member removed");
        setRemoveModalOpen(false);
        setMemberToRemove(null);
        fetchMembers();
      } else {
        toast.error(res.data?.error || "Failed to remove member");
      }
    } catch (err) {
      toast.error(err.response?.data?.error || "Failed to remove member");
    } finally {
      setRemoving(false);
    }
  };

  const formatDate = (isoStr) => {
    if (!isoStr) return "Never";
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric"
      });
    } catch {
      return "—";
    }
  };

  const formatDateTime = (isoStr) => {
    if (!isoStr) return "—";
    try {
      const d = new Date(isoStr);
      return d.toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
        hour12: true
      });
    } catch {
      return "—";
    }
  };

  return (
    <div className="space-y-6">
      {/* Sub-tab Switcher */}
      <div className="flex items-center justify-between border-b border-stone-200 pb-3">
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setActiveSubTab("members")}
            className={clsx(
              "px-4 py-2 text-sm font-semibold rounded-xl transition-all flex items-center gap-2",
              activeSubTab === "members"
                ? "bg-ink-500 text-white shadow-card"
                : "text-stone-600 hover:text-ink-500 hover:bg-stone-100"
            )}
          >
            <Users size={16} />
            <span>Members & Roles</span>
            <span className={clsx(
              "text-xs px-2 py-0.5 rounded-full font-bold",
              activeSubTab === "members" ? "bg-white/20 text-white" : "bg-stone-200 text-stone-700"
            )}>
              {1 + members.length}
            </span>
          </button>

          {isAdmin && (
            <button
              type="button"
              onClick={() => setActiveSubTab("activity")}
              className={clsx(
                "px-4 py-2 text-sm font-semibold rounded-xl transition-all flex items-center gap-2",
                activeSubTab === "activity"
                  ? "bg-ink-500 text-white shadow-card"
                  : "text-stone-600 hover:text-ink-500 hover:bg-stone-100"
              )}
            >
              <Activity size={16} />
              <span>Activity Log</span>
            </button>
          )}
        </div>

        {activeSubTab === "members" && isAdmin && (
          <Button
            variant="primary"
            size="sm"
            onClick={() => setInviteModalOpen(true)}
            className="flex items-center gap-2"
          >
            <UserPlus size={15} />
            <span>Invite Member</span>
          </Button>
        )}
      </div>

      {/* ── SUB-TAB: MEMBERS & ROLES ────────────────────────────────────────── */}
      {activeSubTab === "members" && (
        <SettingsSection
          title="Team Members & Permissions"
          description="Manage who has access to your organization, assign role-based permissions, and invite collaborators."
        >
          {loadingMembers ? (
            <div className="py-12 flex flex-col items-center justify-center text-center space-y-3">
              <LoadingSpinner size="lg" />
              <p className="text-sm text-stone-500">Loading team roster...</p>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Members Table */}
              <div className="overflow-x-auto rounded-xl border border-stone-200 bg-white">
                <table className="w-full text-left text-sm">
                  <thead className="bg-stone-50 border-b border-stone-200 text-xs font-semibold text-stone-600 uppercase tracking-wider">
                    <tr>
                      <th className="py-3 px-4">Member</th>
                      <th className="py-3 px-4">Role</th>
                      <th className="py-3 px-4">Status</th>
                      <th className="py-3 px-4">Last Active</th>
                      <th className="py-3 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stone-100">
                    {/* Primary Owner Row (Pinned) */}
                    {owner && (
                      <tr className="bg-purple-50/20 hover:bg-purple-50/40 transition-colors">
                        <td className="py-3.5 px-4">
                          <div className="flex items-center gap-3">
                            <div className="w-9 h-9 rounded-full bg-purple-600 text-white font-bold text-xs flex items-center justify-center shadow-sm">
                              {(owner.name || owner.company_name || "O").charAt(0).toUpperCase()}
                            </div>
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="font-semibold text-ink-600">
                                  {owner.name || owner.company_name}
                                </span>
                                <span className="text-[10px] font-bold uppercase tracking-wider bg-purple-100 text-purple-800 px-1.5 py-0.5 rounded border border-purple-200">
                                  Primary Owner
                                </span>
                              </div>
                              <p className="text-xs text-stone-500">{owner.email}</p>
                            </div>
                          </div>
                        </td>
                        <td className="py-3.5 px-4">
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border bg-purple-50 text-purple-700 border-purple-200">
                            <Shield size={12} />
                            Owner
                          </span>
                        </td>
                        <td className="py-3.5 px-4">
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                            <CheckCircle2 size={12} />
                            Active
                          </span>
                        </td>
                        <td className="py-3.5 px-4 text-xs text-stone-500">
                          {formatDate(owner.last_login_at)}
                        </td>
                        <td className="py-3.5 px-4 text-right">
                          <span className="text-xs text-stone-400 italic">
                            Protected
                          </span>
                        </td>
                      </tr>
                    )}

                    {/* Team Members */}
                    {members.map((member) => {
                      const roleConfig = ROLE_CONFIGS[member.role] || ROLE_CONFIGS.viewer;
                      const isActionBusy = actionLoadingId === member._id;

                      return (
                        <tr key={member._id} className="hover:bg-stone-50/60 transition-colors">
                          <td className="py-3.5 px-4">
                            <div className="flex items-center gap-3">
                              <div className="w-9 h-9 rounded-full bg-stone-200 text-ink-600 font-bold text-xs flex items-center justify-center">
                                {(member.name || member.email).charAt(0).toUpperCase()}
                              </div>
                              <div>
                                <span className="font-semibold text-ink-600 block">
                                  {member.name || "Invited Member"}
                                </span>
                                <p className="text-xs text-stone-500">{member.email}</p>
                              </div>
                            </div>
                          </td>
                          <td className="py-3.5 px-4">
                            <span className={clsx(
                              "inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold border",
                              roleConfig.color
                            )}>
                              {roleConfig.label}
                            </span>
                          </td>
                          <td className="py-3.5 px-4">
                            {member.status === "active" && (
                              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                                <CheckCircle2 size={12} />
                                Active
                              </span>
                            )}
                            {member.status === "invited" && (
                              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                                <Clock size={12} />
                                Invited
                              </span>
                            )}
                            {member.status === "disabled" && (
                              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
                                <ShieldAlert size={12} />
                                Disabled
                              </span>
                            )}
                          </td>
                          <td className="py-3.5 px-4 text-xs text-stone-500">
                            {member.status === "invited"
                              ? `Invited ${formatDate(member.created_at)}`
                              : formatDate(member.last_login_at)}
                          </td>
                          <td className="py-3.5 px-4 text-right">
                            {isAdmin ? (
                              <div className="flex items-center justify-end gap-1.5">
                                {member.status === "invited" && (
                                  <button
                                    type="button"
                                    onClick={() => handleResendInvite(member._id)}
                                    disabled={isActionBusy}
                                    title="Resend invitation link"
                                    className="p-1.5 text-stone-500 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
                                  >
                                    <RotateCcw size={15} />
                                  </button>
                                )}

                                <button
                                  type="button"
                                  onClick={() => openRoleModal(member)}
                                  disabled={isActionBusy}
                                  title="Change role"
                                  className="p-1.5 text-stone-500 hover:text-ink-600 hover:bg-stone-100 rounded-lg transition-colors"
                                >
                                  <Edit2 size={15} />
                                </button>

                                {member.status !== "invited" && (
                                  <button
                                    type="button"
                                    onClick={() => handleToggleStatus(member)}
                                    disabled={isActionBusy}
                                    title={member.status === "active" ? "Disable account" : "Enable account"}
                                    className={clsx(
                                      "p-1.5 rounded-lg transition-colors",
                                      member.status === "active"
                                        ? "text-stone-500 hover:text-amber-600 hover:bg-amber-50"
                                        : "text-stone-500 hover:text-emerald-600 hover:bg-emerald-50"
                                    )}
                                  >
                                    {member.status === "active" ? <UserX size={15} /> : <UserCheck size={15} />}
                                  </button>
                                )}

                                <button
                                  type="button"
                                  onClick={() => openRemoveModal(member)}
                                  disabled={isActionBusy}
                                  title="Remove member"
                                  className="p-1.5 text-stone-500 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors"
                                >
                                  <Trash2 size={15} />
                                </button>
                              </div>
                            ) : (
                              <span className="text-xs text-stone-400">—</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}

                    {members.length === 0 && (
                      <tr>
                        <td colSpan={5} className="py-8 text-center text-stone-500 text-sm">
                          No team members added yet. Invite your colleagues to collaborate!
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              {/* Roles Summary Reference Box */}
              <div className="bg-stone-50 border border-stone-200 rounded-xl p-4">
                <h4 className="text-xs font-bold text-ink-600 uppercase tracking-wider mb-2">
                  Role Permissions Reference
                </h4>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
                  {Object.entries(ROLE_CONFIGS).map(([key, item]) => (
                    <div key={key} className="bg-white p-3 rounded-lg border border-stone-200">
                      <div className="flex items-center gap-1.5 font-bold text-ink-600 mb-1">
                        <span className={clsx("w-2 h-2 rounded-full", item.color)} />
                        <span>{item.label}</span>
                      </div>
                      <p className="text-stone-500 leading-relaxed">{item.description}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </SettingsSection>
      )}

      {/* ── SUB-TAB: AUDIT ACTIVITY LOG ─────────────────────────────────────── */}
      {activeSubTab === "activity" && isAdmin && (
        <SettingsSection
          title="Organization Activity & Audit Logs"
          description="Detailed trail of sensitive actions taken across settings, candidate management, approvals, and team invitations."
        >
          {loadingActivity ? (
            <div className="py-12 flex flex-col items-center justify-center text-center space-y-3">
              <LoadingSpinner size="lg" />
              <p className="text-sm text-stone-500">Loading audit history...</p>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center justify-between text-xs text-stone-500">
                <span>Showing recent audit records (up to 100 events)</span>
                <Button variant="secondary" size="sm" onClick={fetchActivity}>
                  Refresh Trail
                </Button>
              </div>

              <div className="overflow-x-auto rounded-xl border border-stone-200 bg-white">
                <table className="w-full text-left text-sm">
                  <thead className="bg-stone-50 border-b border-stone-200 text-xs font-semibold text-stone-600 uppercase tracking-wider">
                    <tr>
                      <th className="py-3 px-4">Timestamp</th>
                      <th className="py-3 px-4">Actor</th>
                      <th className="py-3 px-4">Action</th>
                      <th className="py-3 px-4">Target / Context</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stone-100 font-mono text-xs">
                    {activityLogs.map((log) => (
                      <tr key={log._id} className="hover:bg-stone-50/60 transition-colors">
                        <td className="py-2.5 px-4 text-stone-500 whitespace-nowrap">
                          {formatDateTime(log.ts)}
                        </td>
                        <td className="py-2.5 px-4 font-sans">
                          <div className="flex items-center gap-1.5">
                            <span className="font-medium text-ink-600">
                              {log.actor?.email || "System"}
                            </span>
                            {log.actor?.role && (
                              <span className="text-[10px] uppercase font-bold px-1.5 py-0.2 rounded bg-stone-100 text-stone-600">
                                {log.actor.role}
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="py-2.5 px-4">
                          <span className="px-2 py-0.5 rounded font-semibold text-[11px] bg-indigo-50 text-indigo-700 border border-indigo-100">
                            {log.action}
                          </span>
                        </td>
                        <td className="py-2.5 px-4 text-stone-600 max-w-xs truncate" title={JSON.stringify(log.target || {})}>
                          {log.target ? (
                            <span>
                              {log.target.section && `Section: ${log.target.section}`}
                              {log.target.email && `Email: ${log.target.email}`}
                              {log.target.role && ` -> ${log.target.role}`}
                              {log.target.status && ` -> ${log.target.status}`}
                              {log.target.candidate_id && `Cand: ${log.target.candidate_id}`}
                              {log.target.job_id && `Job: ${log.target.job_id}`}
                              {log.target.title && ` "${log.target.title}"`}
                            </span>
                          ) : (
                            "—"
                          )}
                        </td>
                      </tr>
                    ))}

                    {activityLogs.length === 0 && (
                      <tr>
                        <td colSpan={4} className="py-8 text-center text-stone-500 font-sans text-sm">
                          No audit events recorded yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </SettingsSection>
      )}

      {/* ── MODAL: INVITE MEMBER ────────────────────────────────────────────── */}
      <Modal
        isOpen={inviteModalOpen}
        onClose={() => setInviteModalOpen(false)}
        title="Invite Team Member"
        size="md"
        footer={
          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="secondary"
              onClick={() => setInviteModalOpen(false)}
              disabled={inviting}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="primary"
              onClick={handleInvite}
              loading={inviting}
            >
              Send Invitation
            </Button>
          </div>
        }
      >
        <form onSubmit={handleInvite} className="space-y-4">
          <Input
            label="Work Email Address"
            name="inviteEmail"
            type="email"
            placeholder="colleague@company.com"
            icon={Mail}
            value={inviteEmail}
            onChange={(e) => setInviteEmail(e.target.value)}
            required
            autoFocus
          />

          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-ink-500">
              Assigned Role
            </label>
            <select
              value={inviteRole}
              onChange={(e) => setInviteRole(e.target.value)}
              className="w-full px-3 py-2 text-sm bg-stone-50 border border-stone-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="admin">Admin — Manage settings, team & reviews</option>
              <option value="recruiter">Recruiter — Post jobs, interview & screen candidates</option>
              <option value="viewer">Viewer — Read-only access</option>
            </select>
            <p className="text-xs text-stone-500 mt-1">
              {ROLE_CONFIGS[inviteRole]?.description}
            </p>
          </div>

          <div className="p-3 bg-indigo-50/70 border border-indigo-100 rounded-xl text-xs text-indigo-700 space-y-1">
            <p className="font-semibold">How it works:</p>
            <p>
              An invitation email will be delivered with a secure 72-hour link. The invitee will set their own name and password to activate their account.
            </p>
          </div>
        </form>
      </Modal>

      {/* ── MODAL: CHANGE ROLE ──────────────────────────────────────────────── */}
      <Modal
        isOpen={roleModalOpen}
        onClose={() => setRoleModalOpen(false)}
        title={`Change Role: ${selectedMember?.name || selectedMember?.email}`}
        size="sm"
        footer={
          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="secondary"
              onClick={() => setRoleModalOpen(false)}
              disabled={savingRole}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="primary"
              onClick={handleSaveRole}
              loading={savingRole}
            >
              Update Role
            </Button>
          </div>
        }
      >
        <form onSubmit={handleSaveRole} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-ink-500">
              Select Role
            </label>
            <select
              value={newRole}
              onChange={(e) => setNewRole(e.target.value)}
              className="w-full px-3 py-2 text-sm bg-stone-50 border border-stone-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="admin">Admin</option>
              <option value="recruiter">Recruiter</option>
              <option value="viewer">Viewer</option>
            </select>
            <p className="text-xs text-stone-500 mt-2">
              {ROLE_CONFIGS[newRole]?.description}
            </p>
          </div>
        </form>
      </Modal>

      {/* ── MODAL: REMOVE MEMBER CONFIRMATION ────────────────────────────────── */}
      <Modal
        isOpen={removeModalOpen}
        onClose={() => setRemoveModalOpen(false)}
        title="Remove Team Member"
        size="sm"
        footer={
          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="secondary"
              onClick={() => setRemoveModalOpen(false)}
              disabled={removing}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="danger"
              onClick={handleConfirmRemove}
              loading={removing}
            >
              Remove Member
            </Button>
          </div>
        }
      >
        <div className="space-y-3">
          <div className="flex items-center gap-3 p-3 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-xs">
            <AlertTriangle size={20} className="shrink-0 text-rose-600" />
            <p>
              Are you sure you want to remove <strong>{memberToRemove?.email}</strong> from your organization? They will immediately lose all access.
            </p>
          </div>
        </div>
      </Modal>
    </div>
  );
}
