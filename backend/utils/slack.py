import requests
from utils.settings import get_settings

def mask_slack_url(url: str) -> str:
    """Returns a masked version of a Slack webhook URL."""
    if not url:
        return ""
    url = url.strip()
    if len(url) > 35:
        # e.g. https://hooks.slack.com/services/T.../B.../XXXX
        return f"{url[:33]}...{url[-4:]}"
    return "https://hooks.slack.com/...****"

def send_slack_message(webhook_url: str, text: str, blocks: list | None = None) -> tuple[bool, str]:
    """Sends a Slack incoming webhook notification."""
    if not webhook_url or not webhook_url.startswith("https://hooks.slack.com/"):
        return False, "Invalid Slack webhook URL"

    payload = {"text": text}
    if blocks:
        payload["blocks"] = blocks

    try:
        resp = requests.post(webhook_url, json=payload, timeout=5.0)
        if resp.status_code == 200 and resp.text.strip().lower() == "ok":
            return True, "Slack message sent successfully"
        return False, f"Slack responded with status {resp.status_code}: {resp.text}"
    except Exception as e:
        return False, f"Failed to send Slack message: {e}"

def send_slack_notification(company_id: str, event_type: str, data: dict):
    """
    Dispatches a Slack notification if configured for the given event type.
    Event types: 'new_candidate', 'interview_complete', 'pending_review'.
    Safe: errors are caught and logged, never blocking the calling workflow.
    """
    try:
        settings = get_settings(company_id)
        integrations = settings.get("integrations", {})
        webhook_url = (integrations.get("slack_webhook_url") or "").strip()
        if not webhook_url or not webhook_url.startswith("https://hooks.slack.com/"):
            return

        events = integrations.get("slack_events", {})
        if not events.get(event_type, False):
            return

        # Format message based on event
        candidate_name = data.get("candidate_name", "A candidate")
        job_title = data.get("job_title", "Position")

        if event_type == "new_candidate":
            text = f"🎯 *New Candidate:* {candidate_name} applied for *{job_title}* (Score: {data.get('match_score', 'N/A')})"
        elif event_type == "interview_complete":
            text = f"🎙️ *Interview Completed:* {candidate_name} finished interview for *{job_title}* (Score: {data.get('overall_score', 'N/A')}/100)"
        elif event_type == "pending_review":
            text = f"⚠️ *Action Required:* Rejection recommendation for {candidate_name} ({job_title}) is pending review."
        else:
            text = f"RecruitMate notification for {candidate_name}"

        send_slack_message(webhook_url, text)
    except Exception as e:
        print(f"⚠️ Slack notification error (non-fatal): {e}")
