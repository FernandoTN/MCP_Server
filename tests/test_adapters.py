"""
Google Calendar adapter tests
Test Google Calendar API integration and retry logic
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from googleapiclient.errors import HttpError
from adapters.calendar import GoogleCalendarAdapter
from adapters.retry import RetryConfig, exponential_backoff_retry
from adapters.workers import WorkerPool

@pytest.fixture
def mock_auth_manager():
    """Mock GoogleAuthManager"""
    with patch('adapters.calendar.GoogleAuthManager') as mock:
        mock_instance = Mock()
        mock_instance.get_credentials = AsyncMock()
        mock.return_value = mock_instance
        yield mock_instance

@pytest.fixture
def mock_worker_pool():
    """Mock WorkerPool"""
    with patch('adapters.calendar.get_worker_pool') as mock:
        mock_instance = Mock()
        mock_instance.execute_sync = AsyncMock()
        mock.return_value = mock_instance
        yield mock_instance

@pytest.fixture
def mock_audit_logger():
    """Mock AuditLogger"""
    with patch('adapters.calendar.AuditLogger') as mock:
        mock_instance = Mock()
        mock_instance.log_operation = AsyncMock()
        mock.return_value = mock_instance
        yield mock_instance

@pytest.fixture
def calendar_adapter(mock_auth_manager, mock_worker_pool, mock_audit_logger):
    """GoogleCalendarAdapter with mocked dependencies"""
    return GoogleCalendarAdapter()

class TestGoogleCalendarAdapter:
    """Test Google Calendar adapter functionality"""
    
    @pytest.mark.asyncio
    async def test_create_event_success(self, calendar_adapter, mock_worker_pool):
        """Test successful event creation"""
        # Mock API response
        mock_event = {
            "id": "event123",
            "summary": "Test Event",
            "htmlLink": "https://calendar.google.com/event"
        }
        mock_worker_pool.execute_sync.return_value = mock_event
        
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
        
        result = await calendar_adapter.create_event(arguments)
        
        assert result["success"] is True
        assert "Test Event" in result["message"]
        assert result["data"]["event_id"] == "event123"
    
    @pytest.mark.asyncio
    async def test_create_event_failure(self, calendar_adapter, mock_worker_pool):
        """Test event creation failure"""
        # Mock API error
        mock_worker_pool.execute_sync.side_effect = Exception("API Error")
        
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
        
        result = await calendar_adapter.create_event(arguments)
        
        assert result["success"] is False
        assert "Failed to create calendar event" in result["message"]
    
    @pytest.mark.asyncio
    async def test_update_event_success(self, calendar_adapter, mock_worker_pool):
        """Test successful event update"""
        # Mock existing event and updated event
        existing_event = {"id": "event123", "summary": "Old Event"}
        updated_event = {"id": "event123", "summary": "Updated Event"}
        
        # Mock _get_event to return existing event
        calendar_adapter._get_event = AsyncMock(return_value=existing_event)
        mock_worker_pool.execute_sync.return_value = updated_event
        
        arguments = {
            "calendarId": "test@example.com",
            "eventId": "event123",
            "summary": "Updated Event"
        }
        
        result = await calendar_adapter.update_event(arguments)
        
        assert result["success"] is True
        assert "Updated Event" in result["message"]
        assert result["data"]["event_id"] == "event123"
    
    @pytest.mark.asyncio
    async def test_delete_event_success(self, calendar_adapter, mock_worker_pool):
        """Test successful event deletion"""
        # Mock existing event
        existing_event = {"id": "event123", "summary": "Test Event"}
        calendar_adapter._get_event = AsyncMock(return_value=existing_event)
        mock_worker_pool.execute_sync.return_value = None
        
        arguments = {
            "calendarId": "test@example.com",
            "eventId": "event123",
            "sendUpdates": "all"
        }
        
        result = await calendar_adapter.delete_event(arguments)
        
        assert result["success"] is True
        assert "deleted successfully" in result["message"]
        assert result["data"]["deleted"] is True
    
    @pytest.mark.asyncio
    async def test_freebusy_query_success(self, calendar_adapter, mock_worker_pool):
        """Test successful free/busy query"""
        # Mock API response
        mock_response = {
            "calendars": {
                "test@example.com": {
                    "busy": [
                        {
                            "start": "2024-01-15T10:00:00Z",
                            "end": "2024-01-15T11:00:00Z"
                        }
                    ]
                }
            }
        }
        mock_worker_pool.execute_sync.return_value = mock_response
        
        arguments = {
            "timeMin": datetime.now(),
            "timeMax": datetime.now(),
            "items": [{"id": "test@example.com"}]
        }
        
        result = await calendar_adapter.freebusy_query(arguments)
        
        assert result["success"] is True
        assert "completed successfully" in result["message"]
        assert "calendars" in result["data"]
    
    def test_build_event_body(self, calendar_adapter):
        """Test building event body from arguments"""
        arguments = {
            "summary": "Test Event",
            "description": "Test Description",
            "location": "Test Location",
            "start": {
                "dateTime": datetime.now(),
                "timeZone": "UTC"
            },
            "end": {
                "dateTime": datetime.now(),
                "timeZone": "UTC"
            },
            "attendees": [
                {
                    "email": "attendee@example.com",
                    "displayName": "Attendee",
                    "optional": False
                }
            ]
        }
        
        event_body = calendar_adapter._build_event_body(arguments)
        
        assert event_body["summary"] == "Test Event"
        assert event_body["description"] == "Test Description"
        assert event_body["location"] == "Test Location"
        assert len(event_body["attendees"]) == 1
        assert event_body["attendees"][0]["email"] == "attendee@example.com"
    
    def test_convert_datetime_timed(self, calendar_adapter):
        """Test converting timed datetime"""
        dt_obj = {
            "dateTime": datetime(2024, 1, 15, 10, 0, 0),
            "timeZone": "UTC"
        }
        
        result = calendar_adapter._convert_datetime(dt_obj)
        
        assert "dateTime" in result
        assert result["timeZone"] == "UTC"
    
    def test_convert_datetime_all_day(self, calendar_adapter):
        """Test converting all-day datetime"""
        dt_obj = {
            "date": "2024-01-15"
        }
        
        result = calendar_adapter._convert_datetime(dt_obj)
        
        assert result["date"] == "2024-01-15"
        assert "dateTime" not in result

class TestRetryLogic:
    """Test retry and error handling logic"""
    
    @pytest.mark.asyncio
    async def test_exponential_backoff_success(self):
        """Test successful retry after failures"""
        call_count = 0
        
        async def failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                # Simulate HTTP 429 (rate limit)
                error_resp = Mock()
                error_resp.status = 429
                raise HttpError(resp=error_resp, content=b"Rate limited")
            return "success"
        
        config = RetryConfig(max_retries=3, base_delay=0.1)
        result = await exponential_backoff_retry(failing_function, config)
        
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_exponential_backoff_non_retryable(self):
        """Test non-retryable error (400)"""
        async def failing_function():
            error_resp = Mock()
            error_resp.status = 400
            raise HttpError(resp=error_resp, content=b"Bad request")
        
        config = RetryConfig(max_retries=3, base_delay=0.1)
        
        with pytest.raises(HttpError):
            await exponential_backoff_retry(failing_function, config)
    
    @pytest.mark.asyncio
    async def test_exponential_backoff_max_retries(self):
        """Test max retries exhausted"""
        async def always_failing_function():
            error_resp = Mock()
            error_resp.status = 500
            raise HttpError(resp=error_resp, content=b"Internal server error")
        
        config = RetryConfig(max_retries=2, base_delay=0.1)
        
        with pytest.raises(HttpError):
            await exponential_backoff_retry(always_failing_function, config)

class TestWorkerPool:
    """Test worker pool functionality"""
    
    @pytest.mark.asyncio
    async def test_worker_pool_initialization(self):
        """Test worker pool initialization"""
        pool = WorkerPool(max_workers=2, max_requests_per_second=5)
        
        assert pool.max_workers == 2
        assert not pool.is_running
        assert len(pool.workers) == 0
        
        await pool.start()
        assert pool.is_running
        assert len(pool.workers) == 2
        
        await pool.stop()
        assert not pool.is_running
        assert len(pool.workers) == 0
    
    @pytest.mark.asyncio
    async def test_worker_pool_execute_sync(self):
        """Test synchronous execution through worker pool"""
        pool = WorkerPool(max_workers=1)
        await pool.start()
        
        def test_function(x, y):
            return x + y
        
        try:
            result = await pool.execute_sync(test_function, 2, 3)
            assert result == 5
        finally:
            await pool.stop()
    
    @pytest.mark.asyncio
    async def test_worker_pool_async_function(self):
        """Test async function execution through worker pool"""
        pool = WorkerPool(max_workers=1)
        await pool.start()
        
        async def async_test_function(x, y):
            return x * y
        
        try:
            result = await pool.execute_sync(async_test_function, 3, 4)
            assert result == 12
        finally:
            await pool.stop()
    
    def test_worker_pool_stats(self):
        """Test worker pool statistics"""
        pool = WorkerPool(max_workers=3)
        
        stats = pool.get_stats()
        
        assert stats["is_running"] is False
        assert stats["workers"] == 0
        assert stats["completed_tasks"] == 0
        assert stats["failed_tasks"] == 0
        assert "uptime_seconds" in stats