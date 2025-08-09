#!/usr/bin/env python3
"""
Main entry point for MCP Google Calendar Server
Initializes FastAPI app with MCP transport and starts server
"""

import asyncio
import uvicorn
from fastapi import FastAPI
from transport.gateway import create_app
from services.config import get_settings
from services.telemetry import setup_telemetry

async def main():
    """Main entry point for the MCP server"""
    settings = get_settings()
    
    # Setup telemetry
    if settings.enable_telemetry:
        setup_telemetry()
    
    # Create FastAPI app with MCP integration
    app = create_app()
    
    # Run the server
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=settings.server_port,
        log_level=settings.log_level.lower()
    )
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())