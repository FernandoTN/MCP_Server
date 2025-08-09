"""
Layer B: Lifecycle handler (mcp.server.Server)
Handle initialize request, return server capabilities (tools.listChanged=true)
Manage MCP protocol handshake and capability negotiation
"""

from mcp.server import Server
from mcp.types import InitializeResult, ServerCapabilities, Tool
from services.config import get_settings
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class LifecycleHandler:
    """Handles MCP server lifecycle events and capability negotiation"""
    
    def __init__(self, server: Server):
        self.server = server
        self.settings = get_settings()
        self._initialized = False
    
    def setup_handlers(self):
        """Setup MCP lifecycle event handlers"""
        # For now, just mark as initialized
        # The actual initialization will be handled by the gateway
        self._initialized = True
        logger.info("Lifecycle handler setup completed")
    
    async def _emit_tools_changed(self):
        """Emit tools/list_changed notification when tool schemas evolve"""
        if self._initialized:
            try:
                await self.server.request_context.session.send_notification(
                    "notifications/tools/list_changed"
                )
                logger.info("Emitted tools/list_changed notification")
            except Exception as e:
                logger.error(f"Failed to emit tools/list_changed notification: {e}")
    
    @property
    def is_initialized(self) -> bool:
        """Check if the server has been initialized"""
        return self._initialized