import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
import pytz


class GoogleCalendarService:
    def __init__(self):
        self.service = self._build_service()

    def _build_service(self):
        """Builds the Google Calendar service from service account JSON in env variable."""
        SCOPES = ['https://www.googleapis.com/auth/calendar']
        credentials_raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

        if not credentials_raw:
            raise Exception("Missing GOOGLE_SERVICE_ACCOUNT_JSON in environment variables")

        try:
            credentials_info = json.loads(credentials_raw)
            credentials = service_account.Credentials.from_service_account_info(
                credentials_info,
                scopes=SCOPES
            )
            return build("calendar", "v3", credentials=credentials)
        except json.JSONDecodeError:
            raise Exception("Invalid JSON in GOOGLE_SERVICE_ACCOUNT_JSON")

    def get_calendar_id(self) -> str:
        """
        Returns the target calendar ID.
        Replace 'primary' with an email like 'your-calendar@gmail.com'
        if you want to write to a specific calendar.
        """
        return "primary"  # or your test calendar email if shared with service account

    def check_availability(self, start_time: datetime, end_time: datetime) -> bool:
        try:
            start_time = start_time.astimezone(pytz.UTC)
            end_time = end_time.astimezone(pytz.UTC)

            events_result = self.service.events().list(
                calendarId=self.get_calendar_id(),
                timeMin=start_time.isoformat(),
                timeMax=end_time.isoformat(),
                singleEvents=True,
                orderBy="startTime"
            ).execute()

            return len(events_result.get("items", [])) == 0
        except Exception as e:
            print("⚠️ Availability check error:", e)
            return False

    def get_available_slots(self, date: datetime, duration_hours: int = 1) -> List[str]:
        """
        Returns available time slots on a given date (9am–5pm by default).
        """
        slots = []
        tz = pytz.UTC
        for hour in range(9, 18 - duration_hours):
            start = date.replace(hour=hour, minute=0, second=0, microsecond=0, tzinfo=tz)
            end = start + timedelta(hours=duration_hours)
            if self.check_availability(start, end):
                slots.append(start.strftime("%Y-%m-%d %H:%M"))
        return slots

    def create_event(self,
                     title: str,
                     start_time: datetime,
                     end_time: datetime,
                     description: str = "",
                     attendee_emails: Optional[List[str]] = None) -> Dict:
        """
        Creates a calendar event and returns the status.
        """
        try:
            start_time = start_time.astimezone(pytz.UTC)
            end_time = end_time.astimezone(pytz.UTC)

            event = {
                "summary": title,
                "description": description,
                "start": {"dateTime": start_time.isoformat(), "timeZone": "UTC"},
                "end": {"dateTime": end_time.isoformat(), "timeZone": "UTC"},
            }

            if attendee_emails:
                event["attendees"] = [{"email": email} for email in attendee_emails]

            created = self.service.events().insert(
                calendarId=self.get_calendar_id(),
                body=event
            ).execute()

            return {
                "success": True,
                "event_id": created["id"],
                "event_link": created.get("htmlLink", ""),
                "message": f"✅ Event '{title}' created.",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat()
            }
        except Exception as e:
            print("❌ Error creating event:", e)
            return {
                "success": False,
                "error": str(e),
                "message": "❌ Failed to create event."
            }
