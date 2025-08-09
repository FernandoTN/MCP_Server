# MCP Google Calendar Server

A Model Context Protocol (MCP) server for Google Calendar integration, providing secure and scalable access to Google Calendar APIs through MCP-compliant tools.

## Architecture

This server implements a layered architecture designed for maintainability, security, and scalability:

### Layer A: Transport & Gateway
- **FastAPI + MCP StreamableHttpTransport**: Handles POST /mcp and GET /mcp (SSE) endpoints
- **Authentication**: Bearer token validation and MCP protocol version enforcement
- **CORS Support**: Cross-origin resource sharing for web clients

### Layer B: Lifecycle Handler
- **MCP Protocol Compliance**: Handles initialize/initialized handshake
- **Capability Negotiation**: Advertises tools capability with listChanged support
- **Connection Management**: Manages client connections and protocol state

### Layer C: Tool Registry & Schema Guard
- **Four Core Tools**: create_event, update_event, delete_event, freebusy_query
- **Pydantic Validation**: Strict JSON schema validation for all tool arguments
- **Schema Evolution**: Dynamic tool schema updates with change notifications

### Layer D: Command Router & Queue
- **Async Queue Processing**: Handles tool calls with async worker pools
- **Idempotency Cache**: Redis-based deduplication prevents duplicate operations
- **Request Routing**: Routes validated calls to appropriate adapters

### Layer E: Google Calendar Adapter Workers
- **API Translation**: Maps MCP tools to Google Calendar API endpoints
- **Retry Logic**: Exponential backoff for 429/5xx errors with jitter
- **Quota Management**: Intelligent quota bucket handling and rate limiting
- **Authentication**: OAuth 2.0 and Service Account JWT flows

### Layer F: Shared Services
- **Configuration**: Environment-based settings with validation
- **Secret Management**: Google Cloud Secret Manager integration
- **Observability**: OpenTelemetry tracing and metrics
- **Audit Logging**: Comprehensive before/after event snapshots
- **Notifications**: MCP-compliant notifications for schema changes

## Features

### Core MCP Tools

1. **create_event**: Create new calendar events
2. **update_event**: Update existing calendar events  
3. **delete_event**: Delete calendar events
4. **freebusy_query**: Query calendar availability

### Security & Reliability

- Bearer token authentication
- Exponential backoff retry logic
- Idempotency protection
- Comprehensive audit logging
- OAuth 2.0 & Service Account support

## Quick Start

### Installation

```bash
git clone <repository-url>
cd MCP_Server
pip install -r requirements.txt
cp .env.example .env
# Configure .env with your settings
```

### Run

```bash
python main.py
```

### Usage

The server exposes standard MCP endpoints at:
- `POST /mcp` - JSON-RPC tool calls
- `GET /mcp` - Server-Sent Events
- `GET /health` - Health check

## Configuration

Key environment variables:

```bash
MCP_SERVER_PORT=8080
BEARER_TOKEN=your-token
GOOGLE_SERVICE_ACCOUNT_KEY_PATH=/path/to/key.json
# or
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
REDIS_URL=redis://localhost:6379/0
```

## Testing

```bash
pytest                    # Run all tests
pytest --cov=.           # With coverage
```

## Architecture Compliance

This implementation follows the specified 8-step request flow:

1. Client ↔ Server initialize handshake
2. Server capabilities negotiation
3. Client requests tools/list → returns 4 tool schemas
4. Client calls tools with validated arguments
5. Layer C validates & attaches idempotency key
6. Layer D enqueues job & responds
7. Layer E processes via Google Calendar API
8. Layer F logs audit trail & metrics

Built with Python, FastAPI, Pydantic, Redis, and Google APIs.