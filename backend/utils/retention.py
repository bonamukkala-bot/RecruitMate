import hashlib
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from utils.db import (
    candidates_collection,
    pipeline_collection,
    company_settings_collection
)
from utils.settings import get_settings
from utils.auth_helper import log_audit_event

def purge_expired_candidates(company_id: str | None = None, execute: bool = False) -> dict:
    """
    Purges candidates older than the organization's data_retention_days setting.
    By default (execute=False), runs in DRY-RUN mode and only reports counts.
    When execute=True, hard-deletes candidates and their pipeline records.
    Audit-logs only candidate IDs and hashed emails (never raw personal data).
    """
    now = datetime.now(timezone.utc)
    total_found = 0
    total_purged = 0
    company_results = []

    # Determine target companies
    if company_id:
        company_ids = [str(company_id)]
    else:
        # Scan all companies with retention settings > 0
        settings_docs = list(company_settings_collection.find(
            {"privacy.data_retention_days": {"$gt": 0}},
            {"company_id": 1}
        ))
        company_ids = [str(d["company_id"]) for d in settings_docs if d.get("company_id")]

    for comp_id in company_ids:
        comp_settings = get_settings(comp_id)
        privacy = comp_settings.get("privacy", {})
        retention_days = int(privacy.get("data_retention_days", 0))

        if retention_days <= 0:
            continue  # 0 means keep forever

        cutoff_date = now - timedelta(days=retention_days)

        # Find candidates created prior to cutoff
        query = {
            "company_id": comp_id,
            "created_at": {"$lt": cutoff_date}
        }
        expired = list(candidates_collection.find(query, {"_id": 1, "candidate_email": 1, "created_at": 1}))
        found_count = len(expired)
        total_found += found_count
        purged_count = 0

        if execute and found_count > 0:
            deleted_ids = []
            email_hashes = []

            for cand in expired:
                cid = cand["_id"]
                cid_str = str(cid)
                deleted_ids.append(cid_str)

                # Hash email for privacy-safe audit trail
                raw_email = (cand.get("candidate_email") or "").strip().lower()
                if raw_email:
                    email_hashes.append(hashlib.sha256(raw_email.encode("utf-8")).hexdigest())

                # Cascade deletion: pipeline logs
                pipeline_collection.delete_many({
                    "$or": [{"candidate_id": cid_str}, {"candidate_id": cid}]
                })

                # Hard delete candidate record
                candidates_collection.delete_one({"_id": cid})
                purged_count += 1

            total_purged += purged_count

            # Audit log event with privacy-safe metadata
            log_audit_event(
                company_id=comp_id,
                action="privacy.retention_purge",
                target={"purged_count": purged_count, "retention_days": retention_days},
                details={
                    "cutoff_date": cutoff_date.isoformat(),
                    "purged_count": purged_count,
                    "candidate_ids": deleted_ids[:50],
                    "email_hashes_sample": email_hashes[:10]
                }
            )

        company_results.append({
            "company_id": comp_id,
            "retention_days": retention_days,
            "cutoff_date": cutoff_date.isoformat(),
            "candidates_found": found_count,
            "candidates_purged": purged_count
        })

    return {
        "success": True,
        "execute": execute,
        "dry_run": not execute,
        "candidates_found": total_found,
        "candidates_purged": total_purged,
        "deleted_candidates": total_purged if execute else total_found,
        "companies": company_results
    }
