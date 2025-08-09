"""
Async worker pool for Google Calendar operations
Manages concurrent API calls with quota awareness
"""

import asyncio
import logging
from typing import Dict, Any, Callable, Optional, List
from dataclasses import dataclass
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from .retry import QuotaManager, RateLimiter

logger = logging.getLogger(__name__)

@dataclass
class WorkerTask:
    """Represents a task for the worker pool"""
    id: str
    func: Callable
    args: tuple
    kwargs: dict
    created_at: datetime
    priority: int = 0

class WorkerPool:
    """Manages a pool of async workers for Google Calendar operations"""
    
    def __init__(
        self,
        max_workers: int = 5,
        max_requests_per_second: float = 10,
        queue_size: int = 100
    ):
        self.max_workers = max_workers
        self.queue = asyncio.Queue(maxsize=queue_size)
        self.workers: List[asyncio.Task] = []
        self.is_running = False
        
        # Quota and rate limiting
        self.quota_manager = QuotaManager()
        self.rate_limiter = RateLimiter(max_requests_per_second)
        
        # Thread pool for blocking operations
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)
        
        # Statistics
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.start_time = datetime.utcnow()
    
    async def start(self):
        """Start the worker pool"""
        if self.is_running:
            return
        
        self.is_running = True
        self.start_time = datetime.utcnow()
        
        # Start worker tasks
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self.workers.append(worker)
        
        logger.info(f"Started worker pool with {self.max_workers} workers")
    
    async def stop(self):
        """Stop the worker pool"""
        if not self.is_running:
            return
        
        logger.info("Stopping worker pool")
        self.is_running = False
        
        # Cancel all workers
        for worker in self.workers:
            worker.cancel()
        
        # Wait for workers to complete
        if self.workers:
            await asyncio.gather(*self.workers, return_exceptions=True)
        
        self.workers.clear()
        
        # Shutdown thread pool
        self.thread_pool.shutdown(wait=True)
        
        logger.info("Worker pool stopped")
    
    async def _worker(self, name: str):
        """Worker coroutine that processes tasks from the queue"""
        logger.info(f"Worker {name} started")
        
        while self.is_running:
            try:
                # Wait for task with timeout
                task = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                
                logger.debug(f"Worker {name} processing task {task.id}")
                
                # Check quota before processing
                if not await self.quota_manager.check_quota():
                    # Put task back in queue and wait
                    await self.queue.put(task)
                    await asyncio.sleep(5)
                    continue
                
                # Rate limiting
                await self.rate_limiter.wait_if_needed()
                
                # Process the task
                try:
                    if asyncio.iscoroutinefunction(task.func):
                        result = await task.func(*task.args, **task.kwargs)
                    else:
                        # Run blocking function in thread pool
                        result = await asyncio.get_event_loop().run_in_executor(
                            self.thread_pool,
                            lambda: task.func(*task.args, **task.kwargs)
                        )
                    
                    self.completed_tasks += 1
                    logger.debug(f"Worker {name} completed task {task.id}")
                    
                except Exception as e:
                    self.failed_tasks += 1
                    logger.error(f"Worker {name} failed task {task.id}: {e}")
                    
                    # Handle quota exceeded
                    if "quota" in str(e).lower() or "rate limit" in str(e).lower():
                        await self.quota_manager.handle_quota_exceeded()
                
                # Mark task as done
                self.queue.task_done()
                
            except asyncio.TimeoutError:
                # No tasks to process, continue
                continue
            except Exception as e:
                logger.error(f"Worker {name} error: {e}")
    
    async def submit_task(
        self,
        func: Callable,
        *args,
        task_id: str = None,
        priority: int = 0,
        **kwargs
    ) -> str:
        """
        Submit a task to the worker pool
        
        Args:
            func: Function to execute
            *args: Function arguments
            task_id: Optional task ID
            priority: Task priority (higher = more important)
            **kwargs: Function keyword arguments
            
        Returns:
            Task ID
        """
        if not self.is_running:
            await self.start()
        
        if not task_id:
            task_id = f"task-{datetime.utcnow().isoformat()}-{id(func)}"
        
        task = WorkerTask(
            id=task_id,
            func=func,
            args=args,
            kwargs=kwargs,
            created_at=datetime.utcnow(),
            priority=priority
        )
        
        try:
            await self.queue.put(task)
            logger.debug(f"Submitted task {task_id}")
            return task_id
        except asyncio.QueueFull:
            logger.error(f"Queue full, rejecting task {task_id}")
            raise Exception("Worker pool queue is full")
    
    async def execute_sync(
        self,
        func: Callable,
        *args,
        timeout: Optional[float] = 30.0,
        **kwargs
    ) -> Any:
        """
        Execute a task synchronously (wait for result)
        
        Args:
            func: Function to execute
            *args: Function arguments
            timeout: Maximum time to wait for result
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
        """
        if not self.is_running:
            await self.start()
        
        # Check quota first
        if not await self.quota_manager.check_quota():
            raise Exception("API quota exceeded")
        
        # Rate limiting
        await self.rate_limiter.wait_if_needed()
        
        try:
            if asyncio.iscoroutinefunction(func):
                return await asyncio.wait_for(func(*args, **kwargs), timeout)
            else:
                return await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        self.thread_pool,
                        lambda: func(*args, **kwargs)
                    ),
                    timeout
                )
        except Exception as e:
            # Handle quota exceeded
            if "quota" in str(e).lower() or "rate limit" in str(e).lower():
                await self.quota_manager.handle_quota_exceeded()
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """Get worker pool statistics"""
        uptime = (datetime.utcnow() - self.start_time).total_seconds()
        
        return {
            "is_running": self.is_running,
            "workers": len(self.workers),
            "queue_size": self.queue.qsize(),
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "uptime_seconds": uptime,
            "tasks_per_second": self.completed_tasks / uptime if uptime > 0 else 0
        }

# Global worker pool instance
_worker_pool: Optional[WorkerPool] = None

def get_worker_pool() -> WorkerPool:
    """Get the global worker pool instance"""
    global _worker_pool
    if _worker_pool is None:
        _worker_pool = WorkerPool()
    return _worker_pool

async def shutdown_worker_pool():
    """Shutdown the global worker pool"""
    global _worker_pool
    if _worker_pool:
        await _worker_pool.stop()
        _worker_pool = None