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
