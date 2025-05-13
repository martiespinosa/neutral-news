import traceback
from src.process import process_news_groups
from src.storage import store_news_in_firestore
from src.parsers import fetch_all_rss

def fetch_news_task():
    try:
        print("🪵 Starting periodic RSS loading...")
        all_news = fetch_all_rss()
        print(f"🪵 Total news obtained: {len(all_news)}")
        
        print("🪵 Storing news in Firestore...")
        stored_count = store_news_in_firestore(all_news)
        print(f"{stored_count} new news were saved")
        
        print("🪵 Starting news grouping...")
        process_news_groups()
        print("🪵 RSS processing completed successfully")
    except Exception as e:
        print(f"Error in fetch_news_task: {str(e)}")
        traceback.print_exc()