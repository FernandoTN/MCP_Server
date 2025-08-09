"""
Tool registry and validation tests
Test Pydantic schemas and validation logic
"""

import pytest
from datetime import datetime
from pydantic import ValidationError
from tools.schemas import (
    CreateEventSchema,
    UpdateEventSchema,
    DeleteEventSchema,
    FreeBusyQuerySchema,
    EventDateTime,
    Attendee
)
from tools.validators import ToolValidator, ValidationException
from tools.registry import ToolRegistry

class TestEventSchemas:
    """Test event schema validation"""
    
    def test_create_event_schema_valid(self):
        """Test valid create event schema"""
        data = {
            "calendarId": "test@example.com",
            "summary": "Test Event",
            "start": {
                "dateTime": datetime.now(),
                "timeZone": "UTC"
            },
            "end": {
                "dateTime": datetime.now(),
                "timeZone": "UTC"
            }
        }
        
        schema = CreateEventSchema(**data)
        assert schema.calendarId == "test@example.com"
        assert schema.summary == "Test Event"
    
    def test_create_event_schema_missing_required(self):
        """Test create event schema with missing required fields"""
        data = {
            "summary": "Test Event"
            # Missing calendarId, start, end
        }
        
        with pytest.raises(ValidationError):
            CreateEventSchema(**data)
    
    def test_event_datetime_timed(self):
        """Test EventDateTime with timed event"""
        data = {
            "dateTime": datetime.now(),
            "timeZone": "America/New_York"
        }
        
        event_dt = EventDateTime(**data)
        assert event_dt.dateTime is not None
        assert event_dt.timeZone == "America/New_York"
    
    def test_event_datetime_all_day(self):
        """Test EventDateTime with all-day event"""
        data = {
            "date": "2024-01-15"
        }
        
        event_dt = EventDateTime(**data)
        assert event_dt.date == "2024-01-15"
        assert event_dt.dateTime is None
    
    def test_event_datetime_invalid_both(self):
        """Test EventDateTime with both date and dateTime (should fail)"""
        data = {
            "dateTime": datetime.now(),
            "date": "2024-01-15"
        }
        
        with pytest.raises(ValidationError):
            EventDateTime(**data)
    
    def test_attendee_schema(self):
        """Test attendee schema validation"""
        data = {
            "email": "attendee@example.com",
            "displayName": "John Doe",
            "optional": False
        }
        
        attendee = Attendee(**data)
        assert attendee.email == "attendee@example.com"
        assert attendee.displayName == "John Doe"
        assert attendee.optional is False
    
    def test_update_event_schema_partial(self):
        """Test update event schema with partial data"""
        data = {
            "calendarId": "test@example.com",
            "eventId": "event123",
            "summary": "Updated Event"
            # Only updating summary, other fields optional
        }
        
        schema = UpdateEventSchema(**data)
        assert schema.summary == "Updated Event"
        assert schema.description is None
    
    def test_delete_event_schema(self):
        """Test delete event schema"""
        data = {
            "calendarId": "test@example.com",
            "eventId": "event123",
            "sendUpdates": "all"
        }
        
        schema = DeleteEventSchema(**data)
        assert schema.calendarId == "test@example.com"
        assert schema.eventId == "event123"
        assert schema.sendUpdates == "all"
    
    def test_freebusy_query_schema(self):
        """Test free/busy query schema"""
        data = {
            "timeMin": datetime.now(),
            "timeMax": datetime.now(),
            "items": [{"id": "calendar1@example.com"}]
        }
        
        schema = FreeBusyQuerySchema(**data)
        assert len(schema.items) == 1
        assert schema.items[0]["id"] == "calendar1@example.com"
    
    def test_freebusy_query_invalid_items(self):
        """Test free/busy query with invalid items"""
        data = {
            "timeMin": datetime.now(),
            "timeMax": datetime.now(),
            "items": [{"invalid": "field"}]  # Missing 'id' key
        }
        
        with pytest.raises(ValidationError):
            FreeBusyQuerySchema(**data)

class TestToolValidator:
    """Test tool validator functionality"""
    
    def test_validate_create_event_success(self):
        """Test successful validation of create event arguments"""
        arguments = {
            "calendarId": "test@example.com",
            "summary": "Test Event",
            "start": {
                "dateTime": datetime.now(),
                "timeZone": "UTC"
            },
            "end": {
                "dateTime": datetime.now(),
                "timeZone": "UTC"
            }
        }
        
        result = ToolValidator.validate_tool_args("create_event", arguments)
        assert isinstance(result, CreateEventSchema)
        assert result.summary == "Test Event"
    
    def test_validate_unknown_tool(self):
        """Test validation of unknown tool"""
        with pytest.raises(ValidationException):
            ToolValidator.validate_tool_args("unknown_tool", {})
    
    def test_validate_invalid_arguments(self):
        """Test validation with invalid arguments"""
        arguments = {
            "calendarId": "test@example.com"
            # Missing required fields
        }
        
        with pytest.raises(ValidationException):
            ToolValidator.validate_tool_args("create_event", arguments)
    
    def test_get_tool_schema(self):
        """Test getting tool schema"""
        schema = ToolValidator.get_tool_schema("create_event")
        assert isinstance(schema, dict)
        assert "properties" in schema
        assert "calendarId" in schema["properties"]
    
    def test_get_all_schemas(self):
        """Test getting all tool schemas"""
        schemas = ToolValidator.get_all_schemas()
        assert isinstance(schemas, dict)
        assert "create_event" in schemas
        assert "update_event" in schemas
        assert "delete_event" in schemas
        assert "freebusy_query" in schemas
    
    def test_create_error_response(self):
        """Test creating error response"""
        response = ToolValidator.create_error_response("Test error", "Details")
        assert response.success is False
        assert response.message == "Test error"
        assert response.error == "Details"
    
    def test_create_success_response(self):
        """Test creating success response"""
        data = {"result": "success"}
        response = ToolValidator.create_success_response("Success", data)
        assert response.success is True
        assert response.message == "Success"
        assert response.data == data

class TestToolRegistry:
    """Test tool registry functionality"""
    
    def test_registry_initialization(self):
        """Test tool registry initialization"""
        registry = ToolRegistry()
        tools = registry.get_all_tools()
        
        assert len(tools) == 4
        tool_names = [tool.name for tool in tools]
        assert "create_event" in tool_names
        assert "update_event" in tool_names
        assert "delete_event" in tool_names
        assert "freebusy_query" in tool_names
    
    def test_get_tool_by_name(self):
        """Test getting specific tool by name"""
        registry = ToolRegistry()
        tool = registry.get_tool("create_event")
        
        assert tool.name == "create_event"
        assert "Create a new Google Calendar event" in tool.description
    
    def test_get_nonexistent_tool(self):
        """Test getting nonexistent tool"""
        registry = ToolRegistry()
        
        with pytest.raises(ValueError):
            registry.get_tool("nonexistent_tool")
    
    def test_get_tool_names(self):
        """Test getting list of tool names"""
        registry = ToolRegistry()
        names = registry.get_tool_names()
        
        assert len(names) == 4
        assert all(name in names for name in ["create_event", "update_event", "delete_event", "freebusy_query"])
    
    def test_validate_tool_call(self):
        """Test validating tool call through registry"""
        registry = ToolRegistry()
        
        arguments = {
            "calendarId": "test@example.com",
            "summary": "Test Event",
            "start": {
                "dateTime": datetime.now(),
                "timeZone": "UTC"
            },
            "end": {
                "dateTime": datetime.now(),
                "timeZone": "UTC"
            }
        }
        
        result = registry.validate_tool_call("create_event", arguments)
        assert isinstance(result, CreateEventSchema)
    
    def test_get_tool_schemas(self):
        """Test getting tool schemas from registry"""
        registry = ToolRegistry()
        schemas = registry.get_tool_schemas()
        
        assert isinstance(schemas, dict)
        assert len(schemas) == 4