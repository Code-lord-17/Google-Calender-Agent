# main.py
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from .models import ChatMessage, ChatResponse
from .agent import TailorTalkAgent
from .config import Config
import uvicorn
import traceback

app = FastAPI(title="TailorTalk API", version="1.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Set specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize agent
try:
    agent = TailorTalkAgent()
except Exception as e:
    print("❌ Failed to initialize TailorTalkAgent:")
    traceback.print_exc()
    agent = None  # Prevent crash, but /chat will fail gracefully

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "TailorTalk"}

# Root
@app.get("/")
async def root():
    return {"message": "TailorTalk API is running!"}

# Chat endpoint
@app.post("/chat", response_model=ChatResponse)
async def chat(message: ChatMessage):
    try:
        if not agent:
            raise ValueError("Agent is not initialized. Check startup errors.")

        print("📩 Incoming message:", message.message)

        result = agent.chat(message.message)
        print("✅ Agent response:", result)

        return ChatResponse(
            response=result["response"],
            booking_status=result.get("booking_status"),
            event_details=result.get("extracted_info")
        )

    except Exception as e:
        print("❌ Error in /chat endpoint:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# Run the app
if __name__ == "__main__":
    config = Config()
    uvicorn.run("app.main:app", host=config.HOST, port=config.PORT, reload=True)
