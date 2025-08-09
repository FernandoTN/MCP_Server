"""
Layer D: Command router & queue (asyncio.Queue or Celery/RQ)
with idempotency cache (redis-py)
Deduplicate & enqueue validated calls
Forward to adapter using stable request IDs for idempotency
"""

import asyncio
import uuid
import logging
from typing import Dict, Any, List
from dataclasses import dataclass
from datetime import datetime

from tools.validators import ToolValidator, ValidationException
from .idempotency import IdempotencyCache
from adapters.calendar import GoogleCalendarAdapter

logger = logging.getLogger(__name__)

@dataclass
class QueuedJob:
    """Represents a queued tool call job"""
    id: str
    tool_name: str
    arguments: Dict[str, Any]
    created_at: datetime
    user_id: str = None
    idempotency_key: str = None

class CommandQueue:
    """Manages queued tool calls with idempotency and routing to adapters"""
    
    def __init__(self, max_workers: int = 5):
        self.queue = None  # Will be initialized when event loop is available
        self.validator = ToolValidator()
        self.idempotency_cache = IdempotencyCache()
        self.calendar_adapter = GoogleCalendarAdapter()
        self.max_workers = max_workers
        self.workers = []
        self.is_running = False
        self._initialized = False
    
    async def _ensure_initialized(self):
        """Ensure queue is initialized with async components"""
        if not self._initialized:
            self.queue = asyncio.Queue()
            self._initialized = True
            await self._start_workers()
    
    async def _start_workers(self):
        """Start background worker tasks"""
        if not self.is_running:
            self.is_running = True
            for i in range(self.max_workers):
                worker = asyncio.create_task(self._worker(f"worker-{i}"))
                self.workers.append(worker)
            logger.info(f"Started {self.max_workers} queue workers")
    
    async def _worker(self, name: str):
        """Background worker to process queued jobs"""
        logger.info(f"Queue worker {name} started")
        
        while self.is_running:
            try:
                # Wait for job with timeout
                job = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                
                logger.info(f"Worker {name} processing job {job.id} ({job.tool_name})")
                
                # Process the job
                result = await self._process_job(job)
                
                # Cache result if idempotency key exists
                if job.idempotency_key and result:
                    await self.idempotency_cache.set(job.idempotency_key, result)
                
                # Mark job as done
                self.queue.task_done()
                
            except asyncio.TimeoutError:
                # No jobs to process, continue
                continue
            except Exception as e:
                logger.error(f"Worker {name} error processing job: {e}")
                self.queue.task_done()
    
    async def _process_job(self, job: QueuedJob) -> Dict[str, Any]:
        """Process a single job by routing to appropriate adapter"""
        try:
            # Route to Google Calendar adapter
            if job.tool_name == "create_event":
                return await self.calendar_adapter.create_event(job.arguments)
            elif job.tool_name == "update_event":
                return await self.calendar_adapter.update_event(job.arguments)
            elif job.tool_name == "delete_event":
                return await self.calendar_adapter.delete_event(job.arguments)
            elif job.tool_name == "freebusy_query":
                return await self.calendar_adapter.freebusy_query(job.arguments)
            else:
                error_msg = f"Unknown tool: {job.tool_name}"
                logger.error(error_msg)
                return self.validator.create_error_response(error_msg).dict()
                
        except Exception as e:
            error_msg = f"Error processing {job.tool_name}: {str(e)}"
            logger.error(error_msg)
            return self.validator.create_error_response(error_msg, str(e)).dict()
    
    async def enqueue_tool_call(self, tool_name: str, arguments: Dict[str, Any], user_id: str = None) -> List[Dict[str, Any]]:
        """
        Enqueue a tool call for processing with validation and idempotency
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            user_id: Optional user identifier
            
        Returns:
            Tool call result or cached result
        """
        # Ensure async components are initialized
        await self._ensure_initialized()
        
        job_id = str(uuid.uuid4())
        
        try:
            # Validate arguments
            validated_args = self.validator.validate_tool_args(tool_name, arguments)
            
            # Generate idempotency key
            idempotency_key = self.idempotency_cache.generate_key(
                tool_name, arguments, user_id
            )
            
            # Check for existing result
            cached_result = await self.idempotency_cache.get(idempotency_key)
            if cached_result:
                logger.info(f"Returning cached result for {tool_name}")
                return [cached_result]
            
            # Create job
            job = QueuedJob(
                id=job_id,
                tool_name=tool_name,
                arguments=validated_args.dict(),
                created_at=datetime.utcnow(),
                user_id=user_id,
                idempotency_key=idempotency_key
            )
            
            # For now, process synchronously to return result immediately
            # In production, you might want to use SSE streaming for async processing
            result = await self._process_job(job)
            
            # Cache the result
            if result:
                await self.idempotency_cache.set(idempotency_key, result)
            
            return [result]
            
        except ValidationException as e:
            error_response = self.validator.create_error_response(
                f"Validation failed for {tool_name}",
                str(e)
            )
            return [error_response.dict()]
        except Exception as e:
            error_response = self.validator.create_error_response(
                f"Failed to enqueue {tool_name}",
                str(e)
            )
            return [error_response.dict()]
    
    async def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status"""
        await self._ensure_initialized()
        return {
            "queue_size": self.queue.qsize(),
            "workers": len(self.workers),
            "is_running": self.is_running
        }
    
    async def stop(self):
        """Stop the queue and workers"""
        logger.info("Stopping command queue")
        self.is_running = False
        
        # Cancel all workers
        for worker in self.workers:
            worker.cancel()
        
        # Wait for workers to complete
        if self.workers:
            await asyncio.gather(*self.workers, return_exceptions=True)
        
        self.workers.clear()
        logger.info("Command queue stopped")