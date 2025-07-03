from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
import pytz
import logging

# Import your modules
from calendar_service import GoogleCalendarService
from agent import CalendarBookingAgent

# Load .env
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

# Initialize app
app = FastAPI(title="Calendar Booking API", version="1.0.0")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class ChatInput(BaseModel):
    message: str
    session_id: str = None

class TestEventInput(BaseModel):
    title: str = "Test Event"
    start_time: str  # ISO format string
    duration_minutes: int = 60
    description: str = "Test event created via API"
    attendee_emails: list = []

# Initialize services
try:
    calendar_service = GoogleCalendarService()
    agent = CalendarBookingAgent(
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        calendar_service=calendar_service
    )
    logger.info("✅ Services initialized successfully")
except Exception as e:
    logger.error(f"❌ Failed to initialize services: {e}")
    raise

@app.get("/")
def root():
    return {
        "message": "Calendar Booking API is running",
        "version": "1.0.0",
        "endpoints": {
            "chat": "/chat",
            "health": "/health",
            "debug": "/debug",
            "test-event": "/test-event"
        }
    }

@app.get("/health")
def health_check():
    """Health check endpoint"""
    try:
        # Test calendar service
        access_result = calendar_service.verify_calendar_access()
        
        return {
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "calendar": access_result["success"],
                "gemini": bool(os.getenv("GEMINI_API_KEY")),
            },
            "calendar_access": access_result
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.get("/debug")
def debug_info():
    """Debug endpoint to check configuration"""
    try:
        # Check environment variables
        env_status = {
            "GOOGLE_SERVICE_ACCOUNT_JSON": "✅ Set" if os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON") else "❌ Not set",
            "GEMINI_API_KEY": "✅ Set" if os.getenv("GEMINI_API_KEY") else "❌ Not set",
            "TIMEZONE": os.getenv("TIMEZONE", "Not set (using UTC)")
        }
        
        # Test calendar access
        access_result = calendar_service.verify_calendar_access()
        
        # List upcoming events
        events = calendar_service.list_events(days_ahead=7)
        
        return {
            "environment": env_status,
            "calendar_access": access_result,
            "upcoming_events_count": len(events),
            "calendar_id": calendar_service.calendar_id,
            "server_time": datetime.now().isoformat(),
            "server_timezone": str(datetime.now().astimezone().tzinfo)
        }
        
    except Exception as e:
        logger.error(f"Debug info failed: {e}")
        return {
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.post("/test-event")
def create_test_event(event_data: TestEventInput):
    """Create a test event to verify calendar integration"""
    try:
        # Parse the start time
        start_time = datetime.fromisoformat(event_data.start_time.replace('Z', '+00:00'))
        end_time = start_time + timedelta(minutes=event_data.duration_minutes)
        
        logger.info(f"Creating test event: {event_data.title}")
        logger.info(f"Start: {start_time}, End: {end_time}")
        
        # Create the event
        result = calendar_service.create_event(
            title=event_data.title,
            start_time=start_time,
            end_time=end_time,
            description=event_data.description,
            attendee_emails=event_data.attendee_emails
        )
        
        logger.info(f"Test event result: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Test event creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/events")
def list_events(days_ahead: int = 7):
    """List upcoming events"""
    try:
        events = calendar_service.list_events(days_ahead=days_ahead)
        
        # Format events for easier reading
        formatted_events = []
        for event in events:
            formatted_event = {
                "id": event.get("id"),
                "title": event.get("summary", "No title"),
                "start": event.get("start", {}).get("dateTime", event.get("start", {}).get("date")),
                "end": event.get("end", {}).get("dateTime", event.get("end", {}).get("date")),
                "description": event.get("description", ""),
                "attendees": [att.get("email") for att in event.get("attendees", [])],
                "html_link": event.get("htmlLink")
            }
            formatted_events.append(formatted_event)
        
        return {
            "events": formatted_events,
            "count": len(formatted_events),
            "calendar_id": calendar_service.calendar_id
        }
        
    except Exception as e:
        logger.error(f"List events failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
async def chat(input_data: ChatInput):
    """Main chat endpoint"""
    try:
        logger.info(f"📩 Incoming message: {input_data.message}")
        logger.info(f"🔑 Session ID: {input_data.session_id}")
        
        # Process the message
        response = agent.process_message(input_data.message, input_data.session_id)
        
        logger.info(f"📤 Response: {response}")
        
        # Add some debug information
        response["debug"] = {
            "timestamp": datetime.now().isoformat(),
            "session_id": input_data.session_id,
            "message_length": len(input_data.message)
        }
        
        return response
        
    except Exception as e:
        logger.error(f"Chat endpoint failed: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            "response": f"❌ I apologize, but I encountered an error: {str(e)}",
            "booking_confirmed": False,
            "available_slots": [],
            "session_id": input_data.session_id,
            "error": str(e)
        }

@app.delete("/events/{event_id}")
def delete_event(event_id: str):
    """Delete an event"""
    try:
        result = calendar_service.delete_event(event_id)
        return result
    except Exception as e:
        logger.error(f"Delete event failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Add some middleware for request logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.now()
    
    # Log incoming request
    logger.info(f"🌐 {request.method} {request.url.path}")
    
    # Process request
    response = await call_next(request)
    
    # Log response
    process_time = (datetime.now() - start_time).total_seconds()
    logger.info(f"✅ {request.method} {request.url.path} - {response.status_code} ({process_time:.2f}s)")
    
    return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)