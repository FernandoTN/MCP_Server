#!/usr/bin/env python3
"""
MCP Server stdio entry point for Google Calendar
Runs the MCP Calendar server using stdio transport for Claude Desktop
"""

import asyncio
import json
import sys
from tools.registry import ToolRegistry
from tools.validators import ToolValidator

# Global state
initialized = False
tool_registry = None
tool_validator = None

def init_components():
    """Initialize MCP server components"""
    global tool_registry, tool_validator
    try:
        tool_validator = ToolValidator()
        tool_registry = ToolRegistry()
        print("# Google Calendar MCP components initialized", file=sys.stderr)
        return True
    except Exception as e:
        print(f"# Error initializing components: {e}", file=sys.stderr)
        return False

async def handle_message(message):
    """Handle incoming MCP messages"""
    global initialized, tool_registry
    
    method = message.get("method")
    msg_id = message.get("id")
    
    print(f"# Handling method: {method}", file=sys.stderr)
    
    # Handle notifications (no id field)
    if msg_id is None and method in ["initialized"]:
        if method == "initialized":
            print("# Google Calendar MCP server fully initialized", file=sys.stderr)
            return None
    
    # For request methods, ID is required
    if msg_id is None and method not in ["initialized"]:
        print(f"# Error: Missing ID for method {method}", file=sys.stderr)
        return None
    
    if method == "initialize":
        # Initialize components
        if not init_components():
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32603, "message": "Failed to initialize server components"}
            }
        
        initialized = True
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2025-06-18",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "google-calendar-mcp",
                    "version": "1.0.0"
                }
            }
        }
        
    elif method == "tools/list":
        if not initialized:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32002, "message": "Server not initialized"}
            }
        
        try:
            tools = tool_registry.get_all_tools()
            # Convert Tool objects to dictionaries
            tools_dict = []
            for tool in tools:
                tools_dict.append({
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema
                })
            
            return {
                "jsonrpc": "2.0", 
                "id": msg_id,
                "result": {"tools": tools_dict}
            }
        except Exception as e:
            print(f"# Error listing tools: {e}", file=sys.stderr)
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32603, "message": f"Error listing tools: {str(e)}"}
            }
    
    elif method == "tools/call":
        if not initialized:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32002, "message": "Server not initialized"}
            }
        
        try:
            params = message.get("params", {})
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            print(f"# Calling tool: {tool_name} with args: {arguments}", file=sys.stderr)
            
            # Validate the tool call
            tool_registry.validate_tool_call(tool_name, arguments)
            
            # For now, return a mock response since we don't have Google API setup
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{
                        "type": "text", 
                        "text": f"Google Calendar tool '{tool_name}' called successfully with arguments: {arguments}. (Note: This is a mock response - configure Google API credentials to use real functionality)"
                    }]
                }
            }
        except Exception as e:
            print(f"# Error calling tool: {e}", file=sys.stderr)
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32603, "message": f"Error calling tool: {str(e)}"}
            }
    
    else:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"}
        }

async def main():
    """Main entry point for MCP stdio server"""
    print("# Google Calendar MCP Server starting...", file=sys.stderr)
    
    try:
        while True:
            line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
            
            if not line:
                print("# EOF received - stdin closed", file=sys.stderr)
                break
                
            line = line.strip()
            if not line:
                continue
            
            print(f"# <- {line}", file=sys.stderr)
            
            try:
                message = json.loads(line)
                response = await handle_message(message)
                
                if response is not None:
                    response_json = json.dumps(response)
                    print(response_json, flush=True)
                    print(f"# -> {response_json}", file=sys.stderr)
                
            except json.JSONDecodeError as e:
                print(f"# JSON decode error: {e}", file=sys.stderr)
                error_response = {
                    "jsonrpc": "2.0", 
                    "error": {"code": -32700, "message": "Parse error"}
                }
                print(json.dumps(error_response), flush=True)
    
    except Exception as e:
        print(f"# Fatal error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
    
    print("# Google Calendar MCP Server exiting", file=sys.stderr)

if __name__ == "__main__":
    asyncio.run(main())