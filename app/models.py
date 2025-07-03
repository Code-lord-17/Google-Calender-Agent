from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class ChatMessage(BaseModel):
    message: str
    user_id: Optional[str] = "default_user"

class ChatResponse(BaseModel):
    response: str
    booking_status: Optional[str] = None
    event_details: Optional[dict] = None

class EventDetails(BaseModel):
    title: str
    start_time: datetime
    end_time: datetime
    description: Optional[str] = ""
    attendees: Optional[List[str]] = []

class AvailabilityRequest(BaseModel):
    date: str
    duration_minutes: int = 60