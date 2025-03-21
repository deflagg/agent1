from agent import agent, developer, VoiceMode, WorkflowCallbacks

from agents.voice import (
    SingleAgentVoiceWorkflow,
    VoicePipeline,
    AudioInput
)

from util import AudioPlayer, record_audio
from mcp_client import MCPClient
import asyncio

async def main():
    
    voice_mode = VoiceMode.ON_NO_STREAMING

    client1 = MCPClient(developer)
    agent.handoffs.append(client1.agent)
    client = MCPClient(agent)
    
    
    try:
        await client.connect_to_server("mcp_server.py")
        
        if voice_mode == VoiceMode.ON_NO_STREAMING:
            pipeline = VoicePipeline(
                workflow=SingleAgentVoiceWorkflow(agent, callbacks=WorkflowCallbacks())
            )

            audio_input = AudioInput(buffer=record_audio())

            result = await pipeline.run(audio_input)

            with AudioPlayer() as player:
                async for event in result.stream():
                    if event.type == "voice_stream_event_audio":
                        player.add_audio(event.data)
                        print("Received audio")
                    elif event.type == "voice_stream_event_lifecycle":
                        print(f"Received lifecycle event: {event.event}")
        elif voice_mode == VoiceMode.ON_STREAMING:
            pipeline = VoicePipeline(
                workflow=SingleAgentVoiceWorkflow(agent, callbacks=WorkflowCallbacks())
            )

            audio_input = AudioInput(buffer=record_audio())

            result = await pipeline.run(audio_input)

            with AudioPlayer() as player:
                async for event in result.stream():
                    if event.type == "voice_stream_event_audio":
                        player.add_audio(event.data)
                        print("Received audio")
                    elif event.type == "voice_stream_event_lifecycle":
                        print(f"Received lifecycle event: {event.event}")
        else:
            await client.chat_loop()
    finally:
        await client.cleanup()
   
if __name__ == "__main__":
    asyncio.run(main())
