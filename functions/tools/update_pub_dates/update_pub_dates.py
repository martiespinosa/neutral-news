import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import os
import argparse
import sys
import time

# Path to Firebase service account - Relative path from script location
SERVICE_ACCOUNT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../neutralnews-ca548-firebase-adminsdk-fbsvc-b2a2b9fa03.json'))

def parse_pub_date(date_str):
    """
    Parse publication date from various formats into datetime object
    """
    if not date_str:
        return None
        
    if isinstance(date_str, datetime):
        return date_str
        
    if not isinstance(date_str, str):
        return None
        
    date_formats = [
        "%a, %d %b %Y %H:%M:%S %Z",         # Wed, 9 Apr 2025 19:00:00 GMT
        "%a, %d %b %Y %H:%M:%S %z",         # Sat, 10 May 2025 16:55:26 +0200
        "%d %b %Y %H:%M:%S %z",             # 03 Dec 2024 14:20:05 +0100
        "%Y-%m-%dT%H:%M:%S%z",              # 2025-05-14T23:31:37+02:00
        "%Y-%m-%d %H:%M:%S%z",              # 2025-05-14 23:31:37+02:00
        "%Y-%m-%dT%H:%M:%S.%f%z",           # 2025-05-14T23:31:37.000+02:00
        "%a, %d %b %Y %H:%M:%S",            # Wed, 9 Apr 2025 19:00:00
        "%d %b %Y %H:%M:%S",                # 03 Dec 2024 14:20:05
        "%Y-%m-%dT%H:%M:%S",                # 2025-05-14T23:31:37
        "%Y-%m-%d %H:%M:%S",                # 2025-05-14 23:31:37
    ]
    
    # Handle common timezone abbreviations
    cleaned_date_str = date_str
    timezone_mappings = {
        " GMT": " +0000",
        " UTC": " +0000",
        " UT": " +0000",
        " Z": " +0000",
        " EST": " -0500",
        " EDT": " -0400",
        " CST": " -0600",
        " CDT": " -0500",
        " MST": " -0700",
        " MDT": " -0600",
        " PST": " -0800",
        " PDT": " -0700",
        " BST": " +0100",
        " CET": " +0100",
        " CEST": " +0200"
    }
    
    # Replace timezone abbreviations with numeric offsets
    for tz, offset in timezone_mappings.items():
        if date_str.endswith(tz):
            cleaned_date_str = date_str.replace(tz, offset)
            break
    
    # Try parsing with each format
    for date_format in date_formats:
        try:
            return datetime.strptime(cleaned_date_str, date_format)
        except ValueError:
            continue
    
    return None

def format_datetime_spanish(dt):
    """Format datetime in Spanish style"""
    months = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio", 
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
    ]
    
    # Get UTC+2 time (or the current timezone)
    local_dt = dt
    if dt.tzinfo is None:
        # Assume it's already in local time
        pass
    else:
        # Convert to UTC+2
        try:
            import pytz
            local_dt = dt.astimezone(pytz.timezone('Europe/Madrid'))
        except:
            # If pytz is not available, use the current timezone
            pass
    
    # Format: "13 de mayo de 2025, 11:00:41 p.m. UTC+2"
    am_pm = "p.m." if local_dt.hour >= 12 else "a.m."
    hour_12 = local_dt.hour % 12
    if hour_12 == 0:
        hour_12 = 12
        
    formatted = f"{local_dt.day} de {months[local_dt.month-1]} de {local_dt.year}, "
    formatted += f"{hour_12}:{local_dt.minute:02d}:{local_dt.second:02d} {am_pm} UTC+2"
    
    return formatted

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Update pub_date fields in news collection to Timestamp format')
    parser.add_argument('--batch', type=int, default=450, help='Batch size for updates (default: 450)')
    parser.add_argument('--limit', type=int, default=0, help='Limit number of documents to update (0 for all)')
    parser.add_argument('--force', action='store_true', help='Skip confirmation prompt')
    parser.add_argument('--test', action='store_true', help='Test mode: only show what would be updated')
    args = parser.parse_args()

    print(f"⏱️ Timestamp format example: {format_datetime_spanish(datetime.now())}")
    print(f"Connecting to Firebase...")
    
    try:
        cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred)
    except Exception as e:
        print(f"❌ Failed to initialize Firebase: {str(e)}")
        sys.exit(1)

    db = firestore.client()
    
    print(f"Querying news collection for documents with pub_date...")
    
    # Query documents with pub_date field
    query = db.collection('news')
    
    try:
        # First get all documents
        docs = list(query.stream())
        doc_count = len(docs)
        
        print(f"Found {doc_count} total documents in the news collection.")
        
        # Filter documents that need updating
        docs_to_update = []
        for doc in docs:
            data = doc.to_dict()
            pub_date = data.get('pub_date')
            
            # Skip if pub_date doesn't exist
            if pub_date is None:
                continue
                
            # Skip if pub_date is already a Timestamp (server timestamp or proper datetime)
            if isinstance(pub_date, type(firestore.SERVER_TIMESTAMP)) or \
               (hasattr(pub_date, 'timestamp') and callable(getattr(pub_date, 'timestamp'))):
                continue
            
            # Check if pub_date is a string or another format that needs conversion
            if isinstance(pub_date, str) or not isinstance(pub_date, datetime):
                docs_to_update.append((doc, pub_date))
        
        update_count = len(docs_to_update)
        
        print(f"Found {update_count} documents with pub_date field that needs to be updated.")
        
        if update_count == 0:
            print("No documents need updating. Exiting.")
            sys.exit(0)
            
        # Ask for confirmation before proceeding
        if not args.force and not args.test:
            confirmation = input(f"\n⚠️  WARNING: You are about to update pub_date to Timestamp format for {update_count} documents.\n"
                               f"This operation will convert string dates to Firestore Timestamps.\n"
                               f"Proceed? (yes/no): ")
            
            if confirmation.lower() not in ["yes", "y"]:
                print("Operation cancelled by user. No documents were updated.")
                sys.exit(0)
            
            print("\nProceeding with updates...")
            
        # Process in batches
        batch_size = min(args.batch, 450)  # Firestore batch limit is 500
        processed_count = 0
        failed_count = 0
        success_count = 0
        sample_conversions = []
        
        # Process batches
        for i in range(0, update_count, batch_size):
            # Create new batch for each set
            if not args.test:
                batch = db.batch()
                
            current_batch_size = 0
            current_batch_docs = docs_to_update[i:i+batch_size]
            
            print(f"Processing batch {i//batch_size + 1}/{(update_count + batch_size - 1)//batch_size} ({len(current_batch_docs)} documents)...")
            
            for doc, old_pub_date in current_batch_docs:
                processed_count += 1
                doc_id = doc.id
                
                # Try to parse the date
                new_date = parse_pub_date(old_pub_date)
                
                # Skip if parsing failed
                if new_date is None:
                    print(f"  ⚠️ Could not parse date '{old_pub_date}' for document {doc_id}, skipping.")
                    failed_count += 1
                    continue
                
                # Keep sample for displaying
                if len(sample_conversions) < 5:
                    sample_conversions.append((old_pub_date, format_datetime_spanish(new_date)))
                
                # Update in test mode or real mode
                if args.test:
                    print(f"  🔄 Would update document {doc_id}: {old_pub_date} → {new_date}")
                    success_count += 1
                else:
                    try:
                        batch.update(doc.reference, {'pub_date': new_date})
                        current_batch_size += 1
                        success_count += 1
                    except Exception as e:
                        print(f"  ❌ Error updating document {doc_id}: {str(e)}")
                        failed_count += 1
                
                # Check if we've hit the document limit
                if args.limit > 0 and processed_count >= args.limit:
                    print(f"Reached limit of {args.limit} documents.")
                    break
            
            # Commit batch if not in test mode
            if not args.test and current_batch_size > 0:
                try:
                    print(f"  💾 Committing batch of {current_batch_size} updates...")
                    batch.commit()
                    print(f"  ✅ Batch committed successfully.")
                except Exception as e:
                    print(f"  ❌ Error committing batch: {str(e)}")
                    failed_count += current_batch_size
                    success_count -= current_batch_size
            
            # Check if we've hit the document limit
            if args.limit > 0 and processed_count >= args.limit:
                break
        
        # Display sample conversions
        if sample_conversions:
            print("\n📊 Sample conversions:")
            for i, (old, new) in enumerate(sample_conversions):
                print(f"  {i+1}. '{old}' → '{new}'")
        
        # Final report
        if args.test:
            print(f"\n🧪 TEST MODE: No changes were made to the database.")
            print(f"  Would have updated {success_count} documents.")
            print(f"  Would have failed on {failed_count} documents.")
        else:
            print(f"\n✅ Finished updating pub_date fields.")
            print(f"  Successfully updated {success_count} documents.")
            print(f"  Failed to update {failed_count} documents.")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    start_time = time.time()
    main()
    elapsed_time = time.time() - start_time
    print(f"\n⏱️ Total execution time: {elapsed_time:.2f} seconds")
