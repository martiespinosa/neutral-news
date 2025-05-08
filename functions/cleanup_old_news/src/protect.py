import time
import traceback

def protect_referenced_news(db, time_threshold):
    """
    Find news IDs referenced in active neutral_news to protect them from deletion
    
    Args:
        db: Firestore database instance
        time_threshold: Time threshold used for active neutral_news
        
    Returns:
        set: Set of news IDs to protect
    """
    print(f"Identifying news documents referenced in active neutral_news...")
    start_time = time.time()
    
    try:
        # Get active neutral_news (not older than threshold)
        active_neutral_docs = db.collection('neutral_news').where('created_at', '>=', time_threshold).stream()
        
        # Collect all source IDs
        protected_ids = set()
        doc_count = 0
        
        for doc in active_neutral_docs:
            doc_count += 1
            data = doc.to_dict()
            if 'source_ids' in data:
                for source_id in data['source_ids']:
                    protected_ids.add(source_id)
        
        elapsed = time.time() - start_time
        print(f"  ✓ Found {len(protected_ids)} protected news IDs from {doc_count} active neutral_news documents ({elapsed:.2f}s)")
        return protected_ids
        
    except Exception as e:
        print(f"  ✗ Error identifying protected news: {str(e)}")
        traceback.print_exc()
        return set()