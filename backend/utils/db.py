import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── SSL fix for Python 3.13 ───────────────────────────────────────────────────
import certifi
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

from pymongo import MongoClient, ASCENDING
from config import Config

# ── Connection ────────────────────────────────────────────────────────────────
client = MongoClient(
    Config.MONGO_URI,
    tls=True,
    tlsCAFile=certifi.where(),
    tlsAllowInvalidCertificates=True,
    tlsAllowInvalidHostnames=True,
    serverSelectionTimeoutMS=15000
)
db = client[Config.DB_NAME]

# ── Collections ───────────────────────────────────────────────────────────────
companies_collection  = db["companies"]
jobs_collection       = db["jobs"]
candidates_collection = db["candidates"]
pipeline_collection   = db["pipeline"]
otp_collection        = db["otps"]
company_settings_collection = db["company_settings"]
audit_logs_collection = db["audit_logs"]
llm_usage_collection  = db["llm_usage"]

# ── Indexes ───────────────────────────────────────────────────────────────────
def create_indexes():
    try:
        companies_collection.create_index([("email", ASCENDING)], unique=True)
        company_settings_collection.create_index([("company_id", ASCENDING)], unique=True)
        jobs_collection.create_index([("company_id", ASCENDING)])
        candidates_collection.create_index([("company_id", ASCENDING)])
        candidates_collection.create_index([("job_id", ASCENDING)])
        audit_logs_collection.create_index([("company_id", ASCENDING)])
        try:
            llm_usage_collection.create_index([("company_id", ASCENDING), ("ts", ASCENDING)])
            llm_usage_collection.create_index(
                [("ts", ASCENDING)],
                expireAfterSeconds=180 * 24 * 3600
            )
        except Exception as idx_err:
            print(f"⚠️ [llm_usage] Index creation warning (non-fatal): {idx_err}")
        otp_collection.create_index(
            [("expires_at", ASCENDING)],
            expireAfterSeconds=0
        )
        print(f"✅ Indexes ready on database: {db.name}")
    except Exception as e:
        print(f"⚠️ Index warning: {e}")

# ── Test block ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        client.admin.command("ping")
        create_indexes()
        print("✅ MongoDB connected!")
        print(f"   Database    : {Config.DB_NAME}")
        print(f"   Collections : {db.list_collection_names()}")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
