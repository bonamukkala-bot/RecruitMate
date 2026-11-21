import os
from pathlib import Path
from dotenv import load_dotenv

# Explicitly load backend/.env regardless of current working directory
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

class Config:
    # Groq
    GROQ_API_KEY       = os.getenv("GROQ_API_KEY")
    GROQ_MODEL         = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
    GROQ_MODEL_HEAVY   = os.getenv("GROQ_MODEL_HEAVY", "openai/gpt-oss-120b")
    DEFAULT_GROQ_MODELS = [
        "openai/gpt-oss-20b",
        "openai/gpt-oss-120b",
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant"
    ]
    _raw_allowed       = os.getenv("GROQ_ALLOWED_MODELS")
    if _raw_allowed and _raw_allowed.strip():
        GROQ_ALLOWED_MODELS = [m.strip() for m in _raw_allowed.split(",") if m.strip()] or list(DEFAULT_GROQ_MODELS)
    else:
        GROQ_ALLOWED_MODELS = list(DEFAULT_GROQ_MODELS)

    # Ensure configured models are always in allowed list
    for _m in [GROQ_MODEL, GROQ_MODEL_HEAVY]:
        if _m and _m not in GROQ_ALLOWED_MODELS:
            GROQ_ALLOWED_MODELS.append(_m)

    # Estimated pricing per 1M tokens ($/1M tokens)
    GROQ_MODEL_PRICING = {
        "openai/gpt-oss-20b": {"prompt": 0.15, "completion": 0.60},
        "openai/gpt-oss-120b": {"prompt": 0.60, "completion": 2.40},
        "llama-3.3-70b-versatile": {"prompt": 0.59, "completion": 0.79},
        "llama-3.1-8b-instant": {"prompt": 0.05, "completion": 0.08},
    }

    # MongoDB
    MONGO_URI          = os.getenv("MONGO_URI")
    DB_NAME            = os.getenv("MONGO_DB") or "recruitmate"

    # JWT
    JWT_SECRET         = os.getenv("JWT_SECRET")
    JWT_EXPIRY_HOURS   = 8

    # Brevo Email
    BREVO_API_KEY      = os.getenv("BREVO_API_KEY")
    BREVO_SENDER_EMAIL = os.getenv("BREVO_SENDER_EMAIL")
    BREVO_SENDER_NAME  = os.getenv("BREVO_SENDER_NAME")
    TURNSTILE_SECRET_KEY = os.getenv("TURNSTILE_SECRET_KEY")
    FRONTEND_URL       = os.getenv("FRONTEND_URL") or "http://localhost:3000"

    # Google Calendar & Meet Integration
    GOOGLE_CALENDAR_ENABLED     = os.getenv("GOOGLE_CALENDAR_ENABLED", "false").lower() in ("true", "1")
    GOOGLE_CLIENT_ID            = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET        = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI         = os.getenv("GOOGLE_REDIRECT_URI", "")
    GOOGLE_TOKEN_ENCRYPTION_KEY = os.getenv("GOOGLE_TOKEN_ENCRYPTION_KEY", "")
