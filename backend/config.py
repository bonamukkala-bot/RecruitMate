import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Groq
    GROQ_API_KEY       = os.getenv("GROQ_API_KEY")

    # MongoDB
    MONGO_URI          = os.getenv("MONGO_URI")
    DB_NAME            = "recruitmate"

    # JWT
    JWT_SECRET         = os.getenv("JWT_SECRET")
    JWT_EXPIRY_HOURS   = 8

    # Brevo Email
    BREVO_API_KEY      = os.getenv("BREVO_API_KEY")
    BREVO_SENDER_EMAIL = os.getenv("BREVO_SENDER_EMAIL")
    BREVO_SENDER_NAME  = os.getenv("BREVO_SENDER_NAME")