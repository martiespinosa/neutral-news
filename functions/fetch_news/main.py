from firebase_functions import scheduler_fn, options
import traceback
from src.functions.scheduled_tasks import fetch_news_task

# Set the region for deployment
options.set_global_options(region=options.SupportedRegion.US_CENTRAL1)

@scheduler_fn.on_schedule(
    schedule="0 * * * *",  # Ejecutar a cada hora en punto (minuto 0)
    memory=4096,
    timeout_sec=540
)
def fetch_news(event: scheduler_fn.ScheduledEvent) -> None:
    print("Ejecutando fetch_news function...")
    try:
        fetch_news_task()
        print("fetch_news task completada.")
    except Exception as e:
        print(f"Error en fetch_news function: {str(e)}")
        traceback.print_exc()