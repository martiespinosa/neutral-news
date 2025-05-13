import firebase_admin
from firebase_admin import credentials, firestore
import os

# Path to service account JSON file - Relative path from script location
SERVICE_ACCOUNT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../neutralnews-ca548-firebase-adminsdk-fbsvc-b2a2b9fa03.json'))

def main():
    print("Connecting to Firebase...")
    cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
    firebase_admin.initialize_app(cred)
    db = firestore.client()

    print("Fetching neutral news documents...")
    # Query all neutral news documents
    neutral_news_docs = db.collection('neutral_news').stream()
    
    neutral_news_to_update = []
    
    # Process each neutral news document
    for neutral_doc in neutral_news_docs:
        neutral_data = neutral_doc.to_dict()
        neutral_id = neutral_doc.id
        
        # Get the group of the neutral news
        neutral_group = neutral_data.get('group')
        if not neutral_group:
            print(f"⚠️ Neutral news {neutral_id} has no group assigned. Skipping.")
            continue
            
        # Get source_ids list
        source_ids = neutral_data.get('source_ids', [])
        if not source_ids:
            continue
            
        mismatched_sources = []
        sources_to_keep = []
        
        # Check each source_id
        for source_id in source_ids:
            # Get the source document
            source_doc = db.collection('news').document(source_id).get()
            if not source_doc.exists:
                print(f"⚠️ Source {source_id} referenced in neutral news {neutral_id} doesn't exist.")
                mismatched_sources.append(source_id)
                continue
                
            source_data = source_doc.to_dict()
            source_group = source_data.get('group')
            
            # If source has no group or different group, mark for removal
            if not source_group or source_group != neutral_group:
                print(f"👉 Source {source_id} (group: {source_group}) doesn't match neutral news {neutral_id} (group: {neutral_group})")
                mismatched_sources.append(source_id)
            else:
                sources_to_keep.append(source_id)
        
        # If there are mismatched sources, prepare update
        if mismatched_sources:
            neutral_news_to_update.append({
                'doc': neutral_doc,
                'current_sources': source_ids,
                'sources_to_keep': sources_to_keep,
                'mismatched_sources': mismatched_sources
            })
    
    # Show summary and ask for confirmation
    print(f"\nFound {len(neutral_news_to_update)} neutral news documents with mismatched source IDs.")
    
    if len(neutral_news_to_update) == 0:
        print("No documents to update. Exiting.")
        return
    
    # Print details of what will be updated
    for idx, update_info in enumerate(neutral_news_to_update, 1):
        print(f"\n{idx}. Neutral News ID: {update_info['doc'].id}")
        print(f"   Current sources: {len(update_info['current_sources'])}")
        print(f"   Sources to remove: {len(update_info['mismatched_sources'])}")
        print(f"   Sources to keep: {len(update_info['sources_to_keep'])}")
    
    # Ask for confirmation
    confirmation = input(f"\nAre you sure you want to update these {len(neutral_news_to_update)} neutral news documents? (yes/no): ").strip().lower()
    
    if confirmation != 'yes':
        print("Operation cancelled. No documents were updated.")
        return
    
    # Proceed with updates
    updated_count = 0
    for update_info in neutral_news_to_update:
        doc = update_info['doc']
        sources_to_keep = update_info['sources_to_keep']
        
        print(f"🔄 Updating neutral news {doc.id} - Removing {len(update_info['mismatched_sources'])} source IDs")
        
        # Update the document
        doc.reference.update({'source_ids': sources_to_keep})
        updated_count += 1
    
    print(f"\n✅ Finished. Updated {updated_count} neutral news documents with mismatched source IDs.")

if __name__ == '__main__':
    main()
