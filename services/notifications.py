"""
MCP notification system
Emit notifications/tools/list_changed when schemas evolve
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

class NotificationManager:
    """Manages MCP notifications for schema changes and events"""
    
    def __init__(self):
        self._subscribers: Dict[str, List[callable]] = {}
        self._notification_queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start(self):
        """Start the notification worker"""
        if self._running:
            return
        
        self._running = True
        self._worker_task = asyncio.create_task(self._notification_worker())
        logger.info("Notification manager started")
    
    async def stop(self):
        """Stop the notification worker"""
        if not self._running:
            return
        
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Notification manager stopped")
    
    async def _notification_worker(self):
        """Background worker to process notifications"""
        logger.info("Notification worker started")
        
        while self._running:
            try:
                # Wait for notification with timeout
                notification = await asyncio.wait_for(
                    self._notification_queue.get(), 
                    timeout=1.0
                )
                
                await self._process_notification(notification)
                
            except asyncio.TimeoutError:
                # No notifications to process
                continue
            except Exception as e:
                logger.error(f"Error processing notification: {e}")
    
    async def _process_notification(self, notification: Dict[str, Any]):
        """Process a single notification"""
        notification_type = notification.get('type')
        if not notification_type:
            logger.warning("Notification missing type field")
            return
        
        logger.debug(f"Processing notification: {notification_type}")
        
        # Get subscribers for this notification type
        subscribers = self._subscribers.get(notification_type, [])
        
        # Call all subscribers
        for subscriber in subscribers:
            try:
                if asyncio.iscoroutinefunction(subscriber):
                    await subscriber(notification)
                else:
                    subscriber(notification)
            except Exception as e:
                logger.error(f"Error in notification subscriber: {e}")
    
    def subscribe(self, notification_type: str, callback: callable):
        """
        Subscribe to notifications of a specific type
        
        Args:
            notification_type: Type of notification to subscribe to
            callback: Function to call when notification is received
        """
        if notification_type not in self._subscribers:
            self._subscribers[notification_type] = []
        
        self._subscribers[notification_type].append(callback)
        logger.debug(f"Added subscriber for {notification_type}")
    
    def unsubscribe(self, notification_type: str, callback: callable):
        """
        Unsubscribe from notifications
        
        Args:
            notification_type: Type of notification to unsubscribe from
            callback: Callback function to remove
        """
        if notification_type in self._subscribers:
            try:
                self._subscribers[notification_type].remove(callback)
                logger.debug(f"Removed subscriber for {notification_type}")
            except ValueError:
                pass
    
    async def emit_notification(self, notification_type: str, data: Dict[str, Any] = None):
        """
        Emit a notification
        
        Args:
            notification_type: Type of notification
            data: Additional data to include in notification
        """
        notification = {
            'type': notification_type,
            'timestamp': datetime.utcnow().isoformat(),
            'data': data or {}
        }
        
        try:
            self._notification_queue.put_nowait(notification)
            logger.debug(f"Emitted notification: {notification_type}")
        except asyncio.QueueFull:
            logger.warning(f"Notification queue full, dropping notification: {notification_type}")
    
    async def emit_tools_list_changed(self, changes: Dict[str, Any] = None):
        """
        Emit tools/list_changed notification
        
        Args:
            changes: Details about what changed
        """
        await self.emit_notification(
            'notifications/tools/list_changed',
            {
                'changes': changes or {},
                'reason': 'Tool schemas have been updated'
            }
        )
        logger.info("Emitted tools/list_changed notification")
    
    async def emit_server_status_changed(self, status: str, details: Dict[str, Any] = None):
        """
        Emit server status change notification
        
        Args:
            status: New server status
            details: Additional details about the status change
        """
        await self.emit_notification(
            'notifications/server/status_changed',
            {
                'status': status,
                'details': details or {}
            }
        )
        logger.info(f"Emitted server status changed: {status}")
    
    async def emit_error_notification(self, error: str, component: str = "", details: Dict[str, Any] = None):
        """
        Emit error notification
        
        Args:
            error: Error message
            component: Component where error occurred
            details: Additional error details
        """
        await self.emit_notification(
            'notifications/error',
            {
                'error': error,
                'component': component,
                'details': details or {}
            }
        )
        logger.warning(f"Emitted error notification: {error}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get notification manager statistics"""
        return {
            'running': self._running,
            'queue_size': self._notification_queue.qsize() if self._notification_queue else 0,
            'subscriber_count': sum(len(subs) for subs in self._subscribers.values()),
            'notification_types': list(self._subscribers.keys())
        }

# Global notification manager
_notification_manager: Optional[NotificationManager] = None

def get_notification_manager() -> NotificationManager:
    """Get global notification manager instance"""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager()
    return _notification_manager

async def start_notifications():
    """Start global notification manager"""
    manager = get_notification_manager()
    await manager.start()

async def stop_notifications():
    """Stop global notification manager"""
    global _notification_manager
    if _notification_manager:
        await _notification_manager.stop()
        _notification_manager = None

# Convenience functions
async def emit_tools_changed(changes: Dict[str, Any] = None):
    """Emit tools list changed notification"""
    manager = get_notification_manager()
    await manager.emit_tools_list_changed(changes)

async def emit_server_status(status: str, details: Dict[str, Any] = None):
    """Emit server status notification"""
    manager = get_notification_manager()
    await manager.emit_server_status_changed(status, details)

async def emit_error(error: str, component: str = "", details: Dict[str, Any] = None):
    """Emit error notification"""
    manager = get_notification_manager()
    await manager.emit_error_notification(error, component, details)