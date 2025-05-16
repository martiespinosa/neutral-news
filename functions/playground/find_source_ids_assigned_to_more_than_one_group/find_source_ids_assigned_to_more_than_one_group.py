import firebase_admin
from firebase_admin import credentials, firestore
import os
from collections import defaultdict

# Ruta al archivo JSON de tu cuenta de servicio - Relative path from script location
SERVICE_ACCOUNT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../neutralnews-ca548-firebase-adminsdk-fbsvc-b2a2b9fa03.json'))

def main():
    print("Connecting to Firebase...")
    cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
    firebase_admin.initialize_app(cred)
    db = firestore.client()

    print("Analyzing news and neutral_news collections for duplicate source IDs across groups...")
    
    # First, get all news documents with their source_id and current group
    news_docs = db.collection('news').stream()
    
    # Dictionary to store source_id -> current_group mapping
    source_current_group = {}
    
    # Process news collection to get current groups
    for doc in news_docs:
        data = doc.to_dict()
        source_id = data.get('id')
        group = data.get('group')
        
        if source_id and group:
            source_current_group[source_id] = group
    
    print(f"Found {len(source_current_group)} news items with source IDs and group information")
    
    # Next, check the neutral_news collection to find groups containing each source_id
    # Dictionary to store source_id -> list of groups
    source_groups = defaultdict(set)
    
    # Query all neutral_news documents
    neutral_groups = db.collection('neutral_news').stream()
    
    for group_doc in neutral_groups:
        group_id = group_doc.id
        group_data = group_doc.to_dict()

        # Check if the group has source_ids field
        source_ids = group_data.get('source_ids', [])

        for source_id in source_ids:
            source_groups[source_id].add(group_id)
    
    # Find source IDs that appear in multiple groups
    duplicated_sources = {source_id: groups for source_id, groups in source_groups.items() if len(groups) > 1}
    
    if not duplicated_sources:
        print("\nNo source IDs are assigned to multiple groups. Everything is properly organized!")
        return
    
    # Display the results
    print(f"\nFound {len(duplicated_sources)} source IDs assigned to multiple groups:")
    print("-" * 80)
    
    for source_id, groups in duplicated_sources.items():
        current_group = source_current_group.get(source_id, "Unknown")
        old_groups = [g for g in groups if g != current_group]
        
        print(f"Source ID: {source_id}")
        print(f"  Current Group: {current_group}")
        print(f"  Appears in {len(groups)} groups: {', '.join(groups)}")
        print(f"  Old Groups: {', '.join(old_groups) if old_groups else 'None'}")
        print("-" * 80)
    
    print("\n✅ Analysis completed. This was for information only; no documents were modified.")

if __name__ == '__main__':
    main()
