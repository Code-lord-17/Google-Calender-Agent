# calendar_service.py

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import os
import pickle
from googleapiclient.discovery import build
from datetime import datetime, timedelta

SCOPES = ['https://www.googleapis.com/auth/calendar']

class GoogleCalendarService:
    def __init__(self, credentials_path='oauth2_credentials.json', token_path='token.pickle', calendar_id='primary'):
        self.calendar_id = calendar_id
        self.service = self._authenticate(credentials_path, token_path)

    def _authenticate(self, credentials_path: str, token_path: str):
        creds = None

        # Load token if it exists
        if os.path.exists(token_path):
            with open(token_path, 'rb') as token_file:
                creds = pickle.load(token_file)

        # Refresh or initiate flow if token invalid
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials_path,
                    SCOPES,
                )
                creds = flow.run_local_server(
                    port=8000,
                )
            # Save token
            with open(token_path, 'wb') as token_file:
                pickle.dump(creds, token_file)

        return build('calendar', 'v3', credentials=creds)

    def get_available_slots(self, date: str, duration_minutes: int = 60):
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d")
            start_time = target_date.replace(hour=9, minute=0, second=0, microsecond=0)
            end_time = target_date.replace(hour=17, minute=0, second=0, microsecond=0)

            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=start_time.isoformat() + 'Z',
                timeMax=end_time.isoformat() + 'Z',
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])
            available_slots = []
            current_time = start_time

            for event in events:
                event_start = datetime.fromisoformat(
                    event['start'].get('dateTime', event['start'].get('date')).replace('Z', '+00:00')
                ).replace(tzinfo=None)
                if current_time + timedelta(minutes=duration_minutes) <= event_start:
                    available_slots.append({
                        'start': current_time.strftime("%H:%M"),
                        'end': (current_time + timedelta(minutes=duration_minutes)).strftime("%H:%M"),
                        'datetime': current_time.isoformat()
                    })
                event_end = datetime.fromisoformat(
                    event['end'].get('dateTime', event['end'].get('date')).replace('Z', '+00:00')
                ).replace(tzinfo=None)
                current_time = max(current_time, event_end)

            while current_time + timedelta(minutes=duration_minutes) <= end_time:
                available_slots.append({
                    'start': current_time.strftime("%H:%M"),
                    'end': (current_time + timedelta(minutes=duration_minutes)).strftime("%H:%M"),
                    'datetime': current_time.isoformat()
                })
                current_time += timedelta(minutes=30)

            return available_slots[:5]

        except Exception as e:
            print(f"Error getting available slots: {e}")
            return []

    def create_event(self, title, start_time, end_time, description="", attendees=None):
        try:
            event = {
                'summary': title,
                'description': description,
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': 'IST',
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': 'IST',
                },
            }
            if attendees:
                event['attendees'] = [{'email': email} for email in attendees]

            print("📅 Creating event with payload:", event)  # <-- Log payload

            event_result = self.service.events().insert(
                calendarId=self.calendar_id,
                body=event
            ).execute()

            print("✅ Event created:", event_result)  # <-- Log result

            return event_result.get('id')

        except Exception as e:
            print("❌ Error creating event:", e)  # <-- Log error
            return None
