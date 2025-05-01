# main.py for cleanup_old_news

from firebase_functions import scheduler_fn
import traceback
# Import the specific task logic
# Assuming the src structure is copied directly
from src.functions.scheduled_tasks import cleanup_old_news_task

@scheduler_fn.on_schedule(schedule="every 24 hours", memory=1024, timeout_sec=300)
def cleanup_old_news(event: scheduler_fn.ScheduledEvent) -> None:
    """Triggers the cleanup_old_news_task."""
    try:
        print("Executing cleanup_old_news task...")
        cleanup_old_news_task()
        print("cleanup_old_news task completed.")
    except Exception as e:
        print(f"Error in cleanup_old_news function: {str(e)}")
        traceback.print_exc()

# Ensure the function is registered if running locally with functions-framework
# functions-framework --target cleanup_old_news --source .