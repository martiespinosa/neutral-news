import firebase_admin
from firebase_admin import credentials, firestore
import os
import argparse
import sys
import importlib
import csv
from datetime import datetime
import time

"""SAMPLE: 
python select_news.py --collection news `
  --fields description,scraped_description,title `
  --match-type any `
  --filter-type contains `
  --value lautaro `
  --limit 1000 `
  --output json `
  --export csv `
  --export-path "./results" `
  --no-interactive
"""

# Check for required packages
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

# Ruta al archivo JSON de tu cuenta de servicio - Relative path from script location
SERVICE_ACCOUNT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../neutralnews-ca548-firebase-adminsdk-fbsvc-b2a2b9fa03.json'))

# Configuration - Edit these values if not using command line arguments
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

# Field types - helps determine which fields can be searched with contains/starts_with
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
    if collection_name == "news":
        return ["id", "title", "source_medium", "created_at", "group"]
    elif collection_name == "neutral_news":
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
        
        # We don't apply filters in the Firestore query since we're doing complex multi-field searching
        # Instead, we'll fetch documents and filter in memory
            
        # Execute query and get documents
        docs = query.limit(config["limit"] * 5).stream()  # Fetch more docs since we'll filter in memory
        
        # Post-process for our complex filter operations
        filtered_docs = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            data["_collection"] = collection_name
            
            # Skip filtering if no filter is specified
            if config["filter_type"] == "none" or not config["value"]:
                filtered_docs.append(data)
                continue
            
            # Apply complex multi-field filtering
            matches = []
            search_value = config["value"].lower()
            
            for field in config["fields"]:
                # Skip fields that don't exist in this document
                if field not in data:
                    matches.append(False)
                    continue
                    
                # Convert field value to string for comparison
                field_value = str(data.get(field, "")).lower()
                
                # Apply the appropriate filter type
                if config["filter_type"] == "contains" and search_value in field_value:
                    matches.append(True)
                elif config["filter_type"] == "starts_with" and field_value.startswith(search_value):
                    matches.append(True)
                elif config["filter_type"] == "equals" and field_value == search_value:
                    matches.append(True)
                else:
                    matches.append(False)
            
            # Check if the document matches based on the match type
            if config["match_type"] == "any" and any(matches):
                filtered_docs.append(data)
            elif config["match_type"] == "all" and all(matches) and matches:  # Ensure matches isn't empty
                filtered_docs.append(data)
        
        results.extend(filtered_docs)
    
    # Sort results by created_at (newest first)
    results.sort(key=lambda x: x.get("created_at", datetime.min), reverse=True)
    
    # Limit overall results
    return results[:config["limit"]]

def display_results(results, config):
    """Display search results in the specified format"""
    if not results:
        print("No results found.")
        return

    if config["output"] == "json":
        # Convert any non-serializable objects (like datetimes)
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
        # Group by collection
        by_collection = {}
        for doc in results:
            collection = doc.get("_collection", "unknown")
            if collection not in by_collection:
                by_collection[collection] = []
            by_collection[collection].append(doc)
        
        # Display each collection separately
        for collection, docs in by_collection.items():
            print(f"\n--- Collection: {collection} ---")
            
            # Get fields to display
            fields = get_fields_to_display(collection)
            
            # Prepare table data
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
            
            # Display table
            print(tabulate(rows, headers=headers, tablefmt="grid"))
            print(f"Total: {len(docs)} documents")

def export_results(results, config):
    """Export search results to file in the specified format"""
    if not results:
        print("No results to export.")
        return False
    
    # Ensure export directory exists
    os.makedirs(config["export_path"], exist_ok=True)
    
    # Generate a filename based on search parameters
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    search_term = config["value"].replace(" ", "_")[:20] if config["value"] else "all"
    collection = config["collection"]
    base_filename = f"{collection}_{search_term}_{timestamp}"
    
    # Convert results to a common format for export
    # Convert any non-serializable objects (like datetimes)
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
    
    # Create a DataFrame for easy export
    df = pd.DataFrame(serializable_results)
    
    filepath = ""
    
    if config["export"] == "csv":
        # Export to CSV
        filepath = os.path.join(config["export_path"], f"{base_filename}.csv")
        df.to_csv(filepath, index=False, encoding='utf-8-sig')  # utf-8-sig for Excel compatibility
        
    elif config["export"] == "excel":
        # Export to Excel
        filepath = os.path.join(config["export_path"], f"{base_filename}.xlsx")
        df.to_excel(filepath, index=False, engine='openpyxl')
        
    elif config["export"] == "json":
        # Export to JSON
        filepath = os.path.join(config["export_path"], f"{base_filename}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(serializable_results, f, ensure_ascii=False, indent=2)
            
    elif config["export"] == "html":
        # Export to HTML
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
    
    # Collection
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
    
    # Determine available fields based on collection
    all_available_fields = []
    
    if config["collection"] == "all":
        all_available_fields = list(set(get_all_searchable_fields("news") + get_all_searchable_fields("neutral_news")))
    else:
        all_available_fields = get_all_searchable_fields(config["collection"])
    
    # Sort fields alphabetically for easier finding
    all_available_fields.sort()
    
    # Add "none" as the last option
    all_available_fields.append("none")
    
    # Fields to search in (multiple selection)
    print("\nSelect fields to search in (comma-separated numbers):")
    for i, field in enumerate(all_available_fields):
        print(f"{i+1}. {field}")
    
    fields_choice = input(f"Enter choices (1-{len(all_available_fields)}, e.g., '1,3,5') [default: 1]: ").strip() or "1"
    
    selected_fields = []
    if "," in fields_choice:
        # Multiple field selection
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
        # Single field selection
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
        # Match type (for multi-field searches)
        if len(selected_fields) > 1:
            print("\nSelect match type:")
            print("1. Match ANY field (OR)")
            print("2. Match ALL fields (AND)")
            
            match_choice = input("Enter choice (1-2) [default: 1]: ").strip() or "1"
            
            if match_choice == "1":
                config["match_type"] = "any"
            elif match_choice == "2":
                config["match_type"] = "all"
        
        # Filter type
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
            
        # Search value
        if config["filter_type"] != "none":
            fields_str = ", ".join(config["fields"])
            config["value"] = input(f"\nEnter search value for {fields_str} {config['filter_type']}: ").strip()
    
    # Limit
    limit_input = input(f"\nMaximum results to display [default: {config['limit']}]: ").strip()
    if limit_input and limit_input.isdigit():
        config["limit"] = int(limit_input)
    
    # Output format
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
    
    # Export options
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
                        help="Maximum results to return")
    
    parser.add_argument("--output", choices=["table", "json", "raw"],
                        default=DEFAULT_CONFIG["output"], help="Output format")
    
    parser.add_argument("--export", choices=["csv", "excel", "json", "html"],
                        help="Export results to file format")
    
    parser.add_argument("--export-path", default=DEFAULT_CONFIG["export_path"],
                        help="Directory path for exported files")
    
    parser.add_argument("--no-interactive", action="store_true",
                        help="Run in non-interactive mode")
    
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
        "interactive": not args.no_interactive
    }
    
    return config

def main():
    """Main function"""
    # Check if tabulate is installed
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
    
    # Get configuration
    config = parse_args()
    
    # If interactive mode is enabled and no value is provided, get input interactively
    if config["interactive"] and not config["value"] and config["filter_type"] != "none":
        config = interactive_config()
    
    # Print search parameters
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
    print("="*25)
    
    # Perform search
    results = search_documents(config)
    
    # Display results
    display_results(results, config)
    
    # Export results if specified
    if config["export"]:
        export_results(results, config)
    
    # Summary
    print(f"\nFound {len(results)} documents.")

if __name__ == "__main__":
    main()