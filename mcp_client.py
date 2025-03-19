import asyncio
import argparse
import json
import logging
import os
import sys
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from agents import Agent, Runner, function_tool, AgentHooks, FunctionTool
from langchain_openai import ChatOpenAI

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class MCPClient:
    def __init__(self):
        """Initialize the MCP client and configure the OpenAI API."""
        self.session: Optional[ClientSession] = None  # MCP session for communication
        self.exit_stack = AsyncExitStack()  # Manages async resource cleanup
        self.agent = None  # Will store the OpenAI Agent
        
        # Ensure OpenAI API key is set
        # if not os.getenv("OPENAI_API_KEY"):
        #     raise ValueError("OPENAI_API_KEY not found. Please add it to your .env file.")

    async def connect_to_server(self, server_script_path: str):
        """Connect to the MCP server and create Agent with available tools."""

        # Determine whether the server script is written in Python or JavaScript
        command = "python" if server_script_path.endswith('.py') else "node"

        # Define the parameters for connecting to the MCP server
        command = "D:\\source\\vscode\\agent1\\.venv\\Scripts\\python.exe"
        server_params = StdioServerParameters(command=command, args=[server_script_path])

        # Establish communication with the MCP server using standard input/output (stdio)
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))

        # Extract the read/write streams from the transport object
        self.stdio, self.write = stdio_transport

        # Initialize the MCP client session, which allows interaction with the server
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        # Send an initialization request to the MCP server
        await self.session.initialize()

        # Request the list of available tools from the MCP server
        response = await self.session.list_tools()
        mcp_tools = response.tools  # Extract the tool list from the response

        # Print a message showing the names of the tools available on the server
        print("\nConnected to server with tools:", [tool.name for tool in mcp_tools])

        # Convert MCP tools to OpenAI Agents SDK function tools
        agent_tools = self.convert_mcp_tools_to_agent_tools(mcp_tools)
        
        # Create an Agent with the available tools
        self.agent = Agent(
            name="Assistant",
            instructions="""
            You are a helpful assistant with access to various tools.
            Use the available tools to help the user with their requests.
            When using tools, provide clear and concise responses based on the tool output.
            """,
            tools=agent_tools
        )

    def convert_mcp_tools_to_agent_tools(self, mcp_tools):
        """
        Convert a list of MCP tool definitions into OpenAI Agents SDK FunctionTool objects.
        
        MCP tools have attributes rather than dictionary keys.
        """
        agent_tools = []
        for tool in mcp_tools:
            # Access tool attributes directly instead of using .get()
            tool_name = tool.name
            tool_description = tool.description if hasattr(tool, "description") else ""
            tool_schema = tool.inputSchema if hasattr(tool, "inputSchema") else {}

            # Add these debug prints right before the if statement:
            print(f"tool_schema: {tool_schema}, type: {type(tool_schema)}")
            print(f"tool_schema.type: {getattr(tool_schema, 'type', 'NOT FOUND')}, type: {type(getattr(tool_schema, 'type', None))}")
            print(f"Comparison result: {getattr(tool_schema, 'type', None) != 'object'}")

            # Ensure the input schema is a valid JSON schema for the tool's parameters
            if not tool_schema or tool_schema.get("type") != "object":
                params_schema = {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False  # Required by OpenAI
                }
                # If the original schema had properties, include them
                if tool_schema.get("properties"):
                    params_schema["properties"] = tool_schema.properties
            else:
                # Convert the inputSchema object to a dictionary if needed
                params_schema = tool_schema
                if not isinstance(params_schema, dict):
                    params_schema = tool_schema.__dict__
                
                # Ensure additionalProperties is set to False
                params_schema["additionalProperties"] = False

            # Create a function to call the MCP tool when invoked
            async def tool_invoker(run_context, args_json, tool_name=tool_name):
                try:
                    # Convert args_json from string to dictionary if it's a string
                    if isinstance(args_json, str):
                        args_dict = json.loads(args_json)
                    else:
                        args_dict = args_json
                        
                    # Call the MCP tool with the provided arguments
                    response = await self.session.call_tool(tool_name, args_dict)
                    # Extract and return the text content from the response
                    if response and hasattr(response, "content"):
                        for item in response.content:
                            if hasattr(item, "type") and item.type == "text":
                                return item.text
                    return "No textual response from tool"
                except Exception as e:
                    return f"Error calling tool: {str(e)}"

            # Create the FunctionTool object with mapped fields
            function_tool = FunctionTool(
                name=tool_name,
                description=tool_description,
                params_json_schema=params_schema,
                on_invoke_tool=tool_invoker
            )
            agent_tools.append(function_tool)
        return agent_tools


    async def process_query(self, query: str) -> str:
        """
        Process a user query using the OpenAI Agents SDK.

        Args:
            query (str): The user's input query.

        Returns:
            str: The response generated by the agent.
        """
        if not self.agent:
            return "Error: Agent not initialized. Please connect to a server first."

        # Run the agent with the user query
        result = await Runner.run(self.agent, query)
        
        # Return the agent's final output
        return result.final_output if result.final_output else "No response generated."

    async def chat_loop(self):
        """Run an interactive chat session with the user."""
        print("\nMCP Client Started! Type 'quit' to exit.")

        while True:
            query = input("\nQuery: ").strip()
            if query.lower() == 'quit':
                break

            # Process the user's query and display the response
            response = await self.process_query(query)
            print("\n" + response)

    async def cleanup(self):
        """Clean up resources before exiting."""
        await self.exit_stack.aclose()

async def main():
    """Main function to start the MCP client."""
    parser = argparse.ArgumentParser(description="MCP Client Args")
    parser.add_argument("--server_script", 
                        type=str,
                        default="mcp_server.py", 
                        help="Path to the server script")
    args = parser.parse_args()
    
    if not args.server_script:
        print("Usage: python client.py --server_script <path_to_server_script>")
        sys.exit(1)

    client = MCPClient()
    try:
        # Connect to the MCP server and start the chat loop
        await client.connect_to_server(args.server_script)
        await client.chat_loop()
    finally:
        # Ensure resources are cleaned up
        await client.cleanup()

if __name__ == "__main__":
    # Run the main function within the asyncio event loop
    asyncio.run(main())