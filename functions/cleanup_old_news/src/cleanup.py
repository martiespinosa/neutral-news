import time
import traceback
from google.cloud import firestore
from src.delete import delete_documents_batch

def cleanup_collection(db, collection_name, time_threshold, batch_size=450):
    """
    Delete old documents from a specific collection.
    
    Args:
        db: Firestore database instance
        collection_name: Collection to clean up
        time_threshold: Delete documents older than this timestamp
        batch_size: Maximum batch size for Firestore operations
        
    Returns:
        int: Number of deleted documents
    """
    print(f"Processing collection: {collection_name}")
    start_time = time.time()

    try:
        # Get documents older than threshold
        old_docs_query = db.collection(collection_name).where('created_at', '<', time_threshold)
        old_docs = list(old_docs_query.stream())
        
        if not old_docs:
            print(f"  ℹ️ No old documents found in {collection_name}")
            return 0
        
        print(f"  Found {len(old_docs)} documents to delete in {collection_name}")
        
        # Delete the old documents
        deleted_count = delete_documents_batch(db, old_docs, batch_size, collection_name)
        
        elapsed = time.time() - start_time
        print(f"  ✓ Completed {collection_name} cleanup in {elapsed:.2f} seconds")
        return deleted_count
        
    except Exception as e:
        print(f"  ✗ Error processing collection {collection_name}: {str(e)}")
        traceback.print_exc()
        return 0