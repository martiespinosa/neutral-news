from firebase_functions import https_fn, scheduler_fn
from src.functions.scheduled_tasks import fetch_news, group_news, cleanup_old_news

# Exportar todas las funciones
exports = {
    "fetch_news": fetch_news,
    "group_news": group_news,
    "cleanup_old_news": cleanup_old_news
}