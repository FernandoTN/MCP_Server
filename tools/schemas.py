"""
Pydantic schemas for MCP tool definitions
create_event, update_event, delete_event, freebusy_query tool schemas
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class EventVisibility(str, Enum):
    """Google Calendar event visibility options"""
    DEFAULT = "default"
    PUBLIC = "public"
    PRIVATE = "private"

class EventStatus(str, Enum):
    """Google Calendar event status options"""
    TENTATIVE = "tentative"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"

class AttendeeStatus(str, Enum):
    """Attendee response status"""
    NEEDS_ACTION = "needsAction"
    DECLINED = "declined"
    TENTATIVE = "tentative"
    ACCEPTED = "accepted"

class Attendee(BaseModel):
    """Event attendee schema"""
    email: str = Field(..., description="Attendee email address")
    displayName: Optional[str] = Field(None, description="Attendee display name")
    optional: Optional[bool] = Field(False, description="Whether attendance is optional")
    responseStatus: Optional[AttendeeStatus] = Field(AttendeeStatus.NEEDS_ACTION, description="Attendee response status")
    comment: Optional[str] = Field(None, description="Attendee comment")

class EventDateTime(BaseModel):
    """Event date/time schema"""
    dateTime: Optional[datetime] = Field(None, description="DateTime for timed events")
    date: Optional[str] = Field(None, description="Date for all-day events (YYYY-MM-DD)")
    timeZone: Optional[str] = Field(None, description="Time zone (IANA Time Zone Database name)")
    
    @validator('dateTime', 'date')
    def validate_datetime_or_date(cls, v, values):
        """Ensure either dateTime or date is provided, but not both"""
        if v is None and not values.get('date'):
            raise ValueError('Either dateTime or date must be provided')
        if v is not None and values.get('date'):
            raise ValueError('Cannot specify both dateTime and date')
        return v

class Recurrence(BaseModel):
    """Event recurrence rule schema"""
    rrule: List[str] = Field(..., description="Recurrence rules (RRULE format)")
    exdate: Optional[List[str]] = Field(None, description="Exception dates")
    rdate: Optional[List[str]] = Field(None, description="Recurrence dates")

class CreateEventSchema(BaseModel):
    """Schema for creating a Google Calendar event"""
    calendarId: str = Field(..., description="Calendar ID where the event will be created")
    summary: str = Field(..., description="Event title/summary")
    description: Optional[str] = Field(None, description="Event description")
    start: EventDateTime = Field(..., description="Event start time")
    end: EventDateTime = Field(..., description="Event end time")
    location: Optional[str] = Field(None, description="Event location")
    attendees: Optional[List[Attendee]] = Field(None, description="Event attendees")
    visibility: Optional[EventVisibility] = Field(EventVisibility.DEFAULT, description="Event visibility")
    status: Optional[EventStatus] = Field(EventStatus.CONFIRMED, description="Event status")
    recurrence: Optional[Recurrence] = Field(None, description="Recurrence rules")
    reminders: Optional[Dict[str, Any]] = Field(None, description="Event reminders configuration")
    conferenceData: Optional[Dict[str, Any]] = Field(None, description="Conference data (Google Meet, etc.)")

class UpdateEventSchema(BaseModel):
    """Schema for updating a Google Calendar event"""
    calendarId: str = Field(..., description="Calendar ID containing the event")
    eventId: str = Field(..., description="Event ID to update")
    summary: Optional[str] = Field(None, description="Event title/summary")
    description: Optional[str] = Field(None, description="Event description")
    start: Optional[EventDateTime] = Field(None, description="Event start time")
    end: Optional[EventDateTime] = Field(None, description="Event end time")
    location: Optional[str] = Field(None, description="Event location")
    attendees: Optional[List[Attendee]] = Field(None, description="Event attendees")
    visibility: Optional[EventVisibility] = Field(None, description="Event visibility")
    status: Optional[EventStatus] = Field(None, description="Event status")
    recurrence: Optional[Recurrence] = Field(None, description="Recurrence rules")
    reminders: Optional[Dict[str, Any]] = Field(None, description="Event reminders configuration")
    conferenceData: Optional[Dict[str, Any]] = Field(None, description="Conference data")

class DeleteEventSchema(BaseModel):
    """Schema for deleting a Google Calendar event"""
    calendarId: str = Field(..., description="Calendar ID containing the event")
    eventId: str = Field(..., description="Event ID to delete")
    sendUpdates: Optional[str] = Field("all", description="Send updates to attendees (all, externalOnly, none)")

class FreeBusyTimeRange(BaseModel):
    """Time range for free/busy query"""
    start: datetime = Field(..., description="Start time for free/busy query")
    end: datetime = Field(..., description="End time for free/busy query")

class FreeBusyQuerySchema(BaseModel):
    """Schema for querying free/busy information"""
    timeMin: datetime = Field(..., description="Lower bound for the query (inclusive)")
    timeMax: datetime = Field(..., description="Upper bound for the query (exclusive)")
    timeZone: Optional[str] = Field(None, description="Time zone for the query")
    items: List[Dict[str, str]] = Field(..., description="List of calendars to query (format: [{'id': 'calendar_id'}])")
    
    @validator('items')
    def validate_items(cls, v):
        """Ensure items list contains valid calendar references"""
        if not v:
            raise ValueError('At least one calendar must be specified')
        for item in v:
            if not isinstance(item, dict) or 'id' not in item:
                raise ValueError('Each item must be a dict with an "id" key')
        return v

# Tool response schemas
class ToolResponse(BaseModel):
    """Base tool response schema"""
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Human-readable message")
    data: Optional[Dict[str, Any]] = Field(None, description="Operation result data")
    error: Optional[str] = Field(None, description="Error message if operation failed")