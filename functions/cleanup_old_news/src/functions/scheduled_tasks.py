from datetime import datetime, timedelta
import traceback
from src.config import initialize_firebase


def cleanup_old_news_task():
    try:
        print("Starting old news deletion process...")
        time_threshold = datetime.now() - timedelta(days=7)
        db = initialize_firebase()

        collections = ['news', 'neutral_news']
        total_deleted = 0

        for collection_name in collections:
            old_news_query = db.collection(collection_name).where('created_at', '<', time_threshold)
            old_news_docs = list(old_news_query.stream())

            batch = db.batch()
            deleted_count = 0

            for doc in old_news_docs:
                batch.delete(doc.reference)
                deleted_count += 1
                if deleted_count % 450 == 0:
                    batch.commit()
                    batch = db.batch()

            if deleted_count % 450 != 0:
                batch.commit()

            print(f"Deleted {deleted_count} news items from {collection_name}")
            total_deleted += deleted_count

        print(f"Total deleted: {total_deleted} news items older than 7 days")

    except Exception as e:
        print(f"Error in cleanup_old_news_task: {str(e)}")
        traceback.print_exc()
