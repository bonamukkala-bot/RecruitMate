import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import IntegrationsSettings from "./components/settings/IntegrationsSettings";
import { settingsAPI } from "./api/settings";

jest.mock("./context/SettingsContext", () => ({
  useSettings: () => ({
    settings: {
      integrations: {
        slack_webhook_url: "",
        slack_events: { new_candidate: false, interview_complete: false, pending_review: false },
        webhook_url: "",
        webhook_events: [],
        google_calendar_enabled: false
      }
    },
    loading: false,
    updateSection: jest.fn().mockResolvedValue({ success: true }),
    resetSection: jest.fn().mockResolvedValue({ success: true })
  })
}));

jest.mock("./hooks/useRole", () => () => ({
  role: "owner",
  isAdmin: true,
  isOwner: true,
  isRecruiter: true,
  isViewer: false,
  hasMinRole: () => true
}));

jest.mock("./api/settings", () => ({
  settingsAPI: {
    getWebhooks: jest.fn().mockResolvedValue({ data: { success: true, webhooks: [] } }),
    getApiKeys: jest.fn().mockResolvedValue({
      data: {
        success: true,
        api_keys: [
          {
            id: "key_1",
            name: "Existing ATS Key",
            key_prefix: "rm_live_abc1...",
            scopes: ["read:candidates"],
            revoked: false,
            created_at: "2026-11-20T12:00:00Z"
          }
        ]
      }
    }),
    createApiKey: jest.fn(),
    revokeApiKey: jest.fn(),
    getGoogleStatus: jest.fn().mockResolvedValue({ data: { enabled: false, connected: false } })
  }
}));

describe("IntegrationsSettings - API Keys Generator & Lifecycle", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test("Renders existing keys with prefix, scopes, created date, and Revoke button", async () => {
    render(<IntegrationsSettings />);

    await waitFor(() => {
      expect(screen.getByText("Existing ATS Key")).toBeInTheDocument();
      expect(screen.getByText("rm_live_abc1...")).toBeInTheDocument();
      expect(screen.getByText(/Created:/)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Revoke/i })).toBeInTheDocument();
    });
  });

  test("Clicking Generate Key opens modal, validates required inputs, and submits key creation", async () => {
    settingsAPI.createApiKey.mockResolvedValueOnce({
      data: {
        success: true,
        message: "API key generated successfully",
        key: "rm_live_secretkey1234567890",
        api_key: {
          id: "key_new",
          name: "Zapier Ingestion",
          key_prefix: "rm_live_secr...",
          scopes: ["read:candidates", "write:jobs"],
          created_at: "2026-11-21T12:00:00Z"
        }
      }
    });

    render(<IntegrationsSettings />);

    // 1. Click "Generate Key" button
    const generateBtn = screen.getByRole("button", { name: /Generate Key/i });
    fireEvent.click(generateBtn);

    // Modal title appears
    expect(screen.getByText("Generate External API Key")).toBeInTheDocument();

    // 2. Validate empty name inline validation
    const createBtn = screen.getByRole("button", { name: /Create Key/i });
    fireEvent.click(createBtn);

    expect(await screen.findByText("API key name is required")).toBeInTheDocument();
    expect(settingsAPI.createApiKey).not.toHaveBeenCalled();

    // 3. Fill in key name
    const nameInput = screen.getByPlaceholderText(/Careers Page Intake/i);
    fireEvent.change(nameInput, { target: { value: "Zapier Ingestion" } });

    // 4. Submit form
    fireEvent.click(createBtn);

    // 5. Verify settingsAPI.createApiKey was called (proves form was submitted and not swallowed by outer form)
    await waitFor(() => {
      expect(settingsAPI.createApiKey).toHaveBeenCalledWith({
        name: "Zapier Ingestion",
        scopes: ["read:candidates", "write:jobs"],
        expires_in_days: 90
      });
    });

    // 6. Verify "Show once" raw key dialog is displayed with Copy button
    await waitFor(() => {
      expect(screen.getByText("Your New API Key")).toBeInTheDocument();
      expect(screen.getByText("rm_live_secretkey1234567890")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Copy/i })).toBeInTheDocument();
    });
  });
});
