"""
Layer A: Transport & Gateway
FastAPI with direct MCP server integration
Accept POST /mcp for MCP JSON-RPC requests
Basic HTTP transport for MCP protocol
"""

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
import json
import logging

from server import MCPCalendarServer
from services.config import get_settings

logger = logging.getLogger(__name__)

def create_app() -> FastAPI:
    """Create and configure FastAPI application with MCP integration"""
    app = FastAPI(
        title="MCP Google Calendar Server",
        description="Model Context Protocol server for Google Calendar integration",
        version="1.0.0"
    )
    
    settings = get_settings()
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    
    # Initialize MCP server
    mcp_server = MCPCalendarServer()
    
    @app.post("/mcp")
    async def handle_mcp_request(request: Request):
        """Handle MCP JSON-RPC requests"""
        try:
            body = await request.body()
            content_type = request.headers.get("content-type", "application/json")
            
            if content_type != "application/json":
                raise HTTPException(status_code=400, detail="Content-Type must be application/json")
            
            # Parse JSON-RPC request
            try:
                rpc_request = json.loads(body)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid JSON")
            
            # Handle different MCP methods
            if rpc_request.get("method") == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": rpc_request.get("id"),
                    "result": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": mcp_server.get_server_capabilities().__dict__,
                        "serverInfo": {
                            "name": "google-calendar-mcp",
                            "version": "1.0.0"
                        }
                    }
                }
            elif rpc_request.get("method") == "tools/list":
                tools = mcp_server.tool_registry.get_all_tools()
                response = {
                    "jsonrpc": "2.0", 
                    "id": rpc_request.get("id"),
                    "result": {
                        "tools": [tool.__dict__ for tool in tools]
                    }
                }
            elif rpc_request.get("method") == "tools/call":
                params = rpc_request.get("params", {})
                tool_name = params.get("name")
                tool_args = params.get("arguments", {})
                
                result = await mcp_server.command_queue.enqueue_tool_call(tool_name, tool_args)
                response = {
                    "jsonrpc": "2.0",
                    "id": rpc_request.get("id"), 
                    "result": {"content": result}
                }
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": rpc_request.get("id"),
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {rpc_request.get('method')}"
                    }
                }
            
            return Response(
                content=json.dumps(response),
                media_type="application/json"
            )
            
        except Exception as e:
            logger.error(f"Error processing MCP request: {e}")
            error_response = {
                "jsonrpc": "2.0",
                "id": rpc_request.get("id") if 'rpc_request' in locals() else None,
                "error": {
                    "code": -32603,
                    "message": "Internal error"
                }
            }
            return Response(
                content=json.dumps(error_response),
                media_type="application/json",
                status_code=500
            )
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        return {"status": "healthy", "service": "mcp-google-calendar-server"}
    
    return app