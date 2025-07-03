import google.generativeai as genai
from datetime import datetime, timedelta
import json
import re
from typing import Dict, List, Optional, Any
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CalendarBookingAgent:
    def __init__(self, gemini_api_key: str, calendar_service):
        """Initialize the Calendar Booking Agent"""
        self.calendar_service = calendar_service
        self.sessions = {}
        
        # Configure Gemini
        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel('gemini-pro')
        
        # System prompt for the AI
        self.system_prompt = """
        You are a helpful calendar booking assistant. Your job is to help users:
        1. Book meetings and appointments
        2. Check availability
        3. Reschedule meetings
        4. Cancel meetings
        
        Always respond in a friendly, professional manner. When booking meetings, you need:
        - Date and time
        - Duration (default to 60 minutes if not specified)
        - Meeting title/purpose
        - Attendees (if any)
        
        For responses, always include:
        - A helpful response message
        - Whether a booking was confirmed (true/false)
        - Available time slots if needed
        
        Extract information naturally from user messages. Common patterns:
        - "tomorrow at 2 PM" 
        - "next Friday from 10 to 11"
        - "schedule a call with John"
        - "book a meeting for next week"
        """
    
    def process_message(self, message: str, session_id: str) -> Dict[str, Any]:
        """Process user message and return structured response"""
        try:
            # Initialize session if needed
            if session_id not in self.sessions:
                self.sessions[session_id] = {
                    "step": "initial",
                    "context": {},
                    "pending_booking": {}
                }
            
            session = self.sessions[session_id]
            
            # Analyze the message for intent and extract information
            intent_analysis = self._analyze_intent(message)
            extracted_info = self._extract_booking_info(message)
            
            logger.info(f"Intent: {intent_analysis}, Extracted: {extracted_info}")
            
            # Handle different intents
            if intent_analysis["intent"] == "book_meeting":
                return self._handle_booking_request(message, session, extracted_info)
            elif intent_analysis["intent"] == "check_availability":
                return self._handle_availability_check(message, session, extracted_info)
            elif intent_analysis["intent"] == "list_meetings":
                return self._handle_list_meetings(message, session)
            elif intent_analysis["intent"] == "cancel_meeting":
                return self._handle_cancel_meeting(message, session)
            else:
                return self._handle_general_query(message, session)
                
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            return {
                "response": "I apologize, but I encountered an error processing your request. Please try again.",
                "booking_confirmed": False,
                "available_slots": [],
                "session_id": session_id
            }
    
    def _analyze_intent(self, message: str) -> Dict[str, Any]:
        """Analyze user intent using keyword matching and patterns"""
        message_lower = message.lower()
        
        booking_keywords = ['book', 'schedule', 'arrange', 'set up', 'create', 'plan', 'meeting', 'appointment', 'call']
        availability_keywords = ['available', 'availability', 'free', 'busy', 'when can', 'what time']
        list_keywords = ['list', 'show', 'what meetings', 'my schedule', 'upcoming']
        cancel_keywords = ['cancel', 'delete', 'remove', 'reschedule']
        
        if any(keyword in message_lower for keyword in booking_keywords):
            return {"intent": "book_meeting", "confidence": 0.8}
        elif any(keyword in message_lower for keyword in availability_keywords):
            return {"intent": "check_availability", "confidence": 0.8}
        elif any(keyword in message_lower for keyword in list_keywords):
            return {"intent": "list_meetings", "confidence": 0.8}
        elif any(keyword in message_lower for keyword in cancel_keywords):
            return {"intent": "cancel_meeting", "confidence": 0.8}
        else:
            return {"intent": "general", "confidence": 0.5}
    
    def _extract_booking_info(self, message: str) -> Dict[str, Any]:
        """Extract booking information from message"""
        info = {
            "datetime": None,
            "duration": 60,  # Default 60 minutes
            "title": "Meeting",
            "attendees": []
        }
        
        # Extract date/time
        info["datetime"] = self._extract_datetime(message)
        
        # Extract duration
        info["duration"] = self._extract_duration(message)
        
        # Extract title/purpose
        info["title"] = self._extract_title(message)
        
        # Extract attendees (basic email pattern)
        info["attendees"] = self._extract_attendees(message)
        
        return info
    
    def _extract_datetime(self, message: str) -> Optional[datetime]:
        """Extract datetime from natural language"""
        now = datetime.now()
        message_lower = message.lower()
        
        # Handle relative dates
        if 'tomorrow' in message_lower:
            base_date = now + timedelta(days=1)
        elif 'today' in message_lower:
            base_date = now
        elif 'next week' in message_lower:
            base_date = now + timedelta(weeks=1)
        elif 'monday' in message_lower:
            days_ahead = 0 - now.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            base_date = now + timedelta(days_ahead)
        elif 'tuesday' in message_lower:
            days_ahead = 1 - now.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            base_date = now + timedelta(days_ahead)
        elif 'wednesday' in message_lower:
            days_ahead = 2 - now.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            base_date = now + timedelta(days_ahead)
        elif 'thursday' in message_lower:
            days_ahead = 3 - now.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            base_date = now + timedelta(days_ahead)
        elif 'friday' in message_lower:
            days_ahead = 4 - now.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            base_date = now + timedelta(days_ahead)
        else:
            base_date = now
        
        # Extract time
        time_patterns = [
            r'(\d{1,2}):(\d{2})\s*(am|pm)',
            r'(\d{1,2})\s*(am|pm)',
            r'at\s*(\d{1,2})',
        ]
        
        for pattern in time_patterns:
            match = re.search(pattern, message_lower)
            if match:
                try:
                    groups = match.groups()
                    if len(groups) >= 2 and groups[1] in ['am', 'pm']:
                        hour = int(groups[0])
                        minute = int(groups[1]) if len(groups) > 2 and groups[1].isdigit() else 0
                        if groups[-1] == 'pm' and hour != 12:
                            hour += 12
                        elif groups[-1] == 'am' and hour == 12:
                            hour = 0
                    else:
                        hour = int(groups[0])
                        minute = 0
                        # Assume PM for business hours if not specified
                        if 8 <= hour <= 12:
                            pass  # Could be AM
                        elif 1 <= hour <= 7:
                            hour += 12  # Likely PM
                    
                    return base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                except (ValueError, IndexError):
                    continue
        
        return None
    
    def _extract_duration(self, message: str) -> int:
        """Extract meeting duration in minutes"""
        duration_patterns = [
            (r'(\d+)\s*hours?', 60),
            (r'(\d+)\s*hour', 60),
            (r'(\d+)\s*h\b', 60),
            (r'(\d+)\s*minutes?', 1),
            (r'(\d+)\s*mins?', 1),
            (r'(\d+)\s*m\b', 1),
        ]
        
        for pattern, multiplier in duration_patterns:
            match = re.search(pattern, message.lower())
            if match:
                return int(match.group(1)) * multiplier
        
        # Check for time ranges like "2 to 3" or "2-3"
        range_match = re.search(r'(\d+)(?:\s*(?:to|-)\s*)(\d+)', message)
        if range_match:
            start_hour = int(range_match.group(1))
            end_hour = int(range_match.group(2))
            if end_hour > start_hour:
                return (end_hour - start_hour) * 60
        
        return 60  # Default 1 hour
    
    def _extract_title(self, message: str) -> str:
        """Extract meeting title from message"""
        # Simple title extraction - look for common patterns
        message_lower = message.lower()
        
        # Look for specific meeting types
        if 'standup' in message_lower or 'stand up' in message_lower:
            return "Team Standup"
        elif 'review' in message_lower:
            return "Review Meeting"
        elif 'interview' in message_lower:
            return "Interview"
        elif 'call' in message_lower:
            return "Call"
        elif 'demo' in message_lower:
            return "Demo"
        elif 'sync' in message_lower:
            return "Sync Meeting"
        else:
            return "Meeting"
    
    def _extract_attendees(self, message: str) -> List[str]:
        """Extract email addresses from message"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        return re.findall(email_pattern, message)
    
    def _handle_booking_request(self, message: str, session: Dict, extracted_info: Dict) -> Dict[str, Any]:
        """Handle meeting booking request"""
        session["pending_booking"].update(extracted_info)
        
        # Check if we have all required information
        if not extracted_info["datetime"]:
            return {
                "response": "I'd be happy to book that meeting! Could you please specify the date and time? For example: 'tomorrow at 2 PM' or 'Friday at 10:30 AM'",
                "booking_confirmed": False,
                "available_slots": self._get_suggested_slots(),
                "session_id": session.get("step", "")
            }
        
        try:
            # Check availability
            start_time = extracted_info["datetime"]
            end_time = start_time + timedelta(minutes=extracted_info["duration"])
            
            event_result = self.calendar_service.create_event(
                title=extracted_info["title"],
                start_time=start_time,
                end_time=end_time,
                description="Booked via Calendar Assistant",
                attendee_emails=extracted_info["attendees"]
            )

            if event_result.get("success"):
                response = f"✅ Meeting booked successfully!\n\n"
                response += f"📅 **{extracted_info['title']}**\n"
                response += f"🗓️ {start_time.strftime('%A, %B %d, %Y')}\n"
                response += f"🕐 {start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')}\n"

                if extracted_info["attendees"]:
                    response += f"👥 Attendees: {', '.join(extracted_info['attendees'])}\n"

                if event_result.get("event_link"):
                    response += f"[🔗 View Event]({event_result['event_link']})\n"

                return {
                    "response": response,
                    "booking_confirmed": True,
                    "available_slots": [],
                    "session_id": session.get("step", "")
                }

            else:
                return {
                    "response": f"❌ I couldn't book the meeting. Reason: {event_result.get('error', 'Unknown error')}",
                    "booking_confirmed": False,
                    "available_slots": self._get_suggested_slots(),
                    "session_id": session.get("step", "")
                }

        except Exception as e:
            logger.error(f"Booking error: {str(e)}")
            return {
                "response": "❌ An unexpected error occurred while booking. Please try again later.",
                "booking_confirmed": False,
                "available_slots": self._get_suggested_slots(),
                "session_id": session.get("step", "")
            }

    
    def _handle_availability_check(self, message: str, session: Dict, extracted_info: Dict) -> Dict[str, Any]:
        """Handle availability check"""
        try:
            # Get availability for the next 7 days
            available_slots = self._get_availability_slots()
            
            response = "📅 **Your availability for the next 7 days:**\n\n"
            for slot in available_slots[:10]:  # Show first 10 slots
                response += f"• {slot}\n"
            
            return {
                "response": response,
                "booking_confirmed": False,
                "available_slots": available_slots,
                "session_id": session.get("step", "")
            }
            
        except Exception as e:
            logger.error(f"Availability check error: {str(e)}")
            return {
                "response": "I'm having trouble checking your calendar right now. Please try again in a moment.",
                "booking_confirmed": False,
                "available_slots": [],
                "session_id": session.get("step", "")
            }
    
    def _handle_list_meetings(self, message: str, session: Dict) -> Dict[str, Any]:
        """Handle list meetings request"""
        response = "📅 **Your upcoming meetings:**\n\nI'm working on fetching your calendar events. This feature will show your scheduled meetings."
        
        return {
            "response": response,
            "booking_confirmed": False,
            "available_slots": [],
            "session_id": session.get("step", "")
        }
    
    def _handle_cancel_meeting(self, message: str, session: Dict) -> Dict[str, Any]:
        """Handle cancel meeting request"""
        response = "To cancel a meeting, please specify which meeting you'd like to cancel. You can say something like 'cancel my 2 PM meeting tomorrow' or 'cancel the client meeting'."
        
        return {
            "response": response,
            "booking_confirmed": False,
            "available_slots": [],
            "session_id": session.get("step", "")
        }
    
    def _handle_general_query(self, message: str, session: Dict) -> Dict[str, Any]:
        """Handle general queries"""
        try:
            # Use Gemini for general conversation
            prompt = f"{self.system_prompt}\n\nUser: {message}\n\nRespond helpfully about calendar and meeting management."
            
            response = self.model.generate_content(prompt)
            
            return {
                "response": response.text if response.text else "I can help you book meetings, check availability, or manage your calendar. What would you like to do?",
                "booking_confirmed": False,
                "available_slots": [],
                "session_id": session.get("step", "")
            }
            
        except Exception as e:
            logger.error(f"General query error: {str(e)}")
            return {
                "response": "I can help you book meetings, check your availability, list your schedule, or cancel meetings. What would you like to do?",
                "booking_confirmed": False,
                "available_slots": [],
                "session_id": session.get("step", "")
            }
    
    def _get_suggested_slots(self) -> List[str]:
        """Get suggested available time slots"""
        now = datetime.now()
        slots = []
        
        # Generate next 5 business days, 9 AM to 5 PM slots
        for day in range(1, 6):
            date = now + timedelta(days=day)
            if date.weekday() < 5:  # Monday = 0, Friday = 4
                for hour in [9, 10, 11, 14, 15, 16]:  # 9-11 AM, 2-4 PM
                    slot_time = date.replace(hour=hour, minute=0, second=0, microsecond=0)
                    slot_str = slot_time.strftime('%A, %B %d at %I:%M %p')
                    slots.append(slot_str)
        
        return slots[:10]  # Return first 10 slots
    
    def _get_availability_slots(self) -> List[str]:
        """Get formatted availability slots"""
        return self._get_suggested_slots()