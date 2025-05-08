import time
import traceback

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
            
        # Process documents
        batch = db.batch()
        deleted_count = 0
        protected_count = 0
        
        for i, doc in enumerate(old_docs):
            doc_id = doc.id
            
            if doc_id in protected_ids:
                protected_count += 1
                continue
                
            batch.delete(doc.reference)
            deleted_count += 1
            
            if deleted_count % batch_size == 0:
                print(f"  - Committing batch {deleted_count // batch_size} ({batch_size} items) from news...")
                batch.commit()
                batch = db.batch()
        
        if deleted_count % batch_size != 0:
            batch.commit()
            
        elapsed = time.time() - start_time
        print(f"  ✓ Completed news cleanup: {deleted_count} deleted, {protected_count} protected in {elapsed:.2f} seconds")
        return deleted_count, protected_count
        
    except Exception as e:
        print(f"  ✗ Error processing news collection with protection: {str(e)}")
        traceback.print_exc()
        return 0, 0