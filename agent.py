from dotenv import load_dotenv
from agents import Agent, Runner, function_tool, AgentHooks, ItemHelpers
from langchain_openai import ChatOpenAI
from browser_use import Agent as BrowserAgent, Browser, BrowserConfig
from pydantic import BaseModel, Field
import asyncio
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
    You are a developer who develops code.
    You have a tool to execute and debug code.
    Test code with the tool before returning it.
    """,
    handoff_description="Specialist agent developing code",
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




async def main():
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
        tools=[search_web]
    )
    
    client = MCPClient(agent)
    
    try:
        await client.connect_to_server("mcp_server.py")
        await client.chat_loop()
    finally:
        await client.cleanup()
   
if __name__ == "__main__":
    asyncio.run(main())
