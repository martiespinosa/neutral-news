import firebase_admin
from firebase_admin import credentials, firestore
import os

# Ruta al archivo JSON de tu cuenta de servicio - Relative path from script location
SERVICE_ACCOUNT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../neutralnews-ca548-firebase-adminsdk-fbsvc-b2a2b9fa03.json'))
MIN_VALID_SOURCES = 3
def main():
    print("Connecting to Firebase...")
    cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
    firebase_admin.initialize_app(cred)
    db = firestore.client()

    print("Fetching neutral_news documents...")
    docs = db.collection('neutral_news').stream()

    count = 0
    for doc in docs:
        data = doc.to_dict()
        source_ids = data.get('source_ids', [])
        
        # Check if the document has fewer than 2 source IDs
        if len(source_ids) < MIN_VALID_SOURCES:
            doc_id = doc.id
            print(f"🗑️ Deleting document {doc_id} with only {len(source_ids)} sources: {source_ids}")
            doc.reference.delete()
            count += 1
    
    print(f"\n✅ Finished. Deleted {count} neutral_news documents with fewer than 2 sources.")

if __name__ == '__main__':
    main()