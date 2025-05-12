import firebase_admin
from firebase_admin import credentials, firestore
import os
import argparse
import sys
import importlib
import csv
from datetime import datetime, timedelta
import time
import google.api_core.exceptions

"""SAMPLE COMMANDS: 

python select_news.py --collection news `
  --fields description,scraped_description,title `
  --match-type any `
  --filter-type contains `
  --value "barcelona"`
  --limit 25 `
  --output table `
  --no-interactive


python select_news.py --collection news `
  --equality-filter "source_medium:expansion" `
  --limit 50 `
  --export html `
  --export-path "./results" `
  --no-interactive


python select_news.py --collection news `
  --time-filter "days:3" `
  --limit 100 `
  --output table `
  --no-interactive


python select_news.py --collection news `
  --equality-filter "source_medium:expansion" `
  --time-filter "hours:12" `
  --limit 200 `
  --export excel `
  --export-path "./results/politics" `
  --no-interactive


python select_news.py --collection news `
  --fields description,scraped_description,title `
  --match-type any `
  --filter-type contains `
  --value messi `
  --limit 1000 `
  --output table `
  --exclude-embeddings `
  --no-interactive


python select_news.py --collection news `
  --equality-filter "source_medium:expansion" `
  --time-filter "hours:12" `
  --limit 200 `
  --export excel `
  --exclude-embeddings `
  --export-path "./results/politics" `
  --no-interactive
  
python select_news.py --collection news `
  --fields description,scraped_description,title `
  --match-type any `
  --filter-type contains `
  --value lautaro `
  --time-filter "hours:24" `
  --limit 200 `
  --export excel `
  --exclude-embeddings `
  --export-path "./results/politics" `
  --no-interactive
"""


required_packages = ["firebase_admin", "tabulate", "pandas", "openpyxl"]
for package in required_packages:
    try:
        importlib.import_module(package)
    except ImportError:
        print(f"Installing required package: {package}")
        os.system(f"pip install {package}")
        try:
            importlib.import_module(package)
            print(f"Successfully installed {package}")
        except ImportError:
            print(f"Failed to install {package}. Please install it manually: pip install {package}")
            sys.exit(1)

import json
from tabulate import tabulate
import pandas as pd


SERVICE_ACCOUNT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../neutralnews-ca548-firebase-adminsdk-fbsvc-b2a2b9fa03.json'))


DEFAULT_CONFIG = {
    "collection": "neutral_news",  # Options: "news", "neutral_news", "all"
    "limit": 10,                   # Maximum number of results to return
    "fields": ["neutral_title"],   # Fields to search in (can be multiple)
    "match_type": "any",           # Match type: "any" (OR) or "all" (AND)
    "filter_type": "contains",     # Options: "starts_with", "contains", "equals", "none"
    "value": "",                   # Search value
    "output": "table",             # Options: "table", "json", "raw"
    "export": None,                # Export format: "csv", "excel", "json", "html", None
    "export_path": "./results",    # Directory to save exported files
    "interactive": True,           # Whether to prompt for input
}
DEFAULT_CONFIG.update({
    "equality_filters": {},  # Format: {field: value} for exact matches
    "time_filter": {         # Time-based filter configuration
        "enabled": False,
        "field": "created_at",
        "days": 0,
        "hours": 0,
        "minutes": 0,
        "seconds": 0
    },
    "exclude_embeddings": False  # Whether to exclude embedding fields
})

FIELD_TYPES = {
    "news": {
        "title": "string",
        "description": "string",
        "scraped_description": "string",
        "category": "string",
        "image_url": "string",
        "link": "string",
        "source_medium": "string",
        "group": "number",
        "created_at": "date",
        "pub_date": "date"
    },
    "neutral_news": {
        "neutral_title": "string",
        "neutral_description": "string", 
        "category": "string",
        "relevance": "number",
        "group": "number",
        "created_at": "date"
    }
}

def initialize_firebase():
    """Initialize Firebase connection"""
    try:
        cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred)
        return firestore.client()
    except Exception as e:
        print(f"Error initializing Firebase: {str(e)}")
        return None

def format_datetime(timestamp):
    """Format Firestore timestamp for display"""
    if isinstance(timestamp, datetime):
        return timestamp.strftime('%Y-%m-%d %H:%M:%S')
    return str(timestamp)

def get_fields_to_display(collection_name):
    """Get relevant fields to display for a collection"""
    if (collection_name == "news"):
        return ["id", "title", "source_medium", "created_at", "group"]
    elif (collection_name == "neutral_news"):
        return ["group", "neutral_title", "category", "created_at", "relevance"]
    return ["id", "title", "description", "created_at"]

def get_all_searchable_fields(collection_name):
    """Get all fields that can be searched for a collection"""
    if collection_name in FIELD_TYPES:
        return list(FIELD_TYPES[collection_name].keys())
    return []

def get_string_fields(collection_name):
    """Get fields that are strings (searchable with contains/starts_with)"""
    if collection_name in FIELD_TYPES:
        return [field for field, type in FIELD_TYPES[collection_name].items() if type == "string"]
    return []

def parse_time_filter(time_filter_str):
    """Parse time filter string like 'days:3,hours:12,minutes:30'"""
    result = {
        "days": 0,
        "hours": 0,
        "minutes": 0,
        "seconds": 0
    }
    
    if not time_filter_str:
        return result
        
    parts = time_filter_str.split(',')
    for part in parts:
        if ':' in part:
            key, value = part.split(':', 1)
            key = key.strip().lower()
            if key in result and value.isdigit():
                result[key] = int(value)
                
    return result

def is_embedding_field(field_name, value):
    """Detect if a field is likely an embedding field"""

    embedding_names = ["embedding", "vector", "embeddings", "vectors", "_embedding"]
    

    if any(name in field_name.lower() for name in embedding_names):

        if isinstance(value, list) and len(value) > 50:
            return True
    return False

def filter_embeddings(data, exclude_embeddings):
    """Remove embedding fields if required"""
    if not exclude_embeddings:
        return data
        
    filtered_data = {}
    for key, value in data.items():
        if not is_embedding_field(key, value):
            filtered_data[key] = value
    return filtered_data

def search_documents(config):
    """Search documents based on configuration"""
    db = initialize_firebase()
    if not db:
        return []
    
    results = []
    collections_to_search = []
    
    if config["collection"] == "all":
        collections_to_search = ["news", "neutral_news"]
    else:
        collections_to_search = [config["collection"]]
    
    for collection_name in collections_to_search:
        print(f"Searching in collection: {collection_name}")
        query = db.collection(collection_name)
        
        try:

            for field, value in config.get("equality_filters", {}).items():
                query = query.where(field, "==", value)
            

            time_filter = config.get("time_filter", {})
            if time_filter.get("enabled", False):
                field = time_filter.get("field", "created_at")

                threshold_time = datetime.now() - timedelta(
                    days=time_filter.get("days", 0),
                    hours=time_filter.get("hours", 0),
                    minutes=time_filter.get("minutes", 0),
                    seconds=time_filter.get("seconds", 0)
                )
                query = query.where(field, ">=", threshold_time)
                

            docs = query.limit(config["limit"] * 5).stream()
            
        except google.api_core.exceptions.FailedPrecondition as e:
            if "The query requires an index" in str(e):
                print("\n⚠️ ERROR: This query requires a Firebase index to be created.")
                print("You can fix this in two ways:")
                print("1. Create the required index using the link below:")
                

                import re
                url_match = re.search(r'https://console\.firebase\.google\.com/[^\s]+', str(e))
                if url_match:
                    print(f"   {url_match.group(0)}")
                else:
                    print("   See the error message for the index creation link")
                
                print("\n2. As a temporary workaround, we'll run a simpler query and filter the results in memory.")
                print("   Note: This is less efficient for large collections.\n")
                

                query = db.collection(collection_name)
                

                equality_filters = config.get("equality_filters", {})
                if equality_filters:
                    field, value = next(iter(equality_filters.items()))
                    query = query.where(field, "==", value)
                

                docs = query.limit(config["limit"] * 10).stream()
            else:

                raise
            


        filtered_docs = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            data["_collection"] = collection_name
            

            if config.get("exclude_embeddings", False):
                data = filter_embeddings(data, True)
            

            field = config["time_filter"].get("field", "created_at")
            field = config["time_filter"].get("field", "created_at")
            doc_time = data.get(field)
            if config["time_filter"].get("enabled", False):
                threshold_time = datetime.now() - timedelta(
                    days=config["time_filter"].get("days", 0),
                    hours=config["time_filter"].get("hours", 0),
                    minutes=config["time_filter"].get("minutes", 0),
                    seconds=config["time_filter"].get("seconds", 0)
                )
                

                if doc_time and doc_time.tzinfo is not None:

                    doc_time = doc_time.replace(tzinfo=None)
                    

                if not doc_time or doc_time < threshold_time:
                    continue
            

            skip = False
            for field, value in config.get("equality_filters", {}).items():
                if data.get(field) != value:
                    skip = True
                    break
            if skip:
                continue
            

            if config["filter_type"] == "none" or not config["value"]:
                filtered_docs.append(data)
                continue
            

            matches = []
            search_value = config["value"].lower()
            for field in config["fields"]:

                if field not in data:
                    matches.append(False)
                    continue
                    

                field_value = str(data.get(field, "")).lower()
                

                if config["filter_type"] == "contains" and search_value in field_value:
                    matches.append(True)
                elif config["filter_type"] == "starts_with" and field_value.startswith(search_value):
                    matches.append(True)
                elif config["filter_type"] == "equals" and field_value == search_value:
                    matches.append(True)
                else:
                    matches.append(False)
            

            if config["match_type"] == "any" and any(matches):
                filtered_docs.append(data)
            elif config["match_type"] == "all" and all(matches) and matches:  # Ensure matches isn't empty
                filtered_docs.append(data)
        
        results.extend(filtered_docs)
    

    results.sort(key=lambda x: x.get("created_at", datetime.min), reverse=True)
    

    return results[:config["limit"]]

def display_results(results, config):
    """Display search results in the specified format"""
    if not results:
        print("No results found.")
        return

    if config["output"] == "json":

        serializable_results = []
        for doc in results:
            serializable_doc = {}
            for key, value in doc.items():
                if isinstance(value, datetime):
                    serializable_doc[key] = format_datetime(value)
                elif isinstance(value, (int, float, str, bool, list, dict)) or value is None:
                    serializable_doc[key] = value
                else:
                    serializable_doc[key] = str(value)
            serializable_results.append(serializable_doc)
        
        print(json.dumps(serializable_results, indent=2, ensure_ascii=False))
    
    elif config["output"] == "raw":
        for doc in results:
            print("-" * 40)
            for key, value in doc.items():
                print(f"{key}: {value}")
    
    else:  # table format

        by_collection = {}
        for doc in results:
            collection = doc.get("_collection", "unknown")
            if collection not in by_collection:
                by_collection[collection] = []
            by_collection[collection].append(doc)
        

        for collection, docs in by_collection.items():
            print(f"\n--- Collection: {collection} ---")
            

            fields = get_fields_to_display(collection)
            

            headers = fields
            rows = []
            for doc in docs:
                row = []
                for field in fields:
                    value = doc.get(field, "")
                    if isinstance(value, datetime):
                        value = format_datetime(value)
                    elif isinstance(value, (list, dict)):
                        value = str(value)
                    row.append(value)
                rows.append(row)
            

            print(tabulate(rows, headers=headers, tablefmt="grid"))
            print(f"Total: {len(docs)} documents")

def export_results(results, config):
    """Export search results to file in the specified format"""
    if not results:
        print("No results to export.")
        return False
    

    os.makedirs(config["export_path"], exist_ok=True)
    

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    search_term = config["value"].replace(" ", "_")[:20] if config["value"] else "all"
    collection = config["collection"]
    base_filename = f"{collection}_{search_term}_{timestamp}"
    

    serializable_results = []
    for doc in results:
        serializable_doc = {}
        for key, value in doc.items():

            if config.get("exclude_embeddings", False) and is_embedding_field(key, value):
                continue
                
            if isinstance(value, datetime):
                serializable_doc[key] = format_datetime(value)
            elif isinstance(value, (int, float, str, bool, list, dict)) or value is None:
                serializable_doc[key] = value
            else:
                serializable_doc[key] = str(value)
        serializable_results.append(serializable_doc)
    

    df = pd.DataFrame(serializable_results)
    
    filepath = ""
    if config["export"] == "csv":

        filepath = os.path.join(config["export_path"], f"{base_filename}.csv")
        df.to_csv(filepath, index=False, encoding='utf-8-sig')  # utf-8-sig for Excel compatibility
        
    elif config["export"] == "excel":

        filepath = os.path.join(config["export_path"], f"{base_filename}.xlsx")
        df.to_excel(filepath, index=False, engine='openpyxl')
        
    elif config["export"] == "json":

        filepath = os.path.join(config["export_path"], f"{base_filename}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(serializable_results, f, ensure_ascii=False, indent=2)
            
    elif config["export"] == "html":

        filepath = os.path.join(config["export_path"], f"{base_filename}.html")
        df.to_html(filepath, index=False)
    
    if filepath:
        print(f"✅ Results exported to: {os.path.abspath(filepath)}")
        return True
    else:
        return False

def interactive_config():
    """Get search configuration interactively"""
    config = DEFAULT_CONFIG.copy()
    print("\n=== Firebase Document Search ===")
    

    print("\nSelect collection to search:")
    print("1. news")
    print("2. neutral_news")
    print("3. all collections")
    choice = input("Enter choice (1-3) [default: 2]: ").strip() or "2"
    if choice == "1":
        config["collection"] = "news"
    elif choice == "2":
        config["collection"] = "neutral_news"
    elif choice == "3":
        config["collection"] = "all"
    

    all_available_fields = []
    if config["collection"] == "all":
        all_available_fields = list(set(get_all_searchable_fields("news") + get_all_searchable_fields("neutral_news")))
    else:
        all_available_fields = get_all_searchable_fields(config["collection"])
        

    all_available_fields.sort()
    

    all_available_fields.append("none")
    

    print("\nSelect fields to search in (comma-separated numbers):")
    for i, field in enumerate(all_available_fields):
        print(f"{i+1}. {field}")
    fields_choice = input(f"Enter choices (1-{len(all_available_fields)}, e.g., '1,3,5') [default: 1]: ").strip() or "1"
    
    selected_fields = []
    if "," in fields_choice:

        try:
            choices = [int(c.strip()) for c in fields_choice.split(",")]
            for choice in choices:
                if 1 <= choice <= len(all_available_fields):
                    field = all_available_fields[choice-1]
                    if field != "none":
                        selected_fields.append(field)
        except ValueError:
            selected_fields = [all_available_fields[0]]
    else:

        try:
            choice = int(fields_choice)
            if 1 <= choice <= len(all_available_fields):
                field = all_available_fields[choice-1]
                if field != "none":
                    selected_fields.append(field)
        except ValueError:
            selected_fields = [all_available_fields[0]]
    
    if not selected_fields:
        print("No valid fields selected. Using default field.")
        if config["collection"] == "news":
            selected_fields = ["title"]
        else:
            selected_fields = ["neutral_title"]
    
    config["fields"] = selected_fields
    
    if "none" in selected_fields:
        config["filter_type"] = "none"
    else:

        if len(selected_fields) > 1:
            print("\nSelect match type:")
            print("1. Match ANY field (OR)")
            print("2. Match ALL fields (AND)")
            match_choice = input("Enter choice (1-2) [default: 1]: ").strip() or "1"
            if match_choice == "1":
                config["match_type"] = "any"
            elif match_choice == "2":
                config["match_type"] = "all"
        

        print("\nSelect filter type:")
        print("1. contains")
        print("2. starts with")
        print("3. equals")
        print("4. no filter")
        
        filter_choice = input("Enter choice (1-4) [default: 1]: ").strip() or "1"
        if filter_choice == "1":
            config["filter_type"] = "contains"
        elif filter_choice == "2":
            config["filter_type"] = "starts_with"
        elif filter_choice == "3":
            config["filter_type"] = "equals"
        elif filter_choice == "4":
            config["filter_type"] = "none"
        

        if config["filter_type"] != "none":
            fields_str = ", ".join(config["fields"])
            config["value"] = input(f"\nEnter search value for {fields_str} {config['filter_type']}: ").strip()
    

    limit_input = input(f"\nMaximum results to display [default: {config['limit']}]: ").strip()
    if limit_input and limit_input.isdigit():
        config["limit"] = int(limit_input)
    

    print("\nSelect output format:")
    print("1. table (readable)")
    print("2. JSON")
    print("3. raw (all fields)")
    format_choice = input("Enter choice (1-3) [default: 1]: ").strip() or "1"
    if format_choice == "1":
        config["output"] = "table"
    elif format_choice == "2":
        config["output"] = "json"
    elif format_choice == "3":
        config["output"] = "raw"
    

    print("\nExport results to file?")
    print("1. No export (display only)")
    print("2. CSV file (Excel compatible)")
    print("3. Excel file (.xlsx)")
    print("4. JSON file")
    print("5. HTML file")
    
    export_choice = input("Enter choice (1-5) [default: 1]: ").strip() or "1"
    if export_choice == "1":
        config["export"] = None
    elif export_choice == "2":
        config["export"] = "csv"
    elif export_choice == "3":
        config["export"] = "excel"
    elif export_choice == "4":
        config["export"] = "json"
    elif export_choice == "5":
        config["export"] = "html"
    
    if config["export"]:
        default_path = "./results"
        export_path = input(f"Export directory [default: {default_path}]: ").strip() or default_path
        config["export_path"] = export_path
    

    print("\nAdd equality filters? (e.g., source_medium = 'expansion')")
    add_filters = input("Add filters? (y/n) [default: n]: ").strip().lower() == 'y'
    
    if add_filters:
        equality_filters = {}
        while True:

            available_fields = []
            if config["collection"] == "all":
                available_fields = list(set(get_all_searchable_fields("news") + get_all_searchable_fields("neutral_news")))
            else:
                available_fields = get_all_searchable_fields(config["collection"])
            
            print("\nAvailable fields for filtering:")
            for i, field in enumerate(available_fields):
                print(f"{i+1}. {field}")
            
            field_choice = input(f"Select field to filter by (1-{len(available_fields)}) or 'q' to quit: ").strip()
            
            if field_choice.lower() == 'q':
                break
            
            try:
                field_index = int(field_choice) - 1
                if 0 <= field_index < len(available_fields):
                    field = available_fields[field_index]
                    value = input(f"Enter value for {field} (exact match): ").strip()
                    equality_filters[field] = value
                    print(f"Added filter: {field} = '{value}'")
                else:
                    print("Invalid field selection.")
            except ValueError:
                print("Invalid input. Please enter a number.")
        
        config["equality_filters"] = equality_filters
    

    print("\nAdd time-based filter? (e.g., created in the last 3 days)")
    add_time_filter = input("Add time filter? (y/n) [default: n]: ").strip().lower() == 'y'
    
    if add_time_filter:
        time_filter = {"enabled": True}

        time_fields = ["created_at", "pub_date"] if config["collection"] == "news" else ["created_at"]
        print("\nSelect time field:")
        for i, field in enumerate(time_fields):
            print(f"{i+1}. {field}")
        
        field_choice = input(f"Select field (1-{len(time_fields)}) [default: 1]: ").strip() or "1"
        try:
            field_index = int(field_choice) - 1
            if 0 <= field_index < len(time_fields):
                time_filter["field"] = time_fields[field_index]
        except ValueError:
            time_filter["field"] = time_fields[0]
        

        print("\nEnter time threshold (how far back to search):")
        days = input("Days [default: 0]: ").strip() or "0"
        hours = input("Hours [default: 0]: ").strip() or "0"
        minutes = input("Minutes [default: 0]: ").strip() or "0"
        time_filter["days"] = int(days) if days.isdigit() else 0
        time_filter["hours"] = int(hours) if hours.isdigit() else 0
        time_filter["minutes"] = int(minutes) if minutes.isdigit() else 0
        
        time_description = []
        if time_filter["days"]: time_description.append(f"{time_filter['days']} days")
        if time_filter["hours"]: time_description.append(f"{time_filter['hours']} hours")
        if time_filter["minutes"]: time_description.append(f"{time_filter['minutes']} minutes")
        
        time_str = " and ".join(time_description) if time_description else "0 minutes"
        print(f"Added time filter: {time_filter['field']} within the last {time_str}")
        
        config["time_filter"] = time_filter
    

    print("\nExclude embedding fields from results? (can make outputs cleaner)")
    exclude_embeddings = input("Exclude embeddings? (y/n) [default: n]: ").strip().lower() == 'y'
    config["exclude_embeddings"] = exclude_embeddings

    return config

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Search Firebase documents")
    parser.add_argument("--collection", choices=["news", "neutral_news", "all"], 
                        default=DEFAULT_CONFIG["collection"], help="Collection to search in")
    parser.add_argument("--fields", default=",".join(DEFAULT_CONFIG["fields"]),
                        help="Fields to search in (comma-separated)")
    parser.add_argument("--match-type", choices=["any", "all"],
                        default=DEFAULT_CONFIG["match_type"], help="Match type for multi-field search")
    parser.add_argument("--filter-type", choices=["contains", "starts_with", "equals", "none"],
                        default=DEFAULT_CONFIG["filter_type"], help="Type of filter to apply")
    parser.add_argument("--value", default=DEFAULT_CONFIG["value"],
                        help="Search value")
    parser.add_argument("--limit", type=int, default=DEFAULT_CONFIG["limit"],
                        help="Maximum number of results to return")
    parser.add_argument("--output", choices=["table", "json", "raw"],
                        default=DEFAULT_CONFIG["output"], help="Output format")
    parser.add_argument("--export", choices=["csv", "excel", "json", "html"],
                        help="Export format")
    parser.add_argument("--export-path", default=DEFAULT_CONFIG["export_path"],
                        help="Directory path for exported files")
    parser.add_argument("--no-interactive", action="store_true",
                        help="Run in non-interactive mode")
    parser.add_argument("--equality-filter", action="append", 
                        help="Equality filter in format 'field:value' (can be used multiple times)")
    parser.add_argument("--time-field", 
                        help="Field to use for time filter (default: created_at)")
    parser.add_argument("--time-filter", 
                        help="Time filter in format 'days:X,hours:Y,minutes:Z'")
    parser.add_argument("--exclude-embeddings", action="store_true",
                        help="Exclude embedding fields from results")
    
    args = parser.parse_args()
    
    config = {
        "collection": args.collection,
        "fields": args.fields.split(",") if args.fields else DEFAULT_CONFIG["fields"],
        "match_type": args.match_type,
        "filter_type": args.filter_type,
        "value": args.value,
        "limit": args.limit,
        "output": args.output,
        "export": args.export,
        "export_path": args.export_path,
        "interactive": not args.no_interactive,
        "equality_filters": {},
        "time_filter": {"enabled": False},
        "exclude_embeddings": args.exclude_embeddings
    }
    

    if args.equality_filter:
        for filter_str in args.equality_filter:
            if ":" in filter_str:
                field, value = filter_str.split(":", 1)
                config["equality_filters"][field.strip()] = value.strip()
    

    if args.time_filter:
        time_filter_values = parse_time_filter(args.time_filter)
        if any(time_filter_values.values()):  # If any time values are non-zero
            config["time_filter"]["enabled"] = True
            config["time_filter"].update(time_filter_values)
            if args.time_field:
                config["time_filter"]["field"] = args.time_field
    
    return config

def main():
    """Main function"""

    try:
        import tabulate
    except ImportError:
        print("Installing tabulate package...")
        os.system("pip install tabulate")
        try:
            import tabulate
        except ImportError:
            print("Failed to install tabulate. Please install it manually: pip install tabulate")
            sys.exit(1)
    

    config = parse_args()
    

    if config["interactive"] and not config["value"] and config["filter_type"] != "none":
        config = interactive_config()
    

    print("\n=== Search Parameters ===")
    print(f"Collection: {config['collection']}")
    print(f"Fields: {', '.join(config['fields'])}")
    if len(config['fields']) > 1:
        print(f"Match Type: {config['match_type']} ({'OR' if config['match_type'] == 'any' else 'AND'})")
    print(f"Filter Type: {config['filter_type']}")
    print(f"Value: {config['value']}")
    print(f"Limit: {config['limit']}")
    print(f"Output: {config['output']}")
    if config["export"]:
        print(f"Export: {config['export']} ({config['export_path']})")
    if config.get("exclude_embeddings"):
        print("Embeddings: Excluded")
    print("="*25)
    

    equality_filters = config.get("equality_filters", {})
    if equality_filters:
        print("Equality Filters:")
        for field, value in equality_filters.items():
            print(f"  - {field} = '{value}'")
    print("="*25)
    

    time_filter = config.get("time_filter", {})
    if time_filter.get("enabled", False):
        time_description = []
        if time_filter["days"]: time_description.append(f"{time_filter['days']} days")
        if time_filter["hours"]: time_description.append(f"{time_filter['hours']} hours")
        if time_filter["minutes"]: time_description.append(f"{time_filter['minutes']} minutes")
        if time_filter["seconds"]: time_description.append(f"{time_filter['seconds']} seconds")
        time_str = " and ".join(time_description) if time_description else "0 minutes"
        print(f"Time Filter: {time_filter.get('field', 'created_at')} within the last {time_str}")
    

    results = search_documents(config)
    

    display_results(results, config)
    

    if config["export"]:
        export_results(results, config)
    

    print(f"\nFound {len(results)} documents.")

if __name__ == "__main__":
    main()