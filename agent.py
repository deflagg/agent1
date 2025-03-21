from enum import Enum
from typing import AsyncIterator, Callable
from dotenv import load_dotenv
from agents import Agent, Runner, TResponseInputItem, function_tool, AgentHooks, ItemHelpers
from agents.voice import (
    SingleAgentVoiceWorkflow,
    SingleAgentWorkflowCallbacks,
    VoiceWorkflowBase,
    VoiceWorkflowHelper
)
from langchain_openai import ChatOpenAI
from browser_use import Agent as BrowserAgent, Browser, BrowserConfig
from pydantic import BaseModel, Field
from mcp_client import MCPClient

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
        
 #enum for voice mode
class VoiceMode(Enum):
    OFF = "off"
    ON_NO_STREAMING = "on_no_streaming"
    ON_STREAMING = "on_streaming"
    
    
class MyWorkflow(VoiceWorkflowBase):
    def __init__(self, secret_word: str, on_start: Callable[[str], None]):
        """
        Args:
            secret_word: The secret word to guess.
            on_start: A callback that is called when the workflow starts. The transcription
                is passed in as an argument.
        """
        self._input_history: list[TResponseInputItem] = []
        self._current_agent = agent
        self._secret_word = secret_word.lower()
        self._on_start = on_start

    async def run(self, transcription: str) -> AsyncIterator[str]:
        self._on_start(transcription)

        # Add the transcription to the input history
        self._input_history.append(
            {
                "role": "user",
                "content": transcription,
            }
        )

        # If the user guessed the secret word, do alternate logic
        if self._secret_word in transcription.lower():
            yield "You guessed the secret word!"
            self._input_history.append(
                {
                    "role": "assistant",
                    "content": "You guessed the secret word!",
                }
            )
            return

        # Otherwise, run the agent
        result = Runner.run_streamed(self._current_agent, self._input_history)

        async for chunk in VoiceWorkflowHelper.stream_text_from(result):
            yield chunk

        # Update the input history and current agent
        self._input_history = result.to_input_list()
        self._current_agent = result.last_agent

