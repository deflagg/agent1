from dotenv import load_dotenv
from agents import Agent, Runner, function_tool, AgentHooks, ItemHelpers
from langchain_openai import ChatOpenAI
from browser_use import Agent as BrowserAgent, Browser, BrowserConfig
from pydantic import BaseModel, Field
import asyncio
from python_repl import PythonREPL

load_dotenv()

browser = Browser(
    config=BrowserConfig(
        chrome_instance_path='C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
    )
)

@function_tool
def execute_code(code: str) -> str:
    """
    Execute the code and return the output.
    
    args:
        code: The code to execute
        
    returns:
        str: The output of the code
    """
    python_repl = PythonREPL()
    python_repl.run(code)

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
    You are a developer who develops code.
    You have a tool to execute and debug code.
    Test code with the tool before returning it.
    """,
    handoff_description="Specialist agent developing code",
    tools=[execute_code]
)

tester = Agent(
    name="Tester",
    instructions="""
    You are a tester who tests code.
    You have a tool to execute and debug code.
    """,
    handoff_description="Specialist agent for testing code",
    tools=[execute_code]
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




async def main():
    result = Runner.run_streamed(manager, "write a python script to get the os version")
    
    print("=== Thread starting ===")

    async for event in result.stream_events():
        # We'll ignore the raw responses event deltas
        if event.type == "raw_response_event":
            continue
        # When the agent updates, print that
        elif event.type == "agent_updated_stream_event":
            print(f"Agent updated: {event.new_agent.name}")
            continue
        # When items are generated, print them
        elif event.type == "run_item_stream_event":
            if event.item.type == "tool_call_item":
                print("-- Tool was called")
            elif event.item.type == "tool_call_output_item":
                print(f"-- Tool output: {event.item.output}")
            elif event.item.type == "message_output_item":
                print(f"-- Message output:\n {ItemHelpers.text_message_output(event.item)}")
            else:
                pass  # Ignore other event types
            
    print("=== Thread complete ===")
    
    input("Press Enter to exit...")
    await browser.close()
   
if __name__ == "__main__":
    asyncio.run(main())
