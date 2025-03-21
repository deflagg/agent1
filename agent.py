from dotenv import load_dotenv
from agents import Agent, Runner, function_tool, AgentHooks, ItemHelpers
from agents.voice import SingleAgentVoiceWorkflow, SingleAgentWorkflowCallbacks, VoicePipeline, AudioInput
from langchain_openai import ChatOpenAI
from browser_use import Agent as BrowserAgent, Browser, BrowserConfig
from pydantic import BaseModel, Field
import asyncio
from mcp_client import MCPClient
import numpy as np
import sounddevice as sd

from util import AudioPlayer, record_audio

load_dotenv()

browser = Browser(
    # config=BrowserConfig(
    #     chrome_instance_path='C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
    # )
)

@function_tool
async def search_web(query: str) -> str:
    """
    Search the web for the answer to the query. Search for current information.
    
    args:
        query: The query to search the web for
        
    returns:
        str: The answer to the query
    """
    agent = BrowserAgent(
            task=query,
            llm=ChatOpenAI(model="gpt-4o-mini"),
            use_vision=True, 
            browser=browser
        )
    
    result = await agent.run()
    return result

developer = Agent(
    name="Developer",
    instructions="""
    Your name is Tubo Magellan.
    You are a developer who develops code.
    You have a tool to execute and debug code.
    Test code with the tool before returning it.
    """
)

tester = Agent(
    name="Tester",
    instructions="""
    You are a tester who tests code.
    You have a tool to execute and debug code.
    """,
    handoff_description="Specialist agent for testing code",
)

researcher = Agent(
    name="Researcher",
    instructions="""
    You are a researcher who researches code.
    """,
    handoff_description="Specialist agent for all research",
    model="gpt-4o-mini",
    tools=[search_web]
)

class Task(BaseModel):
    agent: str = Field(description="Agent name")
    task: str = Field(description="Task description")
    

class Plan(BaseModel):
    goal: str = Field(description="Goal of the plan")
    tasks: list[Task] = Field(description="List of tasks for agents")

manager = Agent(
    name="Manager",
    instructions="""
    You are a manager who coordinates tasks between agents.
    Create a plan for the agents to complete the task.
    """, 
    handoffs=[developer, tester],
    model="gpt-4o"
)

agent = Agent(
        name="Assistant",
        instructions=f"""
        Use the available tools to help the user with their requests.
        When using tools, provide clear and concise responses based on the tool output.
        
        If you have a tool to execute code, write python code in a code block to perform any calculations or analysis.
        Write code in a code blocks
        ```python
        code
        ```
        """,
        handoffs=[developer],
        tools=[search_web]
    )

class WorkflowCallbacks(SingleAgentWorkflowCallbacks):
    def on_run(self, workflow: SingleAgentVoiceWorkflow, transcription: str) -> None:
        print(f"[debug] on_run called with transcription: {transcription}")

async def main():
    voice_mode = True
    
    client1 = MCPClient(developer)
    agent.handoffs.append(client1.agent)
    client = MCPClient(agent)
    
    
    try:
        await client.connect_to_server("mcp_server.py")
        
        if voice_mode == True:
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
