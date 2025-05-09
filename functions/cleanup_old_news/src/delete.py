import time
import traceback

def delete_documents_batch(db, docs, batch_size=450, collection_name=''):
    """
    Delete a list of documents in batches.
    
    Args:
        db: Firestore database instance
        docs: List of document references to delete
        batch_size: Maximum batch size (Firestore limit is 500)
        collection_name: Name of collection (for logging)
        
    Returns:
        int: Number of deleted documents
    """
    batch = db.batch()
    deleted_count = 0
    start_time = time.time()
    
    try:
        for i, doc in enumerate(docs):
            batch.delete(doc.reference)
            deleted_count += 1
            
            if (i + 1) % batch_size == 0:
                print(f"  - Committing batch {(i + 1) // batch_size} ({batch_size} items) from {collection_name}...")
                batch.commit()
                batch = db.batch()

        if deleted_count % batch_size != 0:
            batch.commit()
        
        elapsed = time.time() - start_time
        if deleted_count > 0:
            print(f"  ✓ Deleted {deleted_count} documents from {collection_name} in {elapsed:.2f} seconds")
        return deleted_count
        
    except Exception as e:
        print(f"  ✗ Error while deleting documents from {collection_name}: {str(e)}")
        traceback.print_exc()
        return deleted_count