import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta
import os

# Ruta al archivo JSON de tu cuenta de servicio - Relative path from script location
SERVICE_ACCOUNT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../neutralnews-ca548-firebase-adminsdk-fbsvc-b2a2b9fa03.json'))

def main():
    print("Connecting to Firebase...")
    cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    
    print("Updating groups associated with deleted source_ids...")
    group_update_count = 0

    group_docs = db.collection('news').where('neutral_score', '!=', None).stream()
    for group_doc in group_docs:
        print(f"🔄 Updating news document {group_doc.id}.")
        group_doc.reference.update({'neutral_score': None})
        group_update_count += 1
    print(f"\n✅ Finished. Updated {group_update_count} news documents to set neutral_score to None.")
    
    group_update_count = 0
    group_docs = db.collection('news').where('group', '!=', None).stream()
    for group_doc in group_docs:
        print(f"🔄 Updating news document {group_doc.id}.")
        group_doc.reference.update({'group': None})
        group_update_count += 1
    print(f"\n✅ Finished. Updated {group_update_count} news documents to set group to None.")
    
    group_update_count = 0
    group_docs = db.collection('news').where('updated_at', '!=', None).stream()
    for group_doc in group_docs:
        print(f"🔄 Updating news document {group_doc.id}.")
        group_doc.reference.update({'updated_at': None})
        group_update_count += 1
    print(f"\n✅ Finished. Updated {group_update_count} news documents to set updated_at to None.")
if __name__ == '__main__':
    main() 