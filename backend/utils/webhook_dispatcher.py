import time
import json
import hmac
import hashlib
import socket
import ipaddress
import threading
from urllib.parse import urlparse
from datetime import datetime, timezone
from bson import ObjectId
import requests

from utils.db import webhooks_collection, webhook_logs_collection

MAX_DELIVERY_LOGS_PER_COMPANY = 50

# Metadata and link-local blocked addresses
BLOCKED_METADATA_IPS = {
    "169.254.169.254",   # AWS / GCP / Azure metadata
    "fd00:ec2::254",     # AWS IPv6 metadata
}

BLOCKED_HOSTNAMES = {
    "metadata.google.internal",
    "instance-data",
    "localhost"
}

def validate_webhook_url(url: str) -> tuple[bool, str]:
    """
    Validates a webhook URL against SSRF vulnerabilities.
    Returns (is_valid, error_message).
    Enforces:
    - HTTPS only
    - Standard port 443 only (or default)
    - Hostname must resolve to valid public IP addresses
    - Blocks private, loopback, link-local, multicast, reserved, and cloud metadata IPs.
    """
    if not url or not isinstance(url, str):
        return False, "Webhook URL must be provided"

    url = url.strip()
    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, f"Malformed URL: {e}"

    if parsed.scheme.lower() != "https":
        return False, "Webhook URL must use HTTPS"

    hostname = parsed.hostname
    if not hostname:
        return False, "Invalid webhook URL: missing hostname"

    if hostname.lower() in BLOCKED_HOSTNAMES:
        return False, "Blocked host address (metadata/internal destination)"

    # Port validation: standard 443 only
    if parsed.port is not None and parsed.port != 443:
        return False, f"Non-standard HTTPS port {parsed.port} is blocked. Only port 443 is permitted."

    # DNS Resolution and IP checking
    try:
        addr_info = socket.getaddrinfo(hostname, 443, socket.AF_UNSPEC, socket.SOCK_STREAM)
        if not addr_info:
            return False, f"Could not resolve hostname '{hostname}'"
    except socket.gaierror as e:
        return False, f"DNS resolution failed for '{hostname}': {e}"
    except Exception as e:
        return False, f"Error validating webhook destination: {e}"

    # Verify every resolved address
    for item in addr_info:
        sockaddr = item[4]
        ip_str = sockaddr[0]

        if ip_str in BLOCKED_METADATA_IPS:
            return False, f"Target IP {ip_str} is a protected cloud metadata address"

        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError:
            return False, f"Invalid IP address resolved: {ip_str}"

        if (
            ip_obj.is_private or
            ip_obj.is_loopback or
            ip_obj.is_link_local or
            ip_obj.is_reserved or
            ip_obj.is_multicast or
            ip_obj.is_unspecified
        ):
            return False, f"Target IP {ip_str} is in a prohibited private or local address range"

    return True, ""

def compute_webhook_signature(secret: str, payload_json: str, timestamp: int) -> str:
    """Computes HMAC-SHA256 signature for payload with timestamp."""
    signed_payload = f"{timestamp}.{payload_json}"
    return hmac.new(
        secret.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

def _record_delivery_log(log_entry: dict):
    """Inserts a webhook delivery log and caps collection to last 50 entries per company."""
    try:
        company_id = log_entry["company_id"]
        webhook_logs_collection.insert_one(log_entry)

        # Count and trim excess logs beyond MAX_DELIVERY_LOGS_PER_COMPANY
        count = webhook_logs_collection.count_documents({"company_id": company_id})
        if count > MAX_DELIVERY_LOGS_PER_COMPANY:
            excess = count - MAX_DELIVERY_LOGS_PER_COMPANY
            oldest_ids = [
                d["_id"] for d in webhook_logs_collection.find(
                    {"company_id": company_id},
                    {"_id": 1}
                ).sort("delivered_at", 1).limit(excess)
            ]
            if oldest_ids:
                webhook_logs_collection.delete_many({"_id": {"$in": oldest_ids}})
    except Exception as e:
        print(f"⚠️ Failed to write webhook delivery log: {e}")

def deliver_webhook_attempt(webhook: dict, event_name: str, payload_json: str, attempt: int = 1) -> tuple[bool, int, str]:
    """
    Executes a single delivery attempt with SSRF re-check, 5s timeout, and no redirects.
    Returns (success, status_code, error_message).
    """
    url = webhook["url"]
    secret = webhook.get("secret", "")

    # Re-validate destination prior to connection to defend against DNS rebinding
    is_valid, err_msg = validate_webhook_url(url)
    if not is_valid:
        return False, 0, f"SSRF Block: {err_msg}"

    timestamp = int(time.time())
    sig = compute_webhook_signature(secret, payload_json, timestamp)

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "RecruitMate-Webhook/1.0",
        "X-RecruitMate-Event": event_name,
        "X-RecruitMate-Signature": f"t={timestamp},v1={sig}"
    }

    start_time = time.time()
    try:
        # allow_redirects=False prevents open redirect SSRF bypasses
        resp = requests.post(
            url,
            data=payload_json,
            headers=headers,
            timeout=5.0,
            allow_redirects=False
        )
        elapsed_ms = round((time.time() - start_time) * 1000)
        success = (200 <= resp.status_code < 300)
        err = "" if success else f"HTTP {resp.status_code}"

        _record_delivery_log({
            "company_id": webhook["company_id"],
            "webhook_id": str(webhook["_id"]),
            "event": event_name,
            "url": url,
            "status_code": resp.status_code,
            "response_time_ms": elapsed_ms,
            "attempt": attempt,
            "success": success,
            "error_message": err,
            "delivered_at": datetime.now(timezone.utc)
        })

        return success, resp.status_code, err

    except requests.exceptions.Timeout:
        elapsed_ms = round((time.time() - start_time) * 1000)
        err = "Request timed out after 5.0 seconds"
        _record_delivery_log({
            "company_id": webhook["company_id"],
            "webhook_id": str(webhook["_id"]),
            "event": event_name,
            "url": url,
            "status_code": 0,
            "response_time_ms": elapsed_ms,
            "attempt": attempt,
            "success": False,
            "error_message": err,
            "delivered_at": datetime.now(timezone.utc)
        })
        return False, 0, err
    except Exception as e:
        elapsed_ms = round((time.time() - start_time) * 1000)
        err = str(e)
        _record_delivery_log({
            "company_id": webhook["company_id"],
            "webhook_id": str(webhook["_id"]),
            "event": event_name,
            "url": url,
            "status_code": 0,
            "response_time_ms": elapsed_ms,
            "attempt": attempt,
            "success": False,
            "error_message": err,
            "delivered_at": datetime.now(timezone.utc)
        })
        return False, 0, err

def _dispatch_worker(company_id: str, event_name: str, payload: dict):
    """Background worker for dispatching webhook events with up to 3 retries and backoff."""
    try:
        webhooks = list(webhooks_collection.find({
            "company_id": str(company_id),
            "active": True,
            "events": event_name
        }))
        if not webhooks:
            return

        payload_json = json.dumps(payload, default=str)

        for wh in webhooks:
            # Up to 3 attempts with exponential backoff (e.g. 1s, 2s)
            for attempt in range(1, 4):
                success, _, _ = deliver_webhook_attempt(wh, event_name, payload_json, attempt=attempt)
                if success:
                    break
                if attempt < 3:
                    time.sleep(attempt * 1.0)
    except Exception as e:
        print(f"⚠️ Webhook dispatch worker error: {e}")

def dispatch_webhook_event(company_id: str, event_name: str, payload: dict):
    """Asynchronously dispatches an event to subscribed outgoing webhooks in a daemon thread."""
    t = threading.Thread(
        target=_dispatch_worker,
        args=(company_id, event_name, payload),
        daemon=True
    )
    t.start()
