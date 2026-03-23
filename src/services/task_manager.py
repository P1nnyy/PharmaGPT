import asyncio
from typing import Dict, Optional
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

class TaskManager:
    """
    Manages background tasks for invoice scanning, allowing for 
    explicit cancellation when a user discards or clears invoices.
    """
    def __init__(self):
        # user_email -> {invoice_id -> asyncio.Task}
        self._tasks: Dict[str, Dict[str, asyncio.Task]] = {}

    def register(self, user_email: str, invoice_id: str, task: asyncio.Task):
        """
        Registers a new scanning task for a user and invoice.
        """
        if user_email not in self._tasks:
            self._tasks[user_email] = {}
        
        self._tasks[user_email][invoice_id] = task
        
        # Cleanup when task finishes naturally or is cancelled
        def cleanup(_):
            if user_email in self._tasks:
                self._tasks[user_email].pop(invoice_id, None)
                if not self._tasks[user_email]:
                    self._tasks.pop(user_email, None)
        
        task.add_done_callback(cleanup)
        logger.info(f"Registered scanning task for {invoice_id} (User: {user_email})")

    def cancel(self, user_email: str, invoice_id: str) -> bool:
        """
        Cancels a specific task for a user.
        """
        user_tasks = self._tasks.get(user_email, {})
        task = user_tasks.get(invoice_id)
        if task and not task.done():
            task.cancel()
            logger.info(f"Requested cancellation for invoice {invoice_id}")
            return True
        return False

    def cancel_all(self, user_email: str):
        """
        Cancels all active scanning tasks for a user.
        """
        user_tasks = self._tasks.get(user_email, {})
        if not user_tasks:
            return

        logger.info(f"Cancelling all active scans for user {user_email} (Count: {len(user_tasks)})")
        for invoice_id, task in list(user_tasks.items()):
            if not task.done():
                task.cancel()
        
        self._tasks.pop(user_email, None)

# Global instance
manager = TaskManager()
