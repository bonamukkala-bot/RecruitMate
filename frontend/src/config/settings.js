import {
  ShieldCheck, Briefcase, Mic, Mail,
  Bot, Users, Building2, Lock, Webhook
} from "lucide-react";

/**
 * Array of active/enabled tab IDs.
 * Only tabs included in this array will be visible in the Settings navigation.
 * To enable a tab in future phases, simply add its ID to this array.
 */
export const ENABLED_TABS = [
  "security",
  "hiring",
  "interview",
  "email",
  "ai",
  "team",
  "company",
  "privacy"
];

export const SETTINGS_TABS = [
  {
    id: "security",
    label: "Security",
    icon: ShieldCheck,
    description: "Two-factor authentication & account protection"
  },
  {
    id: "hiring",
    label: "Hiring Rules",
    icon: Briefcase,
    description: "Score thresholds, weights & approval workflows"
  },
  {
    id: "interview",
    label: "Interview",
    icon: Mic,
    description: "Question quotas, difficulty & proctoring integrity"
  },
  {
    id: "email",
    label: "Email",
    icon: Mail,
    description: "Sender profile, templates & automated alerts"
  },
  {
    id: "ai",
    label: "AI",
    icon: Bot,
    description: "Groq model selection, tone, temperature & usage tracking",
    subSections: ["Models", "Usage"]
  },
  {
    id: "team",
    label: "Team & Roles",
    icon: Users,
    description: "Team invitations, roles & access permissions"
  },
  {
    id: "company",
    label: "Company",
    icon: Building2,
    description: "Public employer branding, logo & candidate theme"
  },
  {
    id: "privacy",
    label: "Privacy",
    icon: Lock,
    description: "Data retention windows & interview consent"
  },
  {
    id: "integrations",
    label: "Integrations",
    icon: Webhook,
    description: "Slack notifications, webhooks & calendar sync"
  }
];
