import time
import traceback
from src.delete import delete_documents_batch

def cleanup_news_collection(db, time_threshold, protected_ids, batch_size=450):
    """
    Delete old news documents except those referenced in active neutral_news
    
    Args:
        db: Firestore database instance
        time_threshold: Delete documents older than this timestamp
        protected_ids: Set of news IDs to protect from deletion
        batch_size: Maximum batch size for Firestore operations
        
    Returns:
        tuple: (deleted_count, protected_count)
    """
    print(f"Processing news collection with protection...")
    start_time = time.time()
    
    try:
        # Get old news documents
        old_docs_query = db.collection('news').where('created_at', '<', time_threshold)
        old_docs = list(old_docs_query.stream())
        
        if not old_docs:
            print(f"  ℹ️ No old documents found in news collection")
            return 0, 0
            
        # Separate documents into protected and to-delete
        docs_to_delete = []
        protected_count = 0
        
        for doc in old_docs:
            if doc.id in protected_ids:
                protected_count += 1
            else:
                docs_to_delete.append(doc)
        
        # Process documents to delete in smaller batches
        deleted_count = 0
        if docs_to_delete:
            # Use a more conservative batch size to avoid "Transaction too big" errors
            adjusted_batch_size = min(batch_size, 200)  # Reduced from 450 to 200
            deleted_count = delete_documents_batch(db, docs_to_delete, adjusted_batch_size, 'news')
            
        elapsed = time.time() - start_time
        print(f"  ✓ Completed news cleanup: {deleted_count} deleted, {protected_count} protected in {elapsed:.2f} seconds")
        return deleted_count, protected_count
        
    except Exception as e:
        print(f"  ✗ Error processing news collection with protection: {str(e)}")
        traceback.print_exc()
        return 0, 0