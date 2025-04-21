from firebase_functions import scheduler_fn
from datetime import datetime, timedelta
import traceback

from src.process import process_news_groups
from src.storage import store_news_in_firestore
from src.config import initialize_firebase
from src.functions.news_api import fetch_all_rss

@scheduler_fn.on_schedule(schedule="every 4 hours", memory=4096, timeout_sec=540)
def fetch_news(event: scheduler_fn.ScheduledEvent) -> None:
    try:
        print("Starting periodic RSS loading...")
        
        # Get all news from RSS
        all_news = fetch_all_rss()
        print(f"Total news obtained: {len(all_news)}")
        
        # Save news to Firestore
        if all_news:
            stored_count = store_news_in_firestore(all_news)
            print(f"{stored_count} new news were saved")
        else:
            print("No news found to save")
        
        # Process and group news directly
        print("Starting news grouping...")
        updated_count = process_news_groups()
        print(f"Groups were updated for {updated_count} news")
      
        print("RSS processing completed successfully")
        return None
    except Exception as e:
        print(f"Error in fetch_news: {str(e)}")
        traceback.print_exc()
        return None

# @scheduler_fn.on_schedule(schedule="every 1 hours", memory=4096, timeout_sec=300)
def group_news(event: scheduler_fn.ScheduledEvent) -> None:
    try:
        print("Starting scheduled news grouping...")
        updated_count = process_news_groups()
        print(f"Groups were updated for {updated_count} news")
        return None
    except Exception as e:
        print(f"Error in group_news: {str(e)}")
        traceback.print_exc()
        return None

@scheduler_fn.on_schedule(schedule="every 24 hours", memory=1024, timeout_sec=300)
def cleanup_old_news(event: scheduler_fn.ScheduledEvent) -> None:
    try:
        print("Starting old news deletion process...")
        
        # Calculate the threshold for news older than 7 days
        time_threshold = datetime.now() - timedelta(hours=168)
        
        # Initialize Firestore
        db = initialize_firebase()
        
        # Colecciones a limpiar
        collections = ['news', 'neutral_news']
        total_deleted = 0
        
        for collection_name in collections:
            # Query for news older than 7 days
            old_news_query = db.collection(collection_name).where('created_at', '<', time_threshold)
            
            # Get the documents
            old_news_docs = list(old_news_query.stream())
            
            # Create a batch for deletion
            batch = db.batch()
            deleted_count = 0
            
            for doc in old_news_docs:
                batch.delete(doc.reference)
                deleted_count += 1
                
                # Firebase has a limit of 500 operations per batch
                if deleted_count % 450 == 0:
                    batch.commit()
                    batch = db.batch()
            
            # Commit any remaining deletions
            if deleted_count % 450 != 0:
                batch.commit()
            
            print(f"Deleted {deleted_count} news items from {collection_name} older than 7 days")
            total_deleted += deleted_count
        
        print(f"Total deleted: {total_deleted} news items older than 7 days")
        
    except Exception as e:
        print(f"Error in cleanup_old_news: {str(e)}")
        traceback.print_exc()