"""
Authentication middleware
Bearer token validation and MCP protocol version enforcement
"""

from fastapi import HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from services.config import get_settings
import logging

logger = logging.getLogger(__name__)

security = HTTPBearer()
settings = get_settings()

async def verify_bearer_token(request: Request) -> str:
    """
    Verify Bearer token from Authorization header
    Returns token if valid, raises HTTPException if invalid
    """
    auth_header = request.headers.get("authorization")
    
    if not auth_header:
        raise HTTPException(
            status_code=401,
            detail="Authorization header required"
        )
    
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Bearer token required"
        )
    
    token = auth_header.split(" ")[1]
    
    # Validate token against configured bearer token
    if settings.bearer_token and token != settings.bearer_token:
        logger.warning(f"Invalid bearer token attempted: {token[:10]}...")
        raise HTTPException(
            status_code=401,
            detail="Invalid bearer token"
        )
    
    return token

async def verify_protocol_version(request: Request) -> str:
    """
    Verify MCP-Protocol-Version header
    Returns version if valid, raises HTTPException if invalid
    """
    protocol_version = request.headers.get("MCP-Protocol-Version")
    
    if not protocol_version:
        raise HTTPException(
            status_code=400,
            detail="MCP-Protocol-Version header required"
        )
    
    if protocol_version != settings.mcp_protocol_version:
        logger.warning(f"Unsupported protocol version: {protocol_version}")
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported protocol version. Expected: {settings.mcp_protocol_version}"
        )
    
    return protocol_version