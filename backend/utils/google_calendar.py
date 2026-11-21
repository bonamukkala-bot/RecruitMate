import uuid
import requests
from datetime import datetime, timezone, timedelta
from config import Config
from utils.settings import get_settings
from utils.encryption import decrypt_token

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CALENDAR_API_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events?conferenceDataVersion=1"

def get_google_access_token(company_id: str) -> str | None:
    """Retrieves and refreshes a Google access token using the stored encrypted refresh token."""
    if not Config.GOOGLE_CALENDAR_ENABLED:
        return None

    settings = get_settings(company_id)
    integrations = settings.get("integrations", {})
    encrypted_refresh = integrations.get("google_refresh_token_enc")
    if not encrypted_refresh:
        return None

    try:
        refresh_token = decrypt_token(encrypted_refresh)
    except Exception as e:
        print(f"⚠️ Failed to decrypt Google refresh token: {e}")
        return None

    if not Config.GOOGLE_CLIENT_ID or not Config.GOOGLE_CLIENT_SECRET:
        return None

    try:
        resp = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": Config.GOOGLE_CLIENT_ID,
                "client_secret": Config.GOOGLE_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token"
            },
            timeout=5.0
        )
        if resp.status_code == 200:
            return resp.json().get("access_token")
        print(f"⚠️ Google token refresh failed ({resp.status_code}): {resp.text}")
        return None
    except Exception as e:
        print(f"⚠️ Google token refresh exception: {e}")
        return None

def create_calendar_meet_event(
    company_id: str,
    summary: str,
    description: str,
    start_time: datetime | str,
    attendee_email: str | None = None
) -> dict | None:
    """
    Creates a Google Calendar event with an auto-generated Google Meet link.
    Only runs if Config.GOOGLE_CALENDAR_ENABLED is True and company is connected.
    Returns dict with event_id and meet_link, or None if disabled/failed.
    """
    if not Config.GOOGLE_CALENDAR_ENABLED:
        return None

    access_token = get_google_access_token(company_id)
    if not access_token:
        return None

    # Determine start and end times
    if isinstance(start_time, str):
        try:
            start_dt = datetime.fromisoformat(start_time)
        except Exception:
            start_dt = datetime.now(timezone.utc) + timedelta(days=2, hours=10)
    else:
        start_dt = start_time

    end_dt = start_dt + timedelta(minutes=45)

    event_body = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start_dt.isoformat()},
        "end": {"dateTime": end_dt.isoformat()},
        "conferenceData": {
            "createRequest": {
                "requestId": str(uuid.uuid4()),
                "conferenceSolutionKey": {"type": "hangoutsMeet"}
            }
        }
    }
    if attendee_email:
        event_body["attendees"] = [{"email": attendee_email}]

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    try:
        resp = requests.post(GOOGLE_CALENDAR_API_URL, json=event_body, headers=headers, timeout=5.0)
        if resp.status_code in (200, 201):
            data = resp.json()
            meet_link = data.get("hangoutLink") or data.get("conferenceData", {}).get("entryPoints", [{}])[0].get("uri")
            return {
                "event_id": data.get("id"),
                "meet_link": meet_link,
                "html_link": data.get("htmlLink")
            }
        print(f"⚠️ Google Calendar event creation failed ({resp.status_code}): {resp.text}")
        return None
    except Exception as e:
        print(f"⚠️ Google Calendar creation error (non-fatal): {e}")
        return None
