from firebase_functions import scheduler_fn, options, pubsub
from datetime import datetime, timedelta
import traceback
import base64 # Import base64 if you need to decode the message body

from src.process import process_news_groups
from src.storage import store_news_in_firestore
from src.config import initialize_firebase
from src.parsers import fetch_all_rss

options.set_global_options(region=options.SupportedRegion.US_CENTRAL1) # Or your desired region e.g. us_central1

# Note: The @scheduler_fn decorator is no longer strictly necessary
# if deploying via gcloud with --trigger-topic, but it doesn't hurt.
# The important part is the function signature.

# Change the function signature to accept event and context
def fetch_news(event: pubsub.CloudEvent[pubsub.MessagePublishedData], context) -> None:
    """
    Cloud Function triggered by Pub/Sub topic to fetch and process news.
    """
    try:
        # Optional: Decode and check the message if needed
        # message_data = base64.b64decode(event.data.message.data).decode('utf-8')
        # print(f"Received message data: {message_data}")

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

# Change the function signature for cleanup_old_news as well
def cleanup_old_news(event: pubsub.CloudEvent[pubsub.MessagePublishedData], context) -> None:
    """
    Cloud Function triggered by Pub/Sub topic to clean up old news.
    """
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
            if deleted_count % 450 != 0 and deleted_count > 0: # Check if there are remaining items
                batch.commit()

            print(f"Deleted {deleted_count} news items from {collection_name} older than 7 days")
            total_deleted += deleted_count

        print(f"Total deleted: {total_deleted} news items older than 7 days")

    except Exception as e:
        print(f"Error in cleanup_old_news: {str(e)}")
        traceback.print_exc()