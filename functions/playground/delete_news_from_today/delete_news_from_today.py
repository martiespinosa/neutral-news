import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta
import os

# Ruta al archivo JSON de tu cuenta de servicio - Relative path from script location
SERVICE_ACCOUNT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../neutralnews-ca548-firebase-adminsdk-fbsvc-b2a2b9fa03.json'))
DAYS_AGO = 14

def main():
    print("Connecting to Firebase...")
    cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
    firebase_admin.initialize_app(cred)
    db = firestore.client()

    # Calculate the cutoff date
    cutoff_date = datetime.now() - timedelta(days=DAYS_AGO)
    print(f"Cutoff date: {cutoff_date} (timezone-naive)")

    # Delete neutral_news documents created before the cutoff date
    print(f"Fetching neutral_news documents created before {cutoff_date}...")
    neutral_news_docs = db.collection('neutral_news').stream()
    neutral_news_count = 0
    deleted_source_ids = []  # To store source_ids of deleted neutral_news documents

    for doc in neutral_news_docs:
        data = doc.to_dict()
        created_at = data.get('created_at')  # Assuming 'created_at' is a timestamp field
        source_ids = data.get('source_ids', [])
        doc_id = doc.id

        # Handle the datetime comparison properly
        if created_at:
            # Convert Firestore timestamp to Python datetime if needed
            if hasattr(created_at, 'timestamp'):
                created_at_datetime = created_at.timestamp()
                created_at_datetime = datetime.fromtimestamp(created_at_datetime)
            else:
                created_at_datetime = created_at
            
            # Make created_at timezone-naive by replacing it with its value without timezone info
            if hasattr(created_at_datetime, 'tzinfo') and created_at_datetime.tzinfo is not None:
                created_at_datetime = created_at_datetime.replace(tzinfo=None)
            
            # Now compare the timezone-naive datetimes
            if created_at_datetime < cutoff_date:
                print(f"🗑️ Deleting neutral_news document {doc_id} created at {created_at_datetime} with sources: {source_ids}")
                deleted_source_ids.extend(source_ids)  # Save the source_ids
                doc.reference.delete()
                neutral_news_count += 1
            else:
                print(f"Keeping document {doc_id} created at {created_at_datetime} (newer than cutoff)")

    print(f"\n✅ Finished. Deleted {neutral_news_count} neutral_news documents created before {cutoff_date}.")

    # Set group field to None for groups associated with deleted source_ids
    print("Updating groups associated with deleted source_ids...")
    group_update_count = 0

    group_docs = db.collection('news').where('group', '!=', None).stream()
    for group_doc in group_docs:
        print(f"🔄 Updating news document {group_doc.id}.")
        group_doc.reference.update({'group': None})
        group_update_count += 1

    print(f"\n✅ Finished. Updated {group_update_count} news documents to set neutral_score to None.")

if __name__ == '__main__':
    main()