A conversational AI agent that helps users book appointments on Google Calendar through natural language chat.

## 🚀 Features

- **Natural Language Processing**: Powered by Google's Gemini AI
- **Google Calendar Integration**: Real-time availability checking and booking
- **Conversational Interface**: Streamlit-based chat interface
- **Smart Scheduling**: Intelligent time slot suggestions
- **Session Management**: Maintains conversation context

## 🛠️ Tech Stack

- **Backend**: FastAPI + Python
- **AI Framework**: LangGraph + LangChain
- **Frontend**: Streamlit
- **LLM**: Google Gemini API
- **Calendar**: Google Calendar API

## 📋 Prerequisites

1. **Google Cloud Service Account**:
   - Create a project in Google Cloud Console
   - Enable Google Calendar API
   - Create a service account
   - Download the JSON credentials file

2. **Gemini API Key**:
   - Get your API key from Google AI Studio

## 🔧 Setup Instructions

### 1. Clone the Repository
```bash
git clone <your-repo-url>
cd calendar-booking-agent
```

### 2. Install Dependencies

**Backend**:
```