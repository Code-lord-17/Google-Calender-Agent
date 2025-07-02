import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from googleapiclient.discovery import build
import pytz

class GoogleCalendarService:
    def __init__(self, credentials_path: str):
        self.credentials_path = credentials_path
        self.service = self._build_service()
        
    def _build_service(self):
        """Build and return Google Calendar service object"""
        SCOPES = ['https://www.googleapis.com/auth/calendar']
        
        credentials = service_account.Credentials.from_service_account_file(
            self.credentials_path, scopes=SCOPES
        )
        
        return build('calendar', 'v3', credentials=credentials)
    
    def get_calendar_id(self) -> str:
        """Get the primary calendar ID"""
        return 'primary'
    
    def check_availability(self, start_time: datetime, end_time: datetime) -> bool:
        """Check if a time slot is available"""
        try:
            # Convert to UTC if timezone-aware
            if start_time.tzinfo is not None:
                start_time = start_time.astimezone(pytz.UTC)
            if end_time.tzinfo is not None:
                end_time = end_time.astimezone(pytz.UTC)
            
            events_result = self.service.events().list(
                calendarId=self.get_calendar_id(),
                timeMin=start_time.isoformat() + 'Z',
                timeMax=end_time.isoformat() + 'Z',
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            return len(events) == 0
            
        except Exception as e:
            print(f"Error checking availability: {e}")
            return False
    
    def get_available_slots(self, date: datetime, duration_hours: int = 1) -> List[str]:
        """Get available time slots for a given date"""
        available_slots = []
        
        # Define business hours (9 AM to 5 PM)
        start_hour = 9
        end_hour = 17
        
        # Set timezone to local timezone
        local_tz = pytz.timezone('UTC')  # You can change this to your local timezone
        
        for hour in range(start_hour, end_hour - duration_hours + 1):
            slot_start = date.replace(hour=hour, minute=0, second=0, microsecond=0)
            slot_end = slot_start + timedelta(hours=duration_hours)
            
            if self.check_availability(slot_start, slot_end):
                available_slots.append(slot_start.strftime("%Y-%m-%d %H:%M"))
        
        return available_slots
    
    def create_event(self, title: str, start_time: datetime, end_time: datetime, 
                    description: str = "", attendee_email: str = None) -> Dict:
        """Create a calendar event"""
        try:
            event = {
                'summary': title,
                'description': description,
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': 'UTC',
                },
            }
            
            if attendee_email:
                event['attendees'] = [{'email': attendee_email}]
            
            created_event = self.service.events().insert(
                calendarId=self.get_calendar_id(),
                body=event
            ).execute()
            
            return {
                'success': True,
                'event_id': created_event['id'],
                'event_link': created_event.get('htmlLink', ''),
                'message': f"Event '{title}' created successfully!"
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': f"Failed to create event: {str(e)}"
            }