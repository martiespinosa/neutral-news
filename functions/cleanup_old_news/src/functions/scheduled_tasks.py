from datetime import datetime, timedelta
import traceback
import time
from src.config import initialize_firebase
from src.cleanup_news_collection import cleanup_news_collection
from src.protect import protect_referenced_news
from src.cleanup import cleanup_collection

def cleanup_old_news_task(retention_days=7, batch_size=450):
    """
    Main task to clean up old news and neutral_news documents
    
    Args:
        retention_days: Number of days to keep documents
        batch_size: Maximum batch size for Firestore operations
        
    Returns:
        bool: True if successful, False otherwise
    """
    print(f"========== CLEANUP TASK STARTED ==========")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Retention period: {retention_days} days")
    overall_start = time.time()
    
    try:
        time_threshold = datetime.now() - timedelta(days=retention_days)
        db = initialize_firebase()
        total_deleted = 0
        
        # 1. Find protected news IDs (referenced in active neutral_news)
        protected_ids = protect_referenced_news(db, time_threshold)
        
        # 2. Clean up news collection with protection
        news_deleted, news_protected = cleanup_news_collection(db, time_threshold, protected_ids, batch_size)
        total_deleted += news_deleted
        
        # 3. Clean up neutral_news collection
        neutral_deleted = cleanup_collection(db, 'neutral_news', time_threshold, batch_size)
        total_deleted += neutral_deleted
        
        overall_elapsed = time.time() - overall_start
        print(f"========== CLEANUP TASK COMPLETED ==========")
        print(f"Total deleted: {total_deleted} documents")
        print(f"Total protected: {news_protected} news documents")
        print(f"Total time: {overall_elapsed:.2f} seconds")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return True
        
    except Exception as e:
        overall_elapsed = time.time() - overall_start
        print(f"========== CLEANUP TASK FAILED ==========")
        print(f"Error in cleanup_old_news_task: {str(e)}")
        print(f"Time elapsed before failure: {overall_elapsed:.2f} seconds")
        traceback.print_exc()
        return False