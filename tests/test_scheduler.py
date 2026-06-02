import asyncio
import unittest
from src.scheduler import StateContext, PriorityScheduler, SchedulerTask, SwingInterruptionMatrix

class TestScheduler(unittest.TestCase):
    def test_state_context_slots(self) -> None:
        """Verifies that StateContext restricts allocations via __slots__ and blocks dynamic __dict__."""
        context = StateContext()
        self.assertFalse(hasattr(context, '__dict__'))
        
        with self.assertRaises(AttributeError):
            context.dynamic_attribute = "test_value"  # type: ignore

    def test_scheduler_task_slots(self) -> None:
        """Verifies that SchedulerTask restricts allocations via __slots__."""
        async def dummy_coro() -> None:
            pass
            
        coro = dummy_coro()
        task = SchedulerTask(priority=1, name="test", coro=coro)
        self.assertFalse(hasattr(task, '__dict__'))
        coro.close()

    def test_priority_ordering(self) -> None:
        """Verifies that SchedulerTasks are compared and sorted by priority values first."""
        async def dummy_coro() -> None:
            pass
            
        coro_high = dummy_coro()
        coro_low = dummy_coro()
        task_high = SchedulerTask(priority=1, name="high", coro=coro_high)
        task_low = SchedulerTask(priority=2, name="low", coro=coro_low)
        
        # Lower integer = higher priority
        self.assertTrue(task_high < task_low)
        coro_high.close()
        coro_low.close()

    def test_scheduler_preemption(self) -> None:
        """Verifies that scheduling a higher-priority task preempts (cancels) the active lower-priority task."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        context = StateContext()
        scheduler = PriorityScheduler(context)
        
        low_prio_started = asyncio.Event()
        low_prio_cancelled = False
        high_prio_executed = False
        
        async def low_prio_coro() -> None:
            nonlocal low_prio_cancelled
            low_prio_started.set()
            try:
                await asyncio.sleep(2.0)
            except asyncio.CancelledError:
                low_prio_cancelled = True
                raise

        async def high_prio_coro() -> None:
            nonlocal high_prio_executed
            high_prio_executed = True

        async def run_test() -> None:
            # Start scheduler run loop
            sched_task = asyncio.create_task(scheduler.run())
            
            # 1. Schedule low priority task (priority 3)
            scheduler.schedule(3, "low_prio", low_prio_coro())
            
            # Wait for the low priority task to begin executing
            await low_prio_started.wait()
            
            # 2. Schedule high priority task (priority 1)
            scheduler.schedule(1, "high_prio", high_prio_coro())
            
            # Allow reactor loop step to process cancellation and switch tasks
            await asyncio.sleep(0.1)
            
            # Stop scheduler loop
            scheduler.stop()
            await sched_task

        try:
            loop.run_until_complete(run_test())
            self.assertTrue(low_prio_cancelled, "Low priority task was not preempted/cancelled.")
            self.assertTrue(high_prio_executed, "High priority task was not executed.")
        finally:
            loop.close()

    def test_swing_interruption(self) -> None:
        """Verifies that the SwingInterruptionMatrix successfully flags desyncs and tool breaks."""
        context = StateContext()
        matrix = SwingInterruptionMatrix(context)
        
        # Valid active state
        context.slot_confirmed = True
        context.current_durability = 100
        self.assertTrue(matrix.validate_swing())

        # Durability depletion checks
        context.current_durability = 0
        self.assertFalse(matrix.validate_swing())
        self.assertTrue(context.swing_interrupted)
        
        # Slot changes pending checks
        context.current_durability = 100
        context.slot_confirmed = False
        context.swing_interrupted = False
        self.assertFalse(matrix.validate_swing())
        self.assertTrue(context.swing_interrupted)

        # Slot change handler updates state context locks
        context.slot_confirmed = True
        context.swing_interrupted = False
        context.action_lock.set()
        
        matrix.handle_slot_change(0, 1)
        self.assertFalse(context.slot_confirmed)
        self.assertTrue(context.swing_interrupted)
        self.assertFalse(context.action_lock.is_set())


if __name__ == "__main__":
    unittest.main()
