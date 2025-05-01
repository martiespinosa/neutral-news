from firebase_functions import scheduler_fn
from firebase_functions import https_fn, options
import traceback

# Import the specific task logic
# Assuming the src structure is copied directly
from src.functions.scheduled_tasks import fetch_news_task

# Ensure the region matches your desired deployment region
options.set_global_options(region=options.SupportedRegion.US_CENTRAL1) # Or your region

@scheduler_fn.on_schedule(schedule="every 4 hours", memory=4096, timeout_sec=540)
def fetch_news(event: scheduler_fn.ScheduledEvent) -> None:
    # Your function logic here
    print("Executing fetch_news function...")
    try:
        fetch_news_task()
        print("fetch_news task completed.")
    except Exception as e:
        print(f"Error in fetch_news function: {str(e)}")
        traceback.print_exc()
    return https_fn.Response("Function executed successfully")