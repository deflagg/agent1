import asyncio
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn
from fastapi.middleware.cors import CORSMiddleware

# Import the Agents SDK voice packages.
# (Make sure you have installed openai[voice] and the required Agents SDK dependencies.)
from agents.voice import VoicePipeline, StreamedAudioInput, SingleAgentVoiceWorkflow
from agents import Agent
from agents.voice import OpenAIVoiceModelProvider, VoicePipelineConfig, STTModelSettings, TTSModelSettings

from dotenv import load_dotenv
load_dotenv()

app = FastAPI()


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/ui", StaticFiles(directory="frontend"), name="ui")



# Optional: serve the index.html from the server.
@app.get("/")
async def get_root():
    return {"message": "Voice Assistant API is running. Go to /ui to access the web interface."}


# Create an agent with voice capabilities.
agent = Agent(
    name="Assistant",
    model="gpt-4o-mini",  # Update with your voice-enabled model name.
    instructions="""You are an AI assistant designed to assist users with their inquiries. 
    When a user requests code that can be executed in a web browser, only provide the appropriate code snippet. 
    For all other inquiries, respond with a helpful and informative answer."""
)

voice_instructions = """Voice Affect: Relaxed, friendly, natural
Tone: Genuine, casual, supportive
Pacing: Easygoing; conversational speed
Emotions: Warm, understanding, reassuring
Pronunciation: Clear, everyday speech; natural emphasis on important points
Pauses: Short, natural breaks for reflection
Phrasing: Informal, relatable, familiar"""

# Create a voice pipeline using a single-agent workflow.
pipeline = VoicePipeline(
    workflow=SingleAgentVoiceWorkflow(agent),
    config=VoicePipelineConfig(
        model_provider=OpenAIVoiceModelProvider(),
        stt_settings=STTModelSettings(language="en", turn_detection={"type": "semantic_vad", "eagerness": "medium"}),
        tts_settings=TTSModelSettings(voice="sage", buffer_size=32, dtype=np.int16, instructions=voice_instructions, speed=1.0)
    )
)

@app.websocket("/ws")
async def audio_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket connection accepted")
    # Create a streamed audio input container.
    audio_input = StreamedAudioInput()
    # Run the voice pipeline in multi-turn (streaming) mode.
    result = await pipeline.run(audio_input)
    
    async def send_audio():
        try:
            # Iterate over streaming events from the pipeline.
            async for event in result.stream():
                # Check for audio events from the TTS part.
                if event.type == "voice_stream_event_audio":
                    audio_chunk: np.ndarray = event.data  # Expected to be an int16 numpy array.
                    await websocket.send_bytes(audio_chunk.tobytes())
                # If the pipeline signals end-of-session, break out.
                elif event.type == "voice_stream_event_lifecycle" and event.event == "session_ended":
                    break
        except Exception as e:
            print("Error sending audio:", e)
    
    send_task = asyncio.create_task(send_audio())
    
    try:
        # Continuously receive PCM audio chunks from the client.
        async for message in websocket.iter_bytes():
            # Convert the incoming bytes to a NumPy array (16-bit PCM).
            audio_chunk = np.frombuffer(message, dtype=np.int16)
            await audio_input.add_audio(audio_chunk)
    except WebSocketDisconnect:
        print("Client disconnected.")
    finally:
        send_task.cancel()

if __name__ == "__main__":
    # Run the server with: uvicorn server:app --reload
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
