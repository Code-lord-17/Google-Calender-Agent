from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class BookingRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class BookingResponse(BaseModel):
    response: str
    session_id: str
    booking_confirmed: bool = False
    suggested_times: Optional[List[str]] = None

class AppointmentDetails(BaseModel):
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    attendee_email: Optional[str] = None