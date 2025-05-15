import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import os
import argparse
import sys

# Ruta al archivo JSON de tu cuenta de servicio - Relative path from script location
SERVICE_ACCOUNT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../neutralnews-ca548-firebase-adminsdk-fbsvc-b2a2b9fa03.json'))

def parse_datetime(dt_str):
    """Parse datetime string in YYYY-MM-DD HH:MM:SS format"""
    try:
        return datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        print(f"Error: Invalid datetime format '{dt_str}'. Use format: YYYY-MM-DD HH:MM:SS")
        sys.exit(1)

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Update field values to None for documents within a specific time period')
    parser.add_argument('--collection', default='news', help='Collection name (default: news)')
    parser.add_argument('--field', default='neutral_score', help='Field name to update to None (default: neutral_score)')
    parser.add_argument('--start', required=True, help='Start datetime in format YYYY-MM-DD HH:MM:SS')
    parser.add_argument('--end', required=True, help='End datetime in format YYYY-MM-DD HH:MM:SS')
    parser.add_argument('--force', action='store_true', help='Skip confirmation prompt')
    args = parser.parse_args()

    # Parse datetime strings
    start_time = parse_datetime(args.start)
    end_time = parse_datetime(args.end)

    print(f"Connecting to Firebase...")
    try:
        cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred)
    except Exception as e:
        print(f"❌ Failed to initialize Firebase: {str(e)}")
        sys.exit(1)

    db = firestore.client()
    
    print(f"Querying {args.collection} collection for documents with updated_at between {start_time} and {end_time}...")
    
    # Query documents in the specified time range
    query = db.collection(args.collection).where('updated_at', '>=', start_time).where('updated_at', '<=', end_time)
    
    try:
        docs = list(query.stream())
        doc_count = len(docs)
        
        print(f"Found {doc_count} documents to update.")
        
        # Ask for confirmation before proceeding
        if doc_count > 0 and not args.force:
            confirmation = input(f"\n⚠️  WARNING: You are about to set '{args.field}' to None for {doc_count} documents in the '{args.collection}' collection.\n"
                               f"This operation cannot be undone. Are you sure you want to continue? (yes/no): ")
            
            if confirmation.lower() not in ["yes", "y"]:
                print("Operation cancelled by user. No documents were updated.")
                sys.exit(0)
            
            print("\nProceeding with updates...")
        
        update_count = 0
        batch = db.batch()
        batch_size = 0
        max_batch_size = 450  # Firestore batch limit is 500, using 450 to be safe
        
        for doc in docs:
            print(f"🔄 Processing document {doc.id}")
            
            # Skip if the field doesn't exist in the document
            doc_data = doc.to_dict()
            if args.field not in doc_data:
                print(f"  ⚠️ Field '{args.field}' not found in document {doc.id}, skipping.")
                continue
            
            # Update the field to None
            batch.update(doc.reference, {args.field: None})
            update_count += 1
            batch_size += 1
            
            # Commit batch when we reach the limit
            if batch_size >= max_batch_size:
                print(f"  💾 Committing batch of {batch_size} updates...")
                batch.commit()
                batch = db.batch()
                batch_size = 0
        
        # Commit any remaining updates
        if batch_size > 0:
            print(f"  💾 Committing final batch of {batch_size} updates...")
            batch.commit()
        
        print(f"\n✅ Finished. Updated {update_count} documents in {args.collection} collection.")
        print(f"   Field '{args.field}' set to None for documents with 'updated_at' between {args.start} and {args.end}.")
        
    except Exception as e:
        print(f"❌ Error updating documents: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()
