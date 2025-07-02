import os
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from models import BookingRequest, BookingResponse
from calendar_service import GoogleCalendarService
from agent import CalendarBookingAgent

load_dotenv()

app = FastAPI(title="Calendar Booking Agent API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Init services
calendar_service = GoogleCalendarService(
    credentials_path=os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials/service-account-key.json")
)
agent = CalendarBookingAgent(
    gemini_api_key=os.getenv("GOOGLE_API_KEY"),
    calendar_service=calendar_service
)

@app.get("/")
def root():
    return {"message": "Calendar Booking Agent API is running!"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/chat", response_model=BookingResponse)
def chat(request: BookingRequest):
    try:
        session_id = request.session_id or str(uuid.uuid4())
        result = agent.process_message(request.message, session_id)
        return BookingResponse(
            response=result["response"],
            session_id=session_id,
            suggested_times=result["available_slots"],
            booking_confirmed=result["booking_confirmed"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
