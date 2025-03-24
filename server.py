# import asyncio
# import json
# import numpy as np
# from fastapi import FastAPI, WebSocket, WebSocketDisconnect
# from fastapi.staticfiles import StaticFiles
# from fastapi.middleware.cors import CORSMiddleware
# import uvicorn
# from typing import Dict, List, Any

# from agent import MyWorkflow
# from agents.voice import StreamedAudioInput, VoicePipeline

# app = FastAPI()

# # Add CORS middleware
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # For production, specify exact origins
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # Mount static files
# app.mount("/ui", StaticFiles(directory="ui"), name="ui")

# # Store active connections
# active_connections: Dict[str, WebSocket] = {}


# class ConnectionManager:
#     def __init__(self):
#         self.active_connections: Dict[str, Dict[str, Any]] = {}

#     async def connect(self, websocket: WebSocket, client_id: str):
#         await websocket.accept()
#         audio_input = StreamedAudioInput()
        
#         # Define callback for transcription events
#         async def on_transcription(transcription: str):
#             await websocket.send_json({
#                 "type": "transcription",
#                 "text": transcription
#             })
        
#         # Create workflow instance
#         workflow = MyWorkflow(
#             secret_word="dog",
#             on_start=lambda transcription: asyncio.create_task(on_transcription(transcription))
#         )
        
#         # Create pipeline with workflow
#         pipeline = VoicePipeline(workflow=workflow)
        
#         # Store connection and associated objects
#         self.active_connections[client_id] = {
#             "websocket": websocket,
#             "audio_input": audio_input,
#             "workflow": workflow,
#             "pipeline": pipeline,
#             "pipeline_task": None,
#             "processing": False,  # Flag to track if pipeline is currently processing
#             "audio_buffer_lock": asyncio.Lock()  # Lock for audio buffer access
#         }
        
#         return audio_input, workflow, pipeline

#     def disconnect(self, client_id: str):
#         if client_id in self.active_connections:
#             # Cancel any running pipeline task
#             pipeline_task = self.active_connections[client_id].get("pipeline_task")
#             if pipeline_task and not pipeline_task.done():
#                 pipeline_task.cancel()
            
#             del self.active_connections[client_id]

#     def get_connection(self, client_id: str):
#         return self.active_connections.get(client_id)


# connection_manager = ConnectionManager()


# @app.websocket("/ws")
# async def websocket_endpoint(websocket: WebSocket):
#     client_id = str(id(websocket))
#     audio_input, workflow, pipeline = await connection_manager.connect(websocket, client_id)
    
#     try:
#         while True:
#             data = await websocket.receive_text()
#             message = json.loads(data)
            
#             connection = connection_manager.get_connection(client_id)
#             if not connection:
#                 continue
                
#             if message["type"] == "audio":
#                 # Convert audio data from JSON to numpy array
#                 audio_data = np.array(message["data"], dtype=np.int16)
                
#                 # Use a lock to prevent race conditions with audio buffer
#                 async with connection["audio_buffer_lock"]:
#                     await audio_input.add_audio(audio_data)
            
#             elif message["type"] == "audio_end":
#                 # Don't start a new pipeline process if one is already running
#                 if connection["processing"]:
#                     await websocket.send_json({
#                         "type": "system",
#                         "text": "Still processing previous audio, please wait"
#                     })
#                     continue
                
#                 connection["processing"] = True
                
#                 # Define the pipeline processing task
#                 async def process_pipeline():
#                     try:
#                         print("=== Starting pipeline execution ===")
#                         # Get a snapshot of the current audio for processing
#                         # This ensures new audio chunks won't affect ongoing processing
                        
#                         # Execute the pipeline
#                         pipeline_result = await connection["pipeline"].run(audio_input)
#                         print(f"Pipeline result: {pipeline_result}")
                        
#                         if not pipeline_result:
#                             print("Pipeline returned no result")
#                             await websocket.send_json({
#                                 "type": "error",
#                                 "message": "Voice processing failed - no result from pipeline"
#                             })
#                             return
                        
#                         # Process the stream in this dedicated task to avoid interruption
#                         print("Beginning stream processing")
#                         try:
#                             async with asyncio.timeout(15):  # 15 second timeout
#                                 # Get the stream once and iterate through it
#                                 stream = pipeline_result.stream()
#                                 if not stream:
#                                     raise ValueError("Stream not available from pipeline result")
                                
#                                 # Process all events from the stream
#                                 async for event in stream:
#                                     print(f"Got event: {event}")
                                    
#                                     # Handle VoiceStreamEventText objects
#                                     if hasattr(event, 'type') and event.type == "voice_stream_event_text":
#                                         await websocket.send_json({
#                                             "type": "response",
#                                             "text": event.text
#                                         })
#                                     # Handle plain strings
#                                     elif isinstance(event, str):
#                                         await websocket.send_json({
#                                             "type": "response",
#                                             "text": event
#                                         })
#                                     # Other event types can be handled here
#                                     elif hasattr(event, 'type'):
#                                         if event.type == "voice_stream_event_audio":
#                                             # Audio event handling, if needed
#                                             pass
#                                         elif event.type == "voice_stream_event_lifecycle":
#                                             if event.event == "done":
#                                                 await websocket.send_json({
#                                                     "type": "system",
#                                                     "text": "Processing complete"
#                                                 })
                                
#                                 print("Stream processing completed successfully")
                                
#                         except asyncio.TimeoutError:
#                             print("Stream processing timed out")
#                             await websocket.send_json({
#                                 "type": "error",
#                                 "message": "Voice processing timed out"
#                             })
#                         except Exception as e:
#                             print(f"Error during stream processing: {str(e)}")
#                             import traceback
#                             traceback.print_exc()
#                             await websocket.send_json({
#                                 "type": "error",
#                                 "message": f"Stream processing error: {str(e)}"
#                             })
                            
#                     except Exception as e:
#                         print(f"Pipeline ERROR: {str(e)}")
#                         import traceback
#                         traceback.print_exc()
#                         await websocket.send_json({
#                             "type": "error",
#                             "message": str(e)
#                         })
#                     finally:
#                         # Always reset the processing flag when done
#                         connection["processing"] = False
#                         print("Pipeline processing completed")
                
#                 # Create and start the pipeline task - we don't await it here
#                 # to allow the WebSocket to continue receiving messages
#                 connection["pipeline_task"] = asyncio.create_task(process_pipeline())
    
#     except WebSocketDisconnect:
#         print(f"Client {client_id} disconnected")
#         connection_manager.disconnect(client_id)
#     except Exception as e:
#         print(f"Unexpected error: {str(e)}")
#         import traceback
#         traceback.print_exc()
#         await websocket.send_json({
#             "type": "error",
#             "message": str(e)
#         })
#         connection_manager.disconnect(client_id)


# @app.get("/")
# async def get_root():
#     return {"message": "Voice Assistant API is running. Go to /ui to access the web interface."}


# if __name__ == "__main__":
#     uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True) 