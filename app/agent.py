# agent.py
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from typing import Dict, Any
from datetime import datetime, timedelta
import json
import re
from .calendar_service import GoogleCalendarService
from .config import Config

config = Config()

llm = ChatGoogleGenerativeAI(
    model=config.MODEL_NAME,
    temperature=config.TEMPERATURE,
    google_api_key=config.GOOGLE_API_KEY,
    convert_system_message_to_human=True
)

class AgentState:
    def __init__(self):
        self.messages = []
        self.user_intent = None
        self.extracted_info = {}
        self.booking_status = None
        self.current_step = "initial"

def classify_intent(state: AgentState) -> AgentState:
    last_message = state.messages[-1].lower() if state.messages else ""
    if any(word in last_message for word in ["book", "schedule", "appointment", "meeting"]):
        state.user_intent = "book_appointment"
    elif any(word in last_message for word in ["available", "free", "slots", "when"]):
        state.user_intent = "check_availability"
    elif any(word in last_message for word in ["cancel", "delete", "remove"]):
        state.user_intent = "cancel_appointment"
    else:
        state.user_intent = "general_chat"
    return state

def extract_information(state: AgentState) -> AgentState:
    message = state.messages[-1] if state.messages else ""

    # Keep previous values unless overwritten
    extracted_date = state.extracted_info.get("date")
    extracted_time = state.extracted_info.get("time")

    # --- DATE Extraction ---
    date_patterns = [
        r'\b(\d{4}-\d{2}-\d{2})\b',
        r'\b(today|tomorrow|yesterday|tonight)\b',  # ← added "tonight"
        r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b'
    ]

    for pattern in date_patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            word = match.group(1).lower() if match.lastindex == 1 else None
            if word == "today":
                extracted_date = datetime.now().strftime("%Y-%m-%d")
            elif word == "tomorrow":
                extracted_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
            elif word == "yesterday":
                extracted_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            elif word == "tonight":
                extracted_date = datetime.now().strftime("%Y-%m-%d")
            elif pattern == date_patterns[2]:
                month, day, year = match.groups()
                extracted_date = f"{year}-{int(month):02d}-{int(day):02d}"
            else:
                extracted_date = match.group(1)
            break  # Stop after first date match

    # --- TIME Extraction ---
    time_patterns = [
        r'\b(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)\b',
        r'\b(\d{1,2})\s*(AM|PM|am|pm)\b',
        r'\b(\d{1,2}):(\d{2})\b'
    ]
    for pattern in time_patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            extracted_time = match.group(0).strip()
            break  # Stop after first time match

    # Update state
    if extracted_date:
        state.extracted_info["date"] = extracted_date
    if extracted_time:
        state.extracted_info["time"] = extracted_time

    return state


def format_12h(date_str: str, time_str: str) -> str:
    for fmt in ("%Y-%m-%d %I:%M %p", "%Y-%m-%d %I %p", "%Y-%m-%d %H:%M"):
        try:
            dt = datetime.strptime(f"{date_str} {time_str}", fmt)
            return dt.strftime("%I:%M %p")
        except ValueError:
            continue
    return time_str

def generate_response(state: AgentState) -> AgentState:
    from .calendar_service import GoogleCalendarService
    calendar_service = GoogleCalendarService(
        credentials_path="oauth2_credentials.json",
        token_path="token.pickle"
    )

    system_prompt = """You are TailorTalk, a helpful AI assistant for booking calendar appointments.
- When users want to book, first check availability.
- Confirm all details before booking.
- Provide clear next steps.
- If information is missing, ask for it naturally."""

    context = {
        "intent": state.user_intent,
        "extracted_info": state.extracted_info,
        "conversation_history": state.messages[-5:],
        "current_step": state.current_step
    }

    user_prompt = f"""Context: {json.dumps(context, indent=2)}
User message: {state.messages[-1]}

Respond as TailorTalk. If booking or checking availability, clearly guide the user and confirm info first."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    response = llm.invoke(messages)
    content = response.content
    print("🧠 Gemini response:", content)

    date = state.extracted_info.get("date")
    time = state.extracted_info.get("time")

    if state.user_intent == "check_availability" and date:
        slots = calendar_service.get_available_slots(date)
        state.extracted_info["slots"] = slots
        content += "\n\n🗓 **Available slots on {}:** {}".format(
            date,
            ', '.join(f"{slot['start']} - {slot['end']}" for slot in slots) if slots else "No available slots."
        )

    if state.user_intent == "book_appointment" and date and time:
        try:
            for fmt in ("%Y-%m-%d %I:%M %p", "%Y-%m-%d %I %p", "%Y-%m-%d %H:%M"):
                try:
                    start_datetime = datetime.strptime(f"{date} {time}", fmt)
                    break
                except ValueError:
                    continue
            else:
                raise ValueError(f"Unsupported time format: {time}")

            end_datetime = start_datetime + timedelta(minutes=60)
            formatted_time = start_datetime.strftime("%I:%M %p")

            event_id = calendar_service.create_event(
                title="Appointment",
                start_time=start_datetime,
                end_time=end_datetime,
                description="Scheduled via TailorTalk",
                attendees=[]
            )
            if event_id:
                state.booking_status = "confirmed"
                content += (
                    f"\n\n✅ **Booking Confirmed!**\n"
                    f"Date: {date}\n"
                    f"Time: {formatted_time} - {(end_datetime).strftime('%I:%M %p')}\n"
                    f"Event ID: {event_id}"
                )
            else:
                content += "\n⚠️ Failed to book the appointment. Please try again later."
        except Exception as e:
            content += f"\n❌ Error while booking: {str(e)}"

    state.messages.append(content)
    return state

def create_agent():
    workflow = StateGraph(AgentState)
    workflow.add_node("classify_intent", classify_intent)
    workflow.add_node("extract_information", extract_information)
    workflow.add_node("generate_response", generate_response)
    workflow.add_edge("classify_intent", "extract_information")
    workflow.add_edge("extract_information", "generate_response")
    workflow.add_edge("generate_response", END)
    workflow.set_entry_point("classify_intent")
    return workflow.compile()

class TailorTalkAgent:
    def __init__(self):
        self.agent = create_agent()
        self.state = AgentState()

    def chat(self, message: str) -> Dict[str, Any]:
        self.state.messages.append(message)
        result = self.agent.invoke(self.state)
        response = result.messages[-1] if result.messages else "I'm sorry, I couldn't process that."
        return {
            "response": response,
            "booking_status": result.booking_status,
            "extracted_info": result.extracted_info
        }
