import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
import pytz
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.ERROR)


class GoogleCalendarService:
    def __init__(self, credentials_path: Optional[str] = None):
        self.service = self._build_service(credentials_path)
        self.calendar_id = self.get_calendar_id()
        
        # Test the service immediately
        self._test_service()

    def _build_service(self, credentials_path: Optional[str]):
        SCOPES = ['https://www.googleapis.com/auth/calendar']

        if credentials_path and os.path.exists(credentials_path):
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path, scopes=SCOPES
            )
        else:
            credentials_raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
            if not credentials_raw:
                raise Exception("Missing GOOGLE_SERVICE_ACCOUNT_JSON in environment variables")

            try:
                credentials_info = json.loads(credentials_raw)
                credentials = service_account.Credentials.from_service_account_info(
                    credentials_info, scopes=SCOPES
                )
            except json.JSONDecodeError:
                raise Exception("Invalid JSON in GOOGLE_SERVICE_ACCOUNT_JSON")

        return build("calendar", "v3", credentials=credentials)

    def _test_service(self):
        """Test the service connection and permissions"""
        try:
            # Test basic connection
            calendar_list = self.service.calendarList().list().execute()
            logger.info(f"✅ Successfully connected to Google Calendar API")
            logger.info(f"📋 Available calendars: {len(calendar_list.get('items', []))}")
            
            # List all calendars to help debug
            for calendar in calendar_list.get('items', []):
                logger.info(f"📅 Calendar: {calendar.get('summary')} (ID: {calendar.get('id')})")
                logger.info(f"   Access Role: {calendar.get('accessRole')}")
                
        except Exception as e:
            logger.error(f"❌ Service test failed: {e}")
            raise

    def get_calendar_id(self) -> str:
        """Get the calendar ID - you can modify this to use a different calendar"""
        return "shaivas.hem@gmail.com"

    def check_availability(self, start_time: datetime, end_time: datetime) -> bool:
        """Check if a time slot is available"""
        try:
            # Ensure timezone awareness
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=pytz.UTC)
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=pytz.UTC)

            # Convert to UTC
            start_time = start_time.astimezone(pytz.UTC)
            end_time = end_time.astimezone(pytz.UTC)

            logger.info(f"🔍 Checking availability from {start_time} to {end_time}")

            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=start_time.isoformat(),
                timeMax=end_time.isoformat(),
                singleEvents=True,
                orderBy="startTime"
            ).execute()

            events = events_result.get("items", [])
            is_available = len(events) == 0
            
            logger.info(f"📊 Found {len(events)} conflicting events. Available: {is_available}")
            return is_available
            
        except Exception as e:
            logger.error(f"⚠️ Availability check error: {e}")
            return False

    def get_available_slots(self, date: datetime, duration_hours: int = 1) -> List[str]:
        """Get available time slots for a given date"""
        slots = []
        
        # Use local timezone if available, otherwise UTC
        local_tz = pytz.timezone(os.getenv('TIMEZONE', 'UTC'))
        
        for hour in range(9, 18 - duration_hours):
            start = date.replace(hour=hour, minute=0, second=0, microsecond=0)
            if start.tzinfo is None:
                start = local_tz.localize(start)
            
            end = start + timedelta(hours=duration_hours)
            
            if self.check_availability(start, end):
                slots.append(start.strftime("%Y-%m-%d %H:%M %Z"))
        
        return slots

    def create_event(self,
                     title: str,
                     start_time: datetime,
                     end_time: datetime,
                     description: str = "",
                     attendee_emails: Optional[List[str]] = None) -> Dict:
        """Create a calendar event"""
        try:
            # Handle timezone conversion properly
            if start_time.tzinfo is None:
                # If no timezone, assume local timezone
                local_tz = pytz.timezone(os.getenv('TIMEZONE', 'UTC'))
                start_time = local_tz.localize(start_time)
            
            if end_time.tzinfo is None:
                local_tz = pytz.timezone(os.getenv('TIMEZONE', 'UTC'))
                end_time = local_tz.localize(end_time)

            logger.info(f"📅 Creating event '{title}'")
            logger.info(f"🕐 Start: {start_time}")
            logger.info(f"🕐 End: {end_time}")
            logger.info(f"📧 Calendar ID: {self.calendar_id}")

            # Create event object
            event = {
                "summary": title,
                "description": description,
                "start": {
                    "dateTime": start_time.isoformat(),
                    "timeZone": str(start_time.tzinfo) if start_time.tzinfo else "UTC"
                },
                "end": {
                    "dateTime": end_time.isoformat(),
                    "timeZone": str(end_time.tzinfo) if end_time.tzinfo else "UTC"
                },
                # Add some default settings
                "reminders": {
                    "useDefault": True
                }
            }

            # Add attendees if provided
            if attendee_emails:
                event["attendees"] = [{"email": email} for email in attendee_emails]
                logger.info(f"👥 Attendees: {attendee_emails}")

            logger.info(f"📝 Event payload: {json.dumps(event, indent=2, default=str)}")

            # Create the event
            created = self.service.events().insert(
                calendarId=self.calendar_id,
                body=event,
                sendUpdates='all'  # Send email notifications
            ).execute()

            logger.info(f"✅ Event created successfully!")
            logger.info(f"🔗 Event ID: {created['id']}")
            logger.info(f"🌐 Event Link: {created.get('htmlLink', 'N/A')}")

            return {
                "success": True,
                "event_id": created["id"],
                "event_link": created.get("htmlLink", ""),
                "message": f"✅ Event '{title}' created successfully.",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "calendar_id": self.calendar_id
            }
            
        except Exception as e:
            logger.error(f"❌ Error creating event: {e}")
            logger.error(f"📝 Event data: {locals()}")
            
            # More detailed error information
            error_msg = str(e)
            if "notFound" in error_msg:
                error_msg = f"Calendar not found. Make sure the service account has access to {self.calendar_id}"
            elif "forbidden" in error_msg:
                error_msg = f"Permission denied. The service account needs 'Make changes to events' permission on {self.calendar_id}"
            
            return {
                "success": False,
                "error": error_msg,
                "message": f"❌ Failed to create event: {error_msg}",
                "calendar_id": self.calendar_id
            }

    def list_events(self, days_ahead: int = 7) -> List[Dict]:
        """List upcoming events"""
        try:
            now = datetime.now(pytz.UTC)
            time_max = now + timedelta(days=days_ahead)
            
            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=now.isoformat(),
                timeMax=time_max.isoformat(),
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            logger.info(f"📋 Found {len(events)} upcoming events")
            
            return events
            
        except Exception as e:
            logger.error(f"❌ Error listing events: {e}")
            return []

    def delete_event(self, event_id: str) -> Dict:
        """Delete an event"""
        try:
            self.service.events().delete(
                calendarId=self.calendar_id,
                eventId=event_id
            ).execute()
            
            return {
                "success": True,
                "message": f"✅ Event {event_id} deleted successfully"
            }
            
        except Exception as e:
            logger.error(f"❌ Error deleting event: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"❌ Failed to delete event: {e}"
            }

    def verify_calendar_access(self) -> Dict:
        """Verify that we can access the target calendar"""
        try:
            # Try to get calendar info
            calendar_info = self.service.calendars().get(calendarId=self.calendar_id).execute()
            
            # Try to list events
            events = self.service.events().list(
                calendarId=self.calendar_id,
                maxResults=1
            ).execute()
            
            return {
                "success": True,
                "calendar_summary": calendar_info.get('summary'),
                "calendar_id": self.calendar_id,
                "access_confirmed": True,
                "message": f"✅ Successfully verified access to calendar: {calendar_info.get('summary')}"
            }
            
        except Exception as e:
            error_msg = str(e)
            if "notFound" in error_msg:
                suggestion = "Make sure the calendar exists and is shared with the service account"
            elif "forbidden" in error_msg:
                suggestion = "Make sure the service account has 'Make changes to events' permission"
            else:
                suggestion = "Check your service account credentials and permissions"
            
            return {
                "success": False,
                "error": error_msg,
                "calendar_id": self.calendar_id,
                "suggestion": suggestion,
                "message": f"❌ Cannot access calendar: {error_msg}"
            }