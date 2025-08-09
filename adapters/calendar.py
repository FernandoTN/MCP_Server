"""
Layer E: Google Calendar adapter workers (google-api-python-client)
Translate MCP tool → Google endpoint (events.insert, events.patch, events.delete, freeBusy.query)
Handle retries, 429/5xx back-off, and quota buckets
Own OAuth refresh / service-account JWT flow
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .auth import GoogleAuthManager
from .retry import with_retry, RetryConfig, exponential_backoff_retry
from .workers import get_worker_pool
from tools.validators import ToolValidator
from services.audit import AuditLogger

logger = logging.getLogger(__name__)

class GoogleCalendarAdapter:
    """Adapter for Google Calendar API operations"""
    
    def __init__(self):
        self.auth_manager = GoogleAuthManager()
        self.validator = ToolValidator()
        self.audit_logger = AuditLogger()
        self.worker_pool = get_worker_pool()
        self._calendar_service = None
        
        # Retry configuration
        self.retry_config = RetryConfig(
            max_retries=3,
            base_delay=1.0,
            max_delay=30.0
        )
    
    async def _get_calendar_service(self):
        """Get authenticated Google Calendar service"""
        if not self._calendar_service:
            credentials = await self.auth_manager.get_credentials()
            self._calendar_service = build('calendar', 'v3', credentials=credentials)
        return self._calendar_service
    
    async def create_event(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new Google Calendar event
        
        Args:
            arguments: Validated CreateEventSchema arguments
            
        Returns:
            Tool response with created event data
        """
        try:
            logger.info(f"Creating calendar event: {arguments.get('summary', 'Untitled')}")
            
            # Extract parameters
            calendar_id = arguments['calendarId']
            event_body = self._build_event_body(arguments)
            
            # Log audit before
            await self.audit_logger.log_operation(
                operation="create_event",
                calendar_id=calendar_id,
                before_state=None,
                after_state=None,
                arguments=arguments
            )
            
            # Execute API call with retry
            result = await self._execute_with_retry(
                self._create_event_api,
                calendar_id,
                event_body
            )
            
            # Log audit after
            await self.audit_logger.log_operation(
                operation="create_event",
                calendar_id=calendar_id,
                before_state=None,
                after_state=result.get('event'),
                arguments=arguments
            )
            
            return self.validator.create_success_response(
                message=f"Event '{result['event']['summary']}' created successfully",
                data={
                    "event": result['event'],
                    "calendar_id": calendar_id,
                    "event_id": result['event']['id'],
                    "html_link": result['event'].get('htmlLink')
                }
            ).dict()
            
        except Exception as e:
            logger.error(f"Failed to create event: {e}")
            return self.validator.create_error_response(
                message="Failed to create calendar event",
                error=str(e)
            ).dict()
    
    async def _create_event_api(self, calendar_id: str, event_body: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the actual API call to create an event"""
        service = await self._get_calendar_service()
        
        def _api_call():
            return service.events().insert(
                calendarId=calendar_id,
                body=event_body,
                sendNotifications=True
            ).execute()
        
        event = await self.worker_pool.execute_sync(_api_call)
        return {"event": event}
    
    async def update_event(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing Google Calendar event
        
        Args:
            arguments: Validated UpdateEventSchema arguments
            
        Returns:
            Tool response with updated event data
        """
        try:
            calendar_id = arguments['calendarId']
            event_id = arguments['eventId']
            
            logger.info(f"Updating calendar event: {event_id}")
            
            # Get current event for audit log
            current_event = await self._get_event(calendar_id, event_id)
            
            # Build update body (only include fields that are being updated)
            update_body = self._build_update_body(arguments)
            
            # Log audit before
            await self.audit_logger.log_operation(
                operation="update_event",
                calendar_id=calendar_id,
                event_id=event_id,
                before_state=current_event,
                after_state=None,
                arguments=arguments
            )
            
            # Execute API call with retry
            result = await self._execute_with_retry(
                self._update_event_api,
                calendar_id,
                event_id,
                update_body
            )
            
            # Log audit after
            await self.audit_logger.log_operation(
                operation="update_event",
                calendar_id=calendar_id,
                event_id=event_id,
                before_state=current_event,
                after_state=result.get('event'),
                arguments=arguments
            )
            
            return self.validator.create_success_response(
                message=f"Event '{result['event']['summary']}' updated successfully",
                data={
                    "event": result['event'],
                    "calendar_id": calendar_id,
                    "event_id": event_id,
                    "html_link": result['event'].get('htmlLink')
                }
            ).dict()
            
        except Exception as e:
            logger.error(f"Failed to update event {arguments.get('eventId')}: {e}")
            return self.validator.create_error_response(
                message="Failed to update calendar event",
                error=str(e)
            ).dict()
    
    async def _update_event_api(self, calendar_id: str, event_id: str, update_body: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the actual API call to update an event"""
        service = await self._get_calendar_service()
        
        def _api_call():
            return service.events().patch(
                calendarId=calendar_id,
                eventId=event_id,
                body=update_body,
                sendNotifications=True
            ).execute()
        
        event = await self.worker_pool.execute_sync(_api_call)
        return {"event": event}
    
    async def delete_event(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Delete a Google Calendar event
        
        Args:
            arguments: Validated DeleteEventSchema arguments
            
        Returns:
            Tool response confirming deletion
        """
        try:
            calendar_id = arguments['calendarId']
            event_id = arguments['eventId']
            send_updates = arguments.get('sendUpdates', 'all')
            
            logger.info(f"Deleting calendar event: {event_id}")
            
            # Get current event for audit log
            current_event = await self._get_event(calendar_id, event_id)
            
            # Log audit before
            await self.audit_logger.log_operation(
                operation="delete_event",
                calendar_id=calendar_id,
                event_id=event_id,
                before_state=current_event,
                after_state=None,
                arguments=arguments
            )
            
            # Execute API call with retry
            await self._execute_with_retry(
                self._delete_event_api,
                calendar_id,
                event_id,
                send_updates
            )
            
            # Log audit after
            await self.audit_logger.log_operation(
                operation="delete_event",
                calendar_id=calendar_id,
                event_id=event_id,
                before_state=current_event,
                after_state={"deleted": True},
                arguments=arguments
            )
            
            return self.validator.create_success_response(
                message=f"Event deleted successfully",
                data={
                    "deleted": True,
                    "calendar_id": calendar_id,
                    "event_id": event_id,
                    "send_updates": send_updates
                }
            ).dict()
            
        except Exception as e:
            logger.error(f"Failed to delete event {arguments.get('eventId')}: {e}")
            return self.validator.create_error_response(
                message="Failed to delete calendar event",
                error=str(e)
            ).dict()
    
    async def _delete_event_api(self, calendar_id: str, event_id: str, send_updates: str):
        """Execute the actual API call to delete an event"""
        service = await self._get_calendar_service()
        
        def _api_call():
            return service.events().delete(
                calendarId=calendar_id,
                eventId=event_id,
                sendNotifications=send_updates != 'none'
            ).execute()
        
        return await self.worker_pool.execute_sync(_api_call)
    
    async def freebusy_query(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Query free/busy information for calendars
        
        Args:
            arguments: Validated FreeBusyQuerySchema arguments
            
        Returns:
            Tool response with free/busy information
        """
        try:
            logger.info(f"Querying free/busy for {len(arguments['items'])} calendars")
            
            # Build query body
            query_body = {
                'timeMin': arguments['timeMin'].isoformat(),
                'timeMax': arguments['timeMax'].isoformat(),
                'items': arguments['items']
            }
            
            if arguments.get('timeZone'):
                query_body['timeZone'] = arguments['timeZone']
            
            # Execute API call with retry
            result = await self._execute_with_retry(
                self._freebusy_query_api,
                query_body
            )
            
            return self.validator.create_success_response(
                message="Free/busy query completed successfully",
                data={
                    "calendars": result['calendars'],
                    "time_min": arguments['timeMin'].isoformat(),
                    "time_max": arguments['timeMax'].isoformat(),
                    "query_time": datetime.now(timezone.utc).isoformat()
                }
            ).dict()
            
        except Exception as e:
            logger.error(f"Failed to query free/busy: {e}")
            return self.validator.create_error_response(
                message="Failed to query free/busy information",
                error=str(e)
            ).dict()
    
    async def _freebusy_query_api(self, query_body: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the actual API call to query free/busy"""
        service = await self._get_calendar_service()
        
        def _api_call():
            return service.freebusy().query(body=query_body).execute()
        
        result = await self.worker_pool.execute_sync(_api_call)
        return {"calendars": result.get('calendars', {})}
    
    async def _get_event(self, calendar_id: str, event_id: str) -> Optional[Dict[str, Any]]:
        """Get an event for audit logging"""
        try:
            service = await self._get_calendar_service()
            
            def _api_call():
                return service.events().get(
                    calendarId=calendar_id,
                    eventId=event_id
                ).execute()
            
            return await self.worker_pool.execute_sync(_api_call)
        except Exception as e:
            logger.warning(f"Could not fetch event {event_id} for audit log: {e}")
            return None
    
    async def _execute_with_retry(self, func, *args, **kwargs):
        """Execute function with exponential backoff retry"""
        return await exponential_backoff_retry(
            func,
            self.retry_config,
            *args,
            **kwargs
        )
    
    def _build_event_body(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Build Google Calendar event body from MCP arguments"""
        event_body = {
            'summary': arguments['summary'],
            'start': self._convert_datetime(arguments['start']),
            'end': self._convert_datetime(arguments['end'])
        }
        
        # Optional fields
        if arguments.get('description'):
            event_body['description'] = arguments['description']
        
        if arguments.get('location'):
            event_body['location'] = arguments['location']
        
        if arguments.get('attendees'):
            event_body['attendees'] = [
                {
                    'email': attendee['email'],
                    'displayName': attendee.get('displayName'),
                    'optional': attendee.get('optional', False),
                    'responseStatus': attendee.get('responseStatus', 'needsAction'),
                    'comment': attendee.get('comment')
                }
                for attendee in arguments['attendees']
            ]
        
        if arguments.get('visibility'):
            event_body['visibility'] = arguments['visibility']
        
        if arguments.get('status'):
            event_body['status'] = arguments['status']
        
        if arguments.get('recurrence'):
            event_body['recurrence'] = arguments['recurrence']['rrule']
            if arguments['recurrence'].get('exdate'):
                event_body['recurrence'].extend([f"EXDATE:{date}" for date in arguments['recurrence']['exdate']])
        
        if arguments.get('reminders'):
            event_body['reminders'] = arguments['reminders']
        
        if arguments.get('conferenceData'):
            event_body['conferenceData'] = arguments['conferenceData']
        
        return event_body
    
    def _build_update_body(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Build update body with only fields that are being updated"""
        update_body = {}
        
        # Only include fields that are present in the arguments
        if 'summary' in arguments:
            update_body['summary'] = arguments['summary']
        
        if 'description' in arguments:
            update_body['description'] = arguments['description']
        
        if 'start' in arguments:
            update_body['start'] = self._convert_datetime(arguments['start'])
        
        if 'end' in arguments:
            update_body['end'] = self._convert_datetime(arguments['end'])
        
        if 'location' in arguments:
            update_body['location'] = arguments['location']
        
        if 'attendees' in arguments:
            update_body['attendees'] = [
                {
                    'email': attendee['email'],
                    'displayName': attendee.get('displayName'),
                    'optional': attendee.get('optional', False),
                    'responseStatus': attendee.get('responseStatus', 'needsAction'),
                    'comment': attendee.get('comment')
                }
                for attendee in arguments['attendees']
            ]
        
        if 'visibility' in arguments:
            update_body['visibility'] = arguments['visibility']
        
        if 'status' in arguments:
            update_body['status'] = arguments['status']
        
        if 'recurrence' in arguments:
            update_body['recurrence'] = arguments['recurrence']['rrule']
            if arguments['recurrence'].get('exdate'):
                update_body['recurrence'].extend([f"EXDATE:{date}" for date in arguments['recurrence']['exdate']])
        
        if 'reminders' in arguments:
            update_body['reminders'] = arguments['reminders']
        
        if 'conferenceData' in arguments:
            update_body['conferenceData'] = arguments['conferenceData']
        
        return update_body
    
    def _convert_datetime(self, dt_obj: Dict[str, Any]) -> Dict[str, Any]:
        """Convert MCP datetime object to Google Calendar format"""
        result = {}
        
        if dt_obj.get('dateTime'):
            # Timed event
            dt = dt_obj['dateTime']
            if isinstance(dt, datetime):
                result['dateTime'] = dt.isoformat()
            else:
                result['dateTime'] = dt
                
            if dt_obj.get('timeZone'):
                result['timeZone'] = dt_obj['timeZone']
        
        elif dt_obj.get('date'):
            # All-day event
            result['date'] = dt_obj['date']
        
        return result