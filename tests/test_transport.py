"""
Transport layer tests
Test FastAPI gateway and authentication
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import json

@pytest.fixture
def mock_settings():
    """Mock settings for testing"""
    with patch('transport.gateway.get_settings') as mock:
        mock.return_value = Mock(
            mcp_protocol_version="2025-06-18",
            bearer_token="test-token",
            enable_telemetry=False
        )
        yield mock.return_value

@pytest.fixture
def mock_mcp_server():
    """Mock MCP server for testing"""
    with patch('transport.gateway.MCPCalendarServer') as mock:
        mock_server = Mock()
        mock.return_value = mock_server
        yield mock_server

@pytest.fixture
def test_client(mock_settings, mock_mcp_server):
    """Test client with mocked dependencies"""
    from transport.gateway import create_app
    app = create_app()
    return TestClient(app)

def test_health_endpoint(test_client):
    """Test health check endpoint"""
    response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_mcp_post_missing_auth(test_client):
    """Test MCP POST endpoint without authentication"""
    response = test_client.post("/mcp", json={"test": "data"})
    assert response.status_code == 401

def test_mcp_post_invalid_protocol_version(test_client):
    """Test MCP POST endpoint with invalid protocol version"""
    headers = {
        "Authorization": "Bearer test-token",
        "MCP-Protocol-Version": "invalid-version"
    }
    response = test_client.post("/mcp", json={"test": "data"}, headers=headers)
    assert response.status_code == 400

def test_mcp_post_invalid_content_type(test_client):
    """Test MCP POST endpoint with invalid content type"""
    headers = {
        "Authorization": "Bearer test-token",
        "MCP-Protocol-Version": "2025-06-18",
        "Content-Type": "text/plain"
    }
    response = test_client.post("/mcp", data="invalid", headers=headers)
    assert response.status_code == 400

@patch('transport.gateway.StreamableHttpTransport')
def test_mcp_post_success(mock_transport, test_client):
    """Test successful MCP POST request"""
    # Mock transport response
    mock_transport_instance = Mock()
    mock_transport_instance.handle_request.return_value = '{"result": "success"}'
    mock_transport.return_value = mock_transport_instance
    
    headers = {
        "Authorization": "Bearer test-token",
        "MCP-Protocol-Version": "2025-06-18"
    }
    
    response = test_client.post("/mcp", json={"test": "data"}, headers=headers)
    assert response.status_code == 200

def test_mcp_get_missing_auth(test_client):
    """Test MCP GET endpoint without authentication"""
    response = test_client.get("/mcp")
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_auth_verify_bearer_token_success():
    """Test successful bearer token verification"""
    from transport.auth import verify_bearer_token
    from fastapi import Request
    
    # Mock request with valid token
    request = Mock(spec=Request)
    request.headers = {"authorization": "Bearer test-token"}
    
    with patch('transport.auth.get_settings') as mock_settings:
        mock_settings.return_value = Mock(bearer_token="test-token")
        
        result = await verify_bearer_token(request)
        assert result == "test-token"

@pytest.mark.asyncio
async def test_auth_verify_bearer_token_invalid():
    """Test bearer token verification with invalid token"""
    from transport.auth import verify_bearer_token
    from fastapi import Request, HTTPException
    
    # Mock request with invalid token
    request = Mock(spec=Request)
    request.headers = {"authorization": "Bearer invalid-token"}
    
    with patch('transport.auth.get_settings') as mock_settings:
        mock_settings.return_value = Mock(bearer_token="test-token")
        
        with pytest.raises(HTTPException) as exc_info:
            await verify_bearer_token(request)
        
        assert exc_info.value.status_code == 401

@pytest.mark.asyncio
async def test_auth_verify_protocol_version_success():
    """Test successful protocol version verification"""
    from transport.auth import verify_protocol_version
    from fastapi import Request
    
    # Mock request with valid protocol version
    request = Mock(spec=Request)
    request.headers = {"MCP-Protocol-Version": "2025-06-18"}
    
    with patch('transport.auth.get_settings') as mock_settings:
        mock_settings.return_value = Mock(mcp_protocol_version="2025-06-18")
        
        result = await verify_protocol_version(request)
        assert result == "2025-06-18"