import json
from firebase_functions import https_fn
from src.parsers import parse_xml
from src.process import process_news_groups
from src.grouping import agrupar_noticias
from src.storage import store_news_in_firestore, update_groups_in_firestore
import traceback
import requests
from src.models import Media

def fetch_all_rss():
    all_news = []
    
    # Get news for each medium
    for medium in Media.get_all():
        press_media = Media.get_press_media(medium)
        if not press_media:
            print(f"Invalid medium: {medium}")
            continue
        
        try:
            print(f"Loading RSS for {press_media.name}...")
            response = requests.get(press_media.link)
            response.raise_for_status()  # Throw exception if HTTP error
            
            # Parse XML and get news
            medium_news = parse_xml(response.text, medium)
            all_news.extend(medium_news)
            print(f"Parsed {len(medium_news)} news for {press_media.name}")
        except Exception as e:
            print(f"Error loading RSS for {press_media.name}: {str(e)}")
            traceback.print_exc()
    
    return all_news

@https_fn.on_request(timeout_sec=300, memory=4096)
def news_api(req: https_fn.Request) -> https_fn.Response:
    """
    HTTP function that handles various news-related operations:
    - GET /news_api: General information about the API
    - GET /news_api?action=group: Group existing news
    - GET /news_api?action=fetch: Get new RSS news
    - POST /news_api: Receives a list of news, groups them and returns the groups
    """
    try:
        # Check if it's a GET request
        if req.method == 'GET':
            action = req.args.get('action', '')
            
            if action == 'group':
                # Execute manual grouping
                print("Starting manual news grouping...")
                updated_count = process_news_groups()
                return https_fn.Response(
                    json.dumps({
                        "status": "success",
                        "groups_updated": updated_count
                    }, ensure_ascii=False),
                    content_type="application/json"
                )
            
            elif action == 'fetch':
                # Execute manual RSS loading
                print("Starting manual RSS loading...")
                all_news = fetch_all_rss()
                stored_count = store_news_in_firestore(all_news) if all_news else 0
                updated_count = process_news_groups()
                return https_fn.Response(
                    json.dumps({
                        "status": "success",
                        "news_fetched": len(all_news),
                        "news_stored": stored_count,
                        "groups_updated": updated_count
                    }, ensure_ascii=False),
                    content_type="application/json"
                )
            
            else:
                # General information about the API
                return https_fn.Response(
                    json.dumps({
                        "message": "News API operational.",
                        "endpoints": {
                            "GET /news_api": "Shows this information",
                            "GET /news_api?action=group": "Groups existing news in Firestore",
                            "GET /news_api?action=fetch": "Gets new news from RSS feeds and groups them",
                            "POST /news_api": "Groups news sent in the request body"
                        },
                        "post_format": [
                            {"id": "news-id-1", "titulo": "News title 1", "cuerpo": "News body 1"}, 
                            {"id": "news-id-2", "titulo": "News title 2", "cuerpo": "News body 2"}
                        ]
                    }, ensure_ascii=False),
                    content_type="application/json"
                )
        
        # If it's a POST request, process the sent news
        elif req.method == 'POST':
            try:
                noticias = req.get_json()
            except Exception as e:
                return https_fn.Response(
                    json.dumps({"error": f"Error processing JSON: {str(e)}"}, ensure_ascii=False),
                    status=400,
                    content_type="application/json"
                )
            
            if noticias is None:
                return https_fn.Response(
                    json.dumps({"error": "No news received. The body must be a JSON array."}, ensure_ascii=False),
                    status=400,
                    content_type="application/json"
                )
            
            if not isinstance(noticias, list):
                return https_fn.Response(
                    json.dumps({"error": "The received format is not valid. An array of news is expected."}, ensure_ascii=False),
                    status=400,
                    content_type="application/json"
                )
            
            # Validate length to avoid memory issues
            if len(noticias) > 500:
                return https_fn.Response(
                    json.dumps({"error": "The maximum number of news allowed is 500."}, ensure_ascii=False),
                    status=400,
                    content_type="application/json"
                )
            
            # Call the function to group the news directly
            print(f"ℹ️ Processing {len(noticias)} news sent via POST...")
            noticias_agrupadas = agrupar_noticias(noticias)
            
            # Return the grouped news as a response
            return https_fn.Response(
                json.dumps(noticias_agrupadas, ensure_ascii=False, indent=2),
                content_type="application/json",
                status=200
            )
        
        else:
            return https_fn.Response(
                json.dumps({"error": "HTTP method not supported"}, ensure_ascii=False),
                status=405,
                content_type="application/json"
            )
    
    except Exception as e:
        error_message = f"Error: {str(e)}"
        print(f"❌ Error in news_api: {error_message}")
        traceback.print_exc()
        return https_fn.Response(
            json.dumps({"error": error_message}, ensure_ascii=False),
            status=500,
            content_type="application/json"
        )