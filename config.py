import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", os.urandom(32).hex())
    DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:5000/auth/callback")
    SCOPES = [
        "https://www.googleapis.com/auth/script.projects",
        "https://www.googleapis.com/auth/script.processes",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/documents",
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/calendar",
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
    ]
    BASE_URL = os.getenv("BASE_URL", "http://localhost:5000")
