"""
MCP Server configuration and setup
Handles server initialization and capability registration
"""

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import ServerCapabilities, Tool
from tools.registry import ToolRegistry
from lifecycle.handler import LifecycleHandler
from router.queue import CommandQueue
from services.config import get_settings

class MCPCalendarServer:
    """Main MCP Server class for Google Calendar integration"""
    
    def __init__(self):
        self.settings = get_settings()
        self.server = Server("google-calendar-mcp")
        self.tool_registry = ToolRegistry()
        self.lifecycle_handler = LifecycleHandler(self.server)
        self.command_queue = CommandQueue()
        
        self._setup_server()
    
    def _setup_server(self):
        """Setup MCP server with tools and handlers"""
        
        # Setup list tools handler
        @self.server.list_tools()
        async def handle_list_tools() -> list[Tool]:
            """List all available tools"""
            return self.tool_registry.get_all_tools()
        
        # Setup tool call handler  
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict) -> list:
            """Handle tool calls through the command queue"""
            return await self.command_queue.enqueue_tool_call(name, arguments)
        
        # Setup lifecycle handlers
        self.lifecycle_handler.setup_handlers()
    
    def get_server_capabilities(self) -> ServerCapabilities:
        """Return server capabilities for MCP protocol"""
        return ServerCapabilities(
            tools={"listChanged": True}
        )
    
    def get_server(self) -> Server:
        """Get the MCP server instance"""
        return self.server