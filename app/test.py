from google.oauth2 import service_account
from googleapiclient.discovery import build
from typing import Optional

# ======= Configuration =======
SERVICE_ACCOUNT_FILE = 'service_account.json'  # Path to your service account file
CALENDAR_ID = 'primary'  # Or replace with actual calendar ID
EVENT_ID = 'ljlponi33fmuphq7gh9mmobkj4'  # Replace with your actual event ID
MY_EMAIL = 'phm23038@gmail.com'  # Your Gmail address
SCOPES = ['https://www.googleapis.com/auth/calendar']
# =============================

def get_calendar_service():
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    service = build("calendar", "v3", credentials=credentials)
    return service

def get_event_by_id(service, calendar_id: str, event_id: str) -> Optional[dict]:
    try:
        event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()
        return event
    except Exception as e:
        print(f"❌ Error fetching event: {e}")
        return None

def add_self_as_attendee(service, calendar_id: str, event: dict, email: str):
    attendees = event.get("attendees", [])
    if not any(att.get("email") == email for att in attendees):
        attendees.append({"email": email})
        event["attendees"] = attendees
        try:
            updated_event = service.events().patch(
                calendarId=calendar_id,
                eventId=event["id"],
                body=event,
                sendUpdates="all"
            ).execute()
            print(f"✅ Added {email} as attendee.")
        except Exception as e:
            print(f"❌ Error updating event with attendee: {e}")
    else:
        print(f"ℹ️ {email} is already an attendee.")

if __name__ == "__main__":
    print("🔎 Checking event...")
    service = get_calendar_service()
    event = get_event_by_id(service, CALENDAR_ID, EVENT_ID)

    if event:
        print("✅ Event Found!")
        print(f"📅 Title: {event.get('summary')}")
        print(f"🕒 Start: {event.get('start').get('dateTime')}")
        print(f"🕒 End: {event.get('end').get('dateTime')}")
        print(f"📍 Description: {event.get('description', 'No description')}")
        add_self_as_attendee(service, CALENDAR_ID, event, MY_EMAIL)
    else:
        print("❌ Event not found.")
