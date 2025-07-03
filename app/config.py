import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    CALENDAR_ID = os.getenv("CALENDAR_ID", "primary")
    
    # FastAPI settings
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8000))
    
    # LLM settings
    MODEL_NAME = "gemini-2.0-flash"
    TEMPERATURE = 0.7