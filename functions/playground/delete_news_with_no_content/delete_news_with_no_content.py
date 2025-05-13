import firebase_admin
from firebase_admin import credentials, firestore
import os

# Ruta al archivo JSON de tu cuenta de servicio - Relative path from script location
SERVICE_ACCOUNT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../neutralnews-ca548-firebase-adminsdk-fbsvc-b2a2b9fa03.json'))

def main():
    print("Connecting to Firebase...")
    cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
    firebase_admin.initialize_app(cred)
    db = firestore.client()

    print("Fetching news documents with no content...")
    # Query all news documents to check for missing content
    news_docs = db.collection('news').stream()
    
    # First, identify documents to delete without actually deleting them
    docs_to_delete = []
    
    for doc in news_docs:
        data = doc.to_dict()
        doc_id = doc.id
        
        description = data.get('description')
        scraped_description = data.get('scraped_description')
        
        # Check if both description and scraped_description are None, empty, or missing
        if ((description is None or description.strip() == '') and 
            (scraped_description is None or scraped_description.strip() == '')):
            docs_to_delete.append(doc)
    
    # Show count and ask for confirmation
    print(f"\nFound {len(docs_to_delete)} news documents with no content.")
    
    if len(docs_to_delete) == 0:
        print("No documents to delete. Exiting.")
        return
    
    # Ask for confirmation
    confirmation = input(f"Are you sure you want to delete these {len(docs_to_delete)} documents? (yes/no): ").strip().lower()
    
    if confirmation != 'yes':
        print("Operation cancelled. No documents were deleted.")
        return
    
    # Proceed with deletion
    deleted_count = 0
    for doc in docs_to_delete:
        print(f"🗑️ Deleting news document {doc.id} with no content.")
        doc.reference.delete()
        deleted_count += 1
    
    print(f"\n✅ Finished. Deleted {deleted_count} news documents with no content.")

if __name__ == '__main__':
    main()
