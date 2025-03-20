import asyncio
import argparse
import json
import logging
import sys
from contextlib import AsyncExitStack

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from agents import Agent, Runner, FunctionTool

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

class MCPClient:
    def __init__(self, agent=None):
        """Initialize the MCP client.
        
        Args:
            agent: Optional pre-configured Agent instance to use instead of creating one
        """
        self.session = None
        self.exit_stack = AsyncExitStack()
        self.agent = agent

    async def connect_to_server(self, server_script_path: str):
        """Connect to the MCP server and create Agent with available tools."""
        # Define the parameters for connecting to the MCP server
        command = "D:\\source\\vscode\\agent1\\.venv\\Scripts\\python.exe"
        server_params = StdioServerParameters(command=command, args=[server_script_path])

        # Establish communication with the MCP server
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        
        # Initialize and get available tools
        await self.session.initialize()
        response = await self.session.list_tools()
        mcp_tools = response.tools
        
        # Convert MCP tools to agent tools
        tools_names = [tool.name for tool in mcp_tools]
        print(f"\nConnected to server with tools: {tools_names}")
        
        agent_tools = [self._create_tool_from_mcp(tool) for tool in mcp_tools]
        
        self.agent.tools.extend(agent_tools)

    def _create_tool_from_mcp(self, mcp_tool):
        """Create an OpenAI Agents SDK FunctionTool from an MCP tool."""
        # Simplify schema handling
        params_schema = getattr(mcp_tool, "inputSchema", {})
        if isinstance(params_schema, dict):
            # Ensure additionalProperties is set to False as required by OpenAI
            params_schema["additionalProperties"] = False
        else:
            params_schema = {
                "type": "object", 
                "properties": getattr(params_schema, "properties", {}),
                "additionalProperties": False
            }
        
        # Create tool invoker function
        async def tool_invoker(run_context, args_json):
            try:
                args_dict = args_json if isinstance(args_json, dict) else json.loads(args_json)
                response = await self.session.call_tool(mcp_tool.name, args_dict)
                
                # Extract text content from response
                if response and hasattr(response, "content"):
                    for item in response.content:
                        if getattr(item, "type", None) == "text":
                            return item.text
                return "No textual response from tool"
            except Exception as e:
                return f"Error calling tool: {str(e)}"
        
        return FunctionTool(
            name=mcp_tool.name,
            description=getattr(mcp_tool, "description", ""),
            params_json_schema=params_schema,
            on_invoke_tool=tool_invoker
        )

    async def process_query(self, query: str) -> str:
        """Process a user query using the agent."""
        if not self.agent:
            return "Error: Agent not initialized. Please connect to a server first."
        
        result = await Runner.run(self.agent, query)
        return result.final_output or "No response generated."

    async def chat_loop(self):
        """Run an interactive chat session with the user."""
        print("\nMCP Client Started! Type 'quit' to exit.")
        
        while True:
            query = input("\nQuery: ").strip()
            if query.lower() == 'quit':
                break
            
            response = await self.process_query(query)
            print("\n" + response)

    async def cleanup(self):
        """Clean up resources before exiting."""
        await self.exit_stack.aclose()

async def main():
    """Main function to start the MCP client."""
    parser = argparse.ArgumentParser(description="MCP Client Args")
    parser.add_argument(
        "--server_script", 
        type=str,
        default="mcp_server.py", 
        help="Path to the server script"
    )
    args = parser.parse_args()
    
     # Create a new agent with the tools
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
        """
    )
    
    client = MCPClient(agent)
    try:
        await client.connect_to_server(args.server_script)
        await client.chat_loop()
    finally:
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(main())