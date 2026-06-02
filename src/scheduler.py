import asyncio
import heapq
import logging
import time
from typing import Any, Coroutine, List, Optional

logger = logging.getLogger("mc_auto.scheduler")

class StateContext:
    """Holds shared state parameters for the automation engine using strict memory limits."""
    __slots__ = (
        'active_slot',
        'slot_confirmed',
        'equipped_tool_multiplier',
        'current_durability',
        'player_x',
        'player_y',
        'player_z',
        'target_x',
        'target_y',
        'target_z',
        'is_mining',
        'mining_progress',
        'server_latency',
        'swing_interrupted',
        'action_lock',
    )

    def __init__(self) -> None:
        self.active_slot: int = 0
        self.slot_confirmed: bool = True
        self.equipped_tool_multiplier: float = 1.0
        self.current_durability: int = 0
        self.player_x: float = 0.0
        self.player_y: float = 0.0
        self.player_z: float = 0.0
        self.target_x: int = 0
        self.target_y: int = 0
        self.target_z: int = 0
        self.is_mining: bool = False
        self.mining_progress: float = 0.0
        self.server_latency: float = 0.0
        self.swing_interrupted: bool = False
        self.action_lock: asyncio.Event = asyncio.Event()
        self.action_lock.set()


class SchedulerTask:
    """Represents a scheduled task with an associated priority."""
    __slots__ = ('priority', 'name', 'coro', 'created_at', 'cancelled')

    def __init__(self, priority: int, name: str, coro: Coroutine[Any, Any, Any]) -> None:
        self.priority: int = priority
        self.name: str = name
        self.coro: Coroutine[Any, Any, Any] = coro
        self.created_at: float = time.time()
        self.cancelled: bool = False

    def __lt__(self, other: 'SchedulerTask') -> bool:
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.created_at < other.created_at


class PriorityScheduler:
    """Asynchronous scheduler managing task priorities and cooperative preemption."""
    __slots__ = ('_queue', '_current_task', '_active_async_task', '_running', 'context')

    def __init__(self, context: StateContext) -> None:
        self._queue: List[SchedulerTask] = []
        self._current_task: Optional[SchedulerTask] = None
        self._active_async_task: Optional[asyncio.Task] = None
        self._running: bool = False
        self.context: StateContext = context

    def schedule(self, priority: int, name: str, coro: Coroutine[Any, Any, Any]) -> SchedulerTask:
        """Schedules a new coroutine with priority. Lower integer values represent higher priorities."""
        task = SchedulerTask(priority, name, coro)
        heapq.heappush(self._queue, task)
        logger.debug(f"Scheduled task '{name}' with priority {priority}")

        # Trigger cooperative preemption if a higher priority task is submitted
        if self._current_task and task.priority < self._current_task.priority:
            if self._active_async_task and not self._active_async_task.done():
                logger.info(f"Preempting current task '{self._current_task.name}' (prio {self._current_task.priority}) for task '{task.name}' (prio {task.priority})")
                self._active_async_task.cancel()
        
        return task

    async def run(self) -> None:
        """Starts the scheduler loop."""
        self._running = True
        logger.info("Priority scheduler loop started")
        
        while self._running:
            try:
                # Wait until slot updates are confirmed by the server
                if not self.context.slot_confirmed:
                    logger.debug("Scheduler waiting for slot confirmation lock...")
                    await self.context.action_lock.wait()
                    continue

                if not self._queue:
                    await asyncio.sleep(0.01)
                    continue

                task = heapq.heappop(self._queue)
                if task.cancelled:
                    continue

                self._current_task = task
                
                # Wrap the coroutine execution into an asyncio task to support preemption (cancellation)
                self._active_async_task = asyncio.create_task(self._run_task_wrapper(task))
                try:
                    await self._active_async_task
                except asyncio.CancelledError:
                    logger.info(f"Task '{task.name}' was preempted and cancelled.")
                finally:
                    self._current_task = None
                    self._active_async_task = None

            except Exception as e:
                logger.error(f"Error in scheduler run loop: {e}", exc_info=True)
                await asyncio.sleep(0.1)

    async def _run_task_wrapper(self, task: SchedulerTask) -> None:
        try:
            await task.coro
        except asyncio.CancelledError:
            # Allow cancellation to propagate to the parent task wrapper
            raise
        except Exception as e:
            logger.error(f"Task '{task.name}' failed with exception: {e}", exc_info=True)

    def stop(self) -> None:
        """Stops the scheduler run loop."""
        self._running = False
        if self._active_async_task and not self._active_async_task.done():
            self._active_async_task.cancel()
        logger.info("Priority scheduler loop stopped")


class SwingInterruptionMatrix:
    """Manages slot confirmation timing states to protect mining sequences from speed flags."""
    __slots__ = ('context',)

    def __init__(self, context: StateContext) -> None:
        self.context: StateContext = context

    def validate_swing(self) -> bool:
        """Checks if a mining swing command is valid under current slot and server synchronization."""
        if not self.context.slot_confirmed:
            logger.warning("Mining swing invalidated: Slot changes pending server confirmation.")
            self.context.swing_interrupted = True
            return False
        
        if self.context.current_durability <= 0:
            logger.warning("Mining swing invalidated: Equipped tool has depleted durability.")
            self.context.swing_interrupted = True
            return False
            
        return True

    def handle_slot_change(self, old_slot: int, new_slot: int) -> None:
        """Preempts current action locks when slot transition is initiated by local macro client."""
        logger.info(f"Slot transition initiated: {old_slot} -> {new_slot}. Halting current actions.")
        self.context.slot_confirmed = False
        self.context.swing_interrupted = True
        self.context.action_lock.clear()
