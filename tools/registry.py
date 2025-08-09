"""
Layer C: Tool registry / schema guard (pydantic models)
Register four tools via server.add_tool()
Validate tools/call arguments & reject on schema error
"""

from mcp.types import Tool
from typing import List, Dict, Any
import logging
from .validators import ToolValidator

logger = logging.getLogger(__name__)

class ToolRegistry:
    """Registry for managing MCP tools and their schemas"""
    
    def __init__(self):
        self.validator = ToolValidator()
        self._tools = self._create_tools()
    
    def _create_tools(self) -> List[Tool]:
        """Create MCP tool definitions with JSON schemas"""
        
        tools = []
        
        # Create Event Tool
        create_event_tool = Tool(
            name="create_event",
            description="Create a new Google Calendar event",
            inputSchema=self.validator.get_tool_schema("create_event")
        )
        tools.append(create_event_tool)
        
        # Update Event Tool  
        update_event_tool = Tool(
            name="update_event",
            description="Update an existing Google Calendar event",
            inputSchema=self.validator.get_tool_schema("update_event")
        )
        tools.append(update_event_tool)
        
        # Delete Event Tool
        delete_event_tool = Tool(
            name="delete_event", 
            description="Delete a Google Calendar event",
            inputSchema=self.validator.get_tool_schema("delete_event")
        )
        tools.append(delete_event_tool)
        
        # Free/Busy Query Tool
        freebusy_tool = Tool(
            name="freebusy_query",
            description="Query free/busy information for Google Calendar",
            inputSchema=self.validator.get_tool_schema("freebusy_query")
        )
        tools.append(freebusy_tool)
        
        logger.info(f"Created {len(tools)} tools: {[tool.name for tool in tools]}")
        return tools
    
    def get_all_tools(self) -> List[Tool]:
        """Get all registered tools"""
        return self._tools
    
    def get_tool(self, name: str) -> Tool:
        """Get a specific tool by name"""
        for tool in self._tools:
            if tool.name == name:
                return tool
        raise ValueError(f"Tool '{name}' not found")
    
    def get_tool_names(self) -> List[str]:
        """Get list of all tool names"""
        return [tool.name for tool in self._tools]
    
    def validate_tool_call(self, name: str, arguments: Dict[str, Any]):
        """
        Validate tool call arguments
        
        Args:
            name: Tool name
            arguments: Tool arguments to validate
            
        Returns:
            Validated arguments
            
        Raises:
            ValidationException: If validation fails
        """
        return self.validator.validate_tool_args(name, arguments)
    
    def get_tool_schemas(self) -> Dict[str, Dict[str, Any]]:
        """Get all tool schemas for documentation or introspection"""
        return self.validator.get_all_schemas()