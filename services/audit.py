"""
Audit logging service
Persist audit log of before/after event snapshots
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)

class AuditAction(str, Enum):
    """Audit action types"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    READ = "read"

@dataclass
class AuditLogEntry:
    """Represents a single audit log entry"""
    timestamp: datetime
    operation: str
    action: AuditAction
    calendar_id: Optional[str]
    event_id: Optional[str]
    user_id: Optional[str]
    before_state: Optional[Dict[str, Any]]
    after_state: Optional[Dict[str, Any]]
    arguments: Optional[Dict[str, Any]]
    success: bool
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), default=str)

class AuditLogger:
    """Manages audit logging for calendar operations"""
    
    def __init__(self, log_file: Optional[str] = None):
        self.log_file = log_file or "audit.log"
        self._setup_file_logger()
    
    def _setup_file_logger(self):
        """Setup dedicated file logger for audit entries"""
        self.audit_logger = logging.getLogger("audit")
        self.audit_logger.setLevel(logging.INFO)
        
        # Create file handler if not already exists
        if not any(isinstance(h, logging.FileHandler) for h in self.audit_logger.handlers):
            file_handler = logging.FileHandler(self.log_file, mode='a')
            
            # Use JSON format for structured logging
            formatter = logging.Formatter('%(message)s')
            file_handler.setFormatter(formatter)
            
            self.audit_logger.addHandler(file_handler)
            self.audit_logger.propagate = False
    
    async def log_operation(
        self,
        operation: str,
        calendar_id: Optional[str] = None,
        event_id: Optional[str] = None,
        before_state: Optional[Dict[str, Any]] = None,
        after_state: Optional[Dict[str, Any]] = None,
        arguments: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        success: bool = True,
        error: Optional[str] = None
    ):
        """
        Log a calendar operation for audit purposes
        
        Args:
            operation: Name of the operation (create_event, update_event, etc.)
            calendar_id: Calendar ID involved in operation
            event_id: Event ID involved in operation
            before_state: State before the operation
            after_state: State after the operation
            arguments: Operation arguments
            user_id: User who performed the operation
            success: Whether the operation was successful
            error: Error message if operation failed
        """
        try:
            # Determine action type from operation
            action = self._determine_action(operation)
            
            # Create audit entry
            entry = AuditLogEntry(
                timestamp=datetime.now(timezone.utc),
                operation=operation,
                action=action,
                calendar_id=calendar_id,
                event_id=event_id,
                user_id=user_id,
                before_state=self._sanitize_state(before_state),
                after_state=self._sanitize_state(after_state),
                arguments=self._sanitize_arguments(arguments),
                success=success,
                error=error
            )
            
            # Log to file
            self.audit_logger.info(entry.to_json())
            
            logger.debug(f"Logged audit entry for {operation}")
            
        except Exception as e:
            logger.error(f"Failed to log audit entry: {e}")
            # Don't fail the operation if audit logging fails
    
    def _determine_action(self, operation: str) -> AuditAction:
        """Determine audit action from operation name"""
        if "create" in operation.lower():
            return AuditAction.CREATE
        elif "update" in operation.lower() or "patch" in operation.lower():
            return AuditAction.UPDATE
        elif "delete" in operation.lower():
            return AuditAction.DELETE
        else:
            return AuditAction.READ
    
    def _sanitize_state(self, state: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Remove sensitive information from state data"""
        if not state:
            return None
        
        # Create a copy to avoid modifying original
        sanitized = dict(state)
        
        # Remove or mask sensitive fields
        sensitive_fields = ['password', 'token', 'secret', 'key', 'credential']
        
        for field in sensitive_fields:
            for key in list(sanitized.keys()):
                if field.lower() in key.lower():
                    sanitized[key] = "***REDACTED***"
        
        return sanitized
    
    def _sanitize_arguments(self, arguments: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Remove sensitive information from arguments"""
        if not arguments:
            return None
        
        # Create a copy to avoid modifying original
        sanitized = dict(arguments)
        
        # Remove sensitive fields that might be in arguments
        sensitive_fields = ['password', 'token', 'secret', 'key', 'credential']
        
        for field in sensitive_fields:
            for key in list(sanitized.keys()):
                if field.lower() in key.lower():
                    sanitized[key] = "***REDACTED***"
        
        return sanitized
    
    async def log_error(
        self,
        operation: str,
        error: str,
        calendar_id: Optional[str] = None,
        event_id: Optional[str] = None,
        arguments: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None
    ):
        """
        Log an operation error
        
        Args:
            operation: Name of the operation that failed
            error: Error message
            calendar_id: Calendar ID involved
            event_id: Event ID involved  
            arguments: Operation arguments
            user_id: User who performed the operation
        """
        await self.log_operation(
            operation=operation,
            calendar_id=calendar_id,
            event_id=event_id,
            arguments=arguments,
            user_id=user_id,
            success=False,
            error=error
        )
    
    async def log_access(
        self,
        operation: str,
        calendar_id: str,
        user_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Log access to calendar resources
        
        Args:
            operation: Access operation (read, list, etc.)
            calendar_id: Calendar being accessed
            user_id: User accessing the calendar
            details: Additional access details
        """
        await self.log_operation(
            operation=f"access_{operation}",
            calendar_id=calendar_id,
            user_id=user_id,
            arguments=details,
            success=True
        )
    
    def get_audit_stats(self) -> Dict[str, Any]:
        """Get audit logging statistics"""
        try:
            import os
            file_size = os.path.getsize(self.log_file) if os.path.exists(self.log_file) else 0
            
            return {
                "log_file": self.log_file,
                "file_size_bytes": file_size,
                "file_exists": os.path.exists(self.log_file)
            }
        except Exception as e:
            logger.error(f"Failed to get audit stats: {e}")
            return {"error": str(e)}

# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None

def get_audit_logger() -> AuditLogger:
    """Get global audit logger instance"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger