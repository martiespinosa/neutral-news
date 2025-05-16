from datetime import datetime, timedelta
from urllib.parse import urlparse, unquote
from .config import initialize_firebase
import traceback

def parse_pub_date(date_str):
    """
    Parse publication date from various formats into datetime object
    """
    if not date_str or not isinstance(date_str, str):
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
    
    print(f"Warning: Could not parse date string: {date_str}")
    return None

def store_news_in_firestore(news_list):
    """
    Store news items in Firestore database
    """
    if not news_list:
        print("No news to store")
        return 0
    
    db = initialize_firebase()
    batch = db.batch()
    news_count = 0
    current_batch = 0
    
    for news in news_list:
        # Check if this news already exists in the database by URL
        existing_news_query = db.collection('news').where('link', '==', news.link).limit(1)
        existing_news = [doc for doc in existing_news_query.stream()]
        
        if not existing_news:
            # Convert pub_date to proper datetime if it exists
            news_dict = news.to_dict()
            
            if 'pub_date' in news_dict and news_dict['pub_date']:
                pub_date_str = news_dict['pub_date']
                parsed_date = parse_pub_date(pub_date_str)
                if parsed_date:
                    news_dict['pub_date'] = parsed_date  # Firestore auto-converts datetime to Timestamp
                else:
                    # If parsing fails, use current time
                    news_dict['pub_date'] = datetime.now()
            
            # Create a new document in the 'news' collection
            news_ref = db.collection('news').document(news.id)
            batch.set(news_ref, news_dict)
            news_count += 1
            current_batch += 1
            
            # Firebase has a 500 operation limit per batch
            if current_batch >= 450:
                batch.commit()
                batch = db.batch()
                current_batch = 0
    
    # Final batch commit if there are pending operations
    if current_batch > 0:
        batch.commit()
    
    print(f"Saved {news_count} new news to Firestore")
    return news_count

def get_all_group_ids() -> set:
    """
    Get all unique group IDs from the 'neutral_news' collection in Firestore
    """
    db = initialize_firebase()
    groups_query = db.collection('neutral_news').select(['group'])
    groups_list = list(groups_query.stream())
    
    groups_ids = set()
    for doc in groups_list:
        data = doc.to_dict()
        if 'group' in data and data['group'] is not None:
            groups_ids.add(data['group'])
    
    print(f"Found {len(groups_ids)} unique group IDs")
    # Print them in a single line for debugging
    print(f"Group IDs: {', '.join(map(str, groups_ids))}")
    return groups_ids

def get_news_for_grouping() -> tuple:
    """
    Get news items for grouping process with improved reference selection

    Returns:
        tuple: (news_for_grouping, news_docs) - List of news items for grouping and dictionary of news documents
    """
    db = initialize_firebase()

    RECENT_GROUPS_HOURS = 48 # Number of hours to look back for recent groups
    REFERENCE_NEWS_HOURS = 48 # Number of hours to look back for reference news

    # Get recent unique group IDs
    recent_groups_time_threshold = datetime.now() - timedelta(hours=RECENT_GROUPS_HOURS)
    recent_groups = db.collection('neutral_news').where(
        'date', '>=', recent_groups_time_threshold
    )

    recent_groups_list = list(recent_groups.stream())
    recent_groups_ids = set()
    for doc in recent_groups_list:
        data = doc.to_dict()
        if 'group' in data and data['group'] is not None:
            recent_groups_ids.add(data['group'])
    print(f"Found {len(recent_groups_ids)} unique group IDs in the last {RECENT_GROUPS_HOURS} hours")

    # OPTIMIZED: Make a single query to get all news from the time period
    reference_groups_time_threshold = datetime.now() - timedelta(hours=REFERENCE_NEWS_HOURS)
    all_news_query = db.collection('news').where(
        'pub_date', '>=', reference_groups_time_threshold
    )
    
    all_news = list(all_news_query.stream())
    print(f"Fetched {len(all_news)} total news items from the last {REFERENCE_NEWS_HOURS} hours")

    # Filter news items programmatically
    ungrouped_news = []
    reference_news = []
    
    for doc in all_news:
        data = doc.to_dict()
        group = data.get('group')
        
        if group is None:
            ungrouped_news.append(doc)
        elif group in recent_groups_ids:
            reference_news.append(doc)

    print(f"Found {len(ungrouped_news)} ungrouped news items in the last {REFERENCE_NEWS_HOURS} hours")
    print(f"Found {len(reference_news)} reference news items from {len(recent_groups_ids)} groups")

    news_docs = {doc.id: doc for doc in ungrouped_news + reference_news}
    
    # Convert documents to processing format
    news_for_grouping = []
    
    for doc in news_docs.values():
        data = doc.to_dict()
        
        news_item = {
            "id": data["id"],
            "title": data["title"],
            "scraped_description": data["scraped_description"],
            "description": data["description"],
            "source_medium": data["source_medium"],
            "embedding": data["embedding"] if "embedding" in data else None,
        }
        
        # Add existing group if it has one
        if data.get("group") is not None:
            news_item["existing_group"] = data["group"]
        
        news_for_grouping.append(news_item)
    
    print(f"Got {len(ungrouped_news)} news to group and {len(reference_news)} reference news")
    return news_for_grouping, news_docs

def update_groups_in_firestore(groups_data: list, news_docs: dict) -> tuple:
    """
    Update group assignments in Firestore
    
    Args:
        groups_data: List of group objects
        news_docs: Dictionary of news documents keyed by ID
        
    Returns:
        tuple: (updated_count, created_count, updated_groups, created_groups) - Numbers and sets of groups
    """
    db = initialize_firebase()
    batch = db.batch()
    updated_count = 0
    created_count = 0
    current_batch = 0
    updated_groups = set()
    created_groups = set()

    for group_data in groups_data:
        group_id = group_data.get("group")
        sources = group_data.get("sources", [])
        
        if group_id is not None:
            group_id = int(float(group_id))
            
        # Process each news item in this group
        for source in sources:
            doc_id = source.get("id")
            
            if doc_id in news_docs:
                doc = news_docs[doc_id]
                doc_data = doc.to_dict()
                doc_ref = doc.reference
                
                # Get current group and check if it needs updating
                current_group = doc_data.get("group")
                
                # Only update if the group changed
                if current_group != group_id:
                    batch.update(doc_ref, {
                        "group": group_id
                        })
                    # Only add to either updated_groups OR created_groups, not both
                    if current_group is None:
                        # This is a new group assignment
                        created_count += 1
                        if group_id is not None:
                            created_groups.add(group_id)
                    else:
                        # This is updating an existing group
                        updated_count += 1
                        if group_id is not None:
                            updated_groups.add(group_id)
                        
                    current_batch += 1
                    
                    # Handle batch size limit
                    if current_batch >= 450:
                        batch.commit()
                        batch = db.batch()
                        current_batch = 0
    
    # Final batch commit if there are pending operations
    if current_batch > 0:
        batch.commit()
    
    return updated_count, created_count, updated_groups, created_groups

def update_news_with_neutral_scores(sources, neutralization_result, sources_to_unassign=None):
    """
    Actualiza las noticias originales con sus puntuaciones de neutralidad.
    """
    try:
        db = initialize_firebase()
        batch = db.batch()
        updated_count = 0
        updated_news_ids = set()
        
        # First, create a set of all source IDs that should be unassigned
        sources_to_unassign_set = set()
        if sources_to_unassign:
            for group_id, source_ids in sources_to_unassign.items():
                for source_id in source_ids:
                    sources_to_unassign_set.add(source_id)
        
        source_ratings = neutralization_result.get("source_ratings", [])
        for rating in source_ratings:
            source_medium = rating.get("source_medium")
            neutral_score = rating.get("rating")
            
            # Buscar las noticias correspondientes
            for source in sources:
                if source.get("source_medium") == source_medium:
                    news_id = source.get("id")
                    if news_id and news_id not in sources_to_unassign_set:
                        news_ref = db.collection('news').document(news_id)
                        doc = news_ref.get()
                        if doc.exists:
                            news_data = doc.to_dict()
                            if news_data:
                                # Solo actualizar si la puntuación es diferente
                                if news_data.get("neutral_score") != neutral_score:
                                    batch.update(news_ref, {"neutral_score": neutral_score, "updated_at": datetime.now()})
                                    updated_count += 1
                                    updated_news_ids.add(news_id)
        
        # Commit the batch
        if updated_count > 0:
            batch.commit()
        
        return updated_count, updated_news_ids
        
    except Exception as e:
        print(f"Error in update_news_with_neutral_scores: {str(e)}")
        return 0, set()
        
def load_all_news_links_from_medium(medium):
    """
    Carga todos los links de noticias de la colección 'news' en Firestore.
    It prints the time it took to load the links.
    """

    db = initialize_firebase()
    news_query = db.collection('news').where('source_medium', '==', medium)
    news_docs = list(news_query.stream())
    
    news_links = []
    for doc in news_docs:
        data = doc.to_dict()
        if data.get("link"):
            news_links.append(data["link"])
    
    return news_links

def ensure_standard_datetime(dt):
    """
    Convert Firebase DatetimeWithNanoseconds to standard Python datetime.
    This prevents errors with nanosecond precision when updating Firestore.
    """
    if dt is None:
        return datetime.now()
    
    # If it's already a standard datetime (not a Firebase datetime), return it
    if type(dt).__name__ == 'datetime':
        return dt
    
    # Convert Firebase DatetimeWithNanoseconds to standard datetime
    try:
        # Create a new standard datetime object with the same values
        return datetime(
            year=dt.year,
            month=dt.month,
            day=dt.day,
            hour=dt.hour,
            minute=dt.minute,
            second=dt.second,
            microsecond=dt.microsecond,
            tzinfo=dt.tzinfo
        )
    except Exception:
        # If conversion fails, return current time
        return datetime.now()

def store_neutral_news(group, neutralization_result, source_ids, sources_to_unassign=None):
    """
    Almacena el resultado de la neutralización en la colección neutral_news.
    También gestiona la eliminación de fuentes que necesitan ser desasignadas del grupo.
    
    Args:
        group: ID del grupo
        neutralization_result: Resultado de la neutralización
        source_ids: IDs de las fuentes
        sources_to_unassign: Diccionario con IDs de fuentes a desasignar del grupo
    """
    try:
        db = initialize_firebase()

        if group is not None:
            group = int(float(group))

        # Procesar las fuentes a desasignar primero
        group_str = str(group)
        if sources_to_unassign and group_str in sources_to_unassign:
            for source_id in sources_to_unassign[group_str]:
                if source_id in source_ids:
                    source_ids.remove(source_id)

        oldest_pub_date = get_oldest_pub_date(source_ids, db)
        # Convert to standard datetime to avoid nanosecond precision issues
        oldest_pub_date = ensure_standard_datetime(oldest_pub_date)

        image_url, image_medium = get_most_neutral_image(
            source_ids,  
            neutralization_result.get("source_ratings", [])
        )
        
        # Ensure all datetime objects are standard Python datetime
        current_time = ensure_standard_datetime(datetime.now())
        
        neutral_news_ref = db.collection('neutral_news').document(str(group))
        neutral_news_data = {
            "group": group,
            "neutral_title": neutralization_result.get("neutral_title"),
            "neutral_description": neutralization_result.get("neutral_description"),
            "category": neutralization_result.get("category"),
            "relevance": neutralization_result.get("relevance"),
            "created_at": current_time,
            "updated_at": current_time,
            "date": oldest_pub_date,
            "image_url": image_url,
            "image_medium": image_medium,
            "source_ids": source_ids,
        }

 
        # Update sources' groups
        for source_id in source_ids:
            news_ref = db.collection('news').document(source_id)
            news_snapshot = news_ref.get()  # Retrieve the document snapshot
            if news_snapshot.exists:  # Check if the document exists
                news_data = news_snapshot.to_dict()
                if news_data.get("group") != group:
                    # Update only if the group is different
                    news_ref.update({"group": group, "updated_at": datetime.now()})
        
        neutral_news_ref.set(neutral_news_data)
        return True
        
    except Exception as e:
        print(f"Error in store_neutral_news: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
def update_existing_neutral_news(group, neutralization_result, source_ids, sources_to_unassign=None):
    """
    Actualiza un documento existente de noticias neutrales en lugar de crear uno nuevo.
    """
    try:
        db = initialize_firebase()
        
        if group is not None:
            group = int(float(group))
            
        group_str = str(group)
        if sources_to_unassign and group_str in sources_to_unassign:
            for source_id in sources_to_unassign[group_str]:
                if source_id in source_ids:
                    source_ids.remove(source_id)
        
        # Initialize neutral_news_ref before any usage
        neutral_news_ref = db.collection('neutral_news').document(str(group))
        
        image_url, image_medium = get_most_neutral_image(
            source_ids, 
            neutralization_result.get("source_ratings", [])
        )
        
        oldest_pub_date = get_oldest_pub_date(source_ids, db)
        # Convert to standard datetime
        oldest_pub_date = ensure_standard_datetime(oldest_pub_date)
        
        # Ensure we're using a standard datetime object, not a DatetimeWithNanoseconds
        current_time = ensure_standard_datetime(datetime.now())
        
        # Actualizamos solo los campos necesarios, manteniendo otros metadatos
        neutral_news_data = {
            "neutral_title": neutralization_result.get("neutral_title"),
            "neutral_description": neutralization_result.get("neutral_description"),
            "category": neutralization_result.get("category"),
            "relevance": neutralization_result.get("relevance"),
            "updated_at": current_time,
            "source_ids": source_ids,
        }

        # Only add these fields if they are valid
        if isinstance(oldest_pub_date, datetime):
            neutral_news_data["date"] = oldest_pub_date
            
        if image_url:
            neutral_news_data["image_url"] = image_url
            
        if image_medium:
            neutral_news_data["image_medium"] = image_medium

        # Update sources' groups
        for source_id in source_ids:
            news_ref = db.collection('news').document(source_id)
            news_snapshot = news_ref.get()  # Retrieve the document snapshot
            if news_snapshot.exists:
                news_data = news_snapshot.to_dict()
                if news_data.get("group") != group:
                    # Update only if the group is different
                    news_ref.update({"group": group, "updated_at": datetime.now()})
        
        neutral_news_ref.update(neutral_news_data)
        return True
        
    except Exception as e:
        print(f"Error in update_existing_neutral_news: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
def get_most_neutral_image(source_ids, source_ratings):
    """
    Selecciona la imagen de la noticia más neutral que tenga imagen.
    
    Args:
        source_ids: Lista de IDs de las noticias fuente
        source_ratings: Lista de diccionarios con ratings de neutralidad por fuente
        
    Returns:
        Tuple of (image_url, source_medium) of the most neutral news with image,
        or (None, None) if no news has a valid image or an error occurs
    """
    try:
        db = initialize_firebase()
        
        # Obtener las noticias originales
        news_refs = [db.collection('news').document(news_id) for news_id in source_ids]
        news_docs = [ref.get() for ref in news_refs]
        
        # Extraer datos de las noticias
        news_data = []
        for doc in news_docs:
            if doc.exists:
                data = doc.to_dict()
                news_data.append({
                    "id": data.get("id"),
                    "source_medium": data.get("source_medium"),
                    "image_url": data.get("image_url"),
                    "neutral_score": None  # Lo llenaremos desde source_ratings
                })
        
        # Asignar puntuaciones de neutralidad a cada noticia
        for rating in source_ratings:
            source_medium = rating.get("source_medium")
            neutral_score = rating.get("rating")
            
            # Asignar la puntuación a la noticia correspondiente
            for news in news_data:
                if news["source_medium"] == source_medium:
                    news["neutral_score"] = neutral_score
        
        # Filtrar noticias que tienen imagen
        news_with_images = []
        for news in news_data:
            image_url = news.get("image_url")
            if image_url and is_valid_image_url(image_url):
                news_with_images.append(news)
        
        # Si no hay ninguna noticia con imagen, devolvemos (None, None)
        if not news_with_images:
            print("No news with images found in this group")
            return None, None
            
        # Ordenar por puntuación de neutralidad (mayor a menor)
        # Usamos 0 como valor predeterminado para manejar casos donde neutral_score es None
        news_with_images.sort(key=lambda x: x.get("neutral_score") or 0, reverse=True)
        
        # Tomar la URL de la imagen de la noticia más neutral
        selected_news = news_with_images[0]
        image_url = selected_news.get("image_url")
        image_medium = selected_news.get("source_medium")
        
        return image_url, image_medium
        
    except Exception as e:
        print(f"Error in get_most_neutral_image: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, None
        
    except Exception as e:
        print(f"Error in get_most_neutral_image: {str(e)}")
        import traceback
        traceback.print_exc()
        return None
    
def normalize_datetime(dt):
    """Convert datetime to naive (remove timezone info) if it has timezone info"""
    if dt is None:
        return datetime.now()
    
    # Handle Firebase DatetimeWithNanoseconds specifically
    dt_type = type(dt).__name__
    if dt_type == 'DatetimeWithNanoseconds':
        # Create a new standard datetime object without the nanosecond precision
        try:
            return datetime(
                year=dt.year,
                month=dt.month,
                day=dt.day,
                hour=dt.hour,
                minute=dt.minute,
                second=dt.second,
                microsecond=dt.microsecond,
                tzinfo=None  # Remove timezone info
            )
        except Exception:
            return datetime.now()
    
    if not isinstance(dt, datetime):
        return datetime.now()
    
    if dt.tzinfo is not None:
        # Convert to UTC then remove timezone info
        try:
            dt = dt.astimezone(tz=None).replace(tzinfo=None)
        except Exception:
            # If conversion fails, create a new naive datetime
            return datetime.now()
    
    return dt

def get_oldest_pub_date(source_ids, db):
    """
    Obtiene la fecha de publicación más antigua de una lista de IDs de noticias.
    Asume que pub_date es un datetime (Firestore Timestamp).
    Asegura que la fecha no sea más antigua que 3 días.
    """
    pub_dates = []
    cutoff_date = datetime.now() - timedelta(days=3)
    batch = db.batch()
    batch_count = 0

    def normalize_datetime(dt):
        """Convert datetime to naive (remove timezone info) if it has timezone info"""
        if dt is None:
            return datetime.now()
        
        # Handle Firebase DatetimeWithNanoseconds specifically
        dt_type = type(dt).__name__
        if dt_type == 'DatetimeWithNanoseconds':
            # Create a new standard datetime object without the nanosecond precision
            try:
                return datetime(
                    year=dt.year,
                    month=dt.month,
                    day=dt.day,
                    hour=dt.hour,
                    minute=dt.minute,
                    second=dt.second,
                    microsecond=dt.microsecond,
                    tzinfo=None  # Remove timezone info
                )
            except Exception:
                return datetime.now()
        
        if not isinstance(dt, datetime):
            return datetime.now()
        
        if dt.tzinfo is not None:
            # Convert to UTC then remove timezone info
            try:
                dt = dt.astimezone(tz=None).replace(tzinfo=None)
            except Exception:
                # If conversion fails, create a new naive datetime
                return datetime.now()
        
        return dt

    for news_id in source_ids:
        try:
            doc = db.collection("news").document(news_id).get()
            if doc.exists:
                data = doc.to_dict()
                pub_date = data.get("pub_date")
                created_at = data.get("created_at")

                # Convert to standard datetime object if needed
                if hasattr(pub_date, 'timestamp'):
                    try:
                        # Convert to standard datetime using timestamp
                        pub_date = datetime.fromtimestamp(pub_date.timestamp())
                    except (AttributeError, TypeError):
                        pub_date = None

                # Fallback to created_at if pub_date is missing or not a datetime
                if pub_date is None and created_at is not None:
                    if hasattr(created_at, 'timestamp'):
                        try:
                            created_at = datetime.fromtimestamp(created_at.timestamp())
                        except (AttributeError, TypeError):
                            created_at = None
                    pub_date = created_at

                # Normalize the datetime to ensure it's timezone-naive
                pub_date = normalize_datetime(pub_date)

                # If pub_date is older than cutoff, use created_at or now, and update Firestore
                if pub_date < cutoff_date:
                    fixed_date = normalize_datetime(datetime.now())
                    if isinstance(created_at, datetime):
                        fixed_date = normalize_datetime(created_at)
                    pub_dates.append(fixed_date)
                    
                    # Update Firestore if needed
                    try:
                        # Ensure we're using a standard Python datetime object for Firestore update
                        standard_fixed_date = datetime(
                            year=fixed_date.year,
                            month=fixed_date.month,
                            day=fixed_date.day,
                            hour=fixed_date.hour,
                            minute=fixed_date.minute,
                            second=fixed_date.second,
                            microsecond=fixed_date.microsecond
                        )
                        batch.update(doc.reference, {"pub_date": standard_fixed_date})
                        batch_count += 1
                        if batch_count >= 450:
                            batch.commit()
                            batch = db.batch()
                            batch_count = 0
                    except Exception as e:
                        print(f"Error updating pub_date for {news_id}: {str(e)}")
                        # Print traceback for debugging
                        traceback.print_exc()
                else:
                    pub_dates.append(pub_date)
        except Exception as e:
            print(f"Error processing document {news_id}: {str(e)}")
            traceback.print_exc()
            continue

    # Commit any remaining updates
    if batch_count > 0:
        try:
            batch.commit()
        except Exception as e:
            print(f"Error committing batch updates: {str(e)}")
            traceback.print_exc()

    # Make sure the default is also a normalized datetime
    if not pub_dates:
        return normalize_datetime(datetime.now())
    
    return min(pub_dates)

def delete_old_news(hours=72):
    """
    Delete news older than specified hours
    """
    db = initialize_firebase()
    time_threshold = datetime.now() - timedelta(hours=hours)
    
    # Query for news older than threshold
    old_news_query = db.collection('news').where('created_at', '<', time_threshold)
    
    # Get the documents
    old_news_docs = list(old_news_query.stream())
    
    # Create a batch for deletion
    batch = db.batch()
    deleted_count = 0
    
    for doc in old_news_docs:
        batch.delete(doc.reference)
        deleted_count += 1
        
        # Firebase has a limit of 500 operations per batch
        if deleted_count % 450 == 0:
            batch.commit()
            batch = db.batch()
    
    # Commit any remaining deletions
    if deleted_count % 450 != 0:
        batch.commit()
    
    print(f"Deleted {deleted_count} news items older than {hours} hours")
    return deleted_count


def is_valid_image_url(url):
    """
    Verifica si la URL corresponde a una imagen y no a un video.
    
    Args:
        url: URL del recurso a verificar
        
    Returns:
        Boolean: True si es una imagen válida, False si no
    """
    if not url:
        return False
    
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.tif', '.svg', '.ico', '.heic', '.heif', '.raw', '.cr2', '.nef', '.orf', '.sr2']
    video_extensions = ['.mp4', '.m4v', '.mov', '.wmv', '.avi', '.flv', '.webm', '.mkv', '.3gp', '.mpeg', '.mpg', '.mpe', '.mpv', '.m2v', '.mts', '.m2ts', '.ts']
    
    parsed_url = urlparse(url)
    path = unquote(parsed_url.path).lower()

    is_image = any(path.endswith(ext) for ext in image_extensions)
    is_video = any(path.endswith(ext) for ext in video_extensions)
    contains_video_pattern = 'video' in url.lower() or 'player' in url.lower()

    return is_image and not (is_video or contains_video_pattern)


def update_news_embedding(news_ids, embeddings):
    """
    Update the embeddings list of news items in smaller batches.
    """
    db = initialize_firebase()
    if len(news_ids) != len(embeddings):
        print("Error: Mismatch between number of news IDs and embeddings.")
        return 0

    updated_count = 0
    # Firestore batch limit is 500 operations.
    # Each update is one operation.
    # SIGNIFICANTLY REDUCE BATCH SIZE due to large embedding data
    batch_size = 50 # Start with a much smaller value, e.g., 50, 20, or even 10
                    # Experiment to find what works.

    for i in range(0, len(news_ids), batch_size):
        batch = db.batch()
        # Get the current slice of IDs and embeddings
        current_news_ids_batch = news_ids[i:i + batch_size]
        current_embeddings_batch = embeddings[i:i + batch_size]
        
        current_batch_operation_count = 0 # To track operations in this specific batch

        for news_id, embedding_list in zip(current_news_ids_batch, current_embeddings_batch):
            if not news_id: # Skip if news_id is None or empty
                print(f"Warning: Skipping update for empty news_id.")
                continue
            try:
                # Ensure embedding_list is not excessively large for a single document
                # (Firestore document limit is ~1MB)
                # If individual embeddings are too large, that's a separate issue.
                news_ref = db.collection('news').document(str(news_id)) # Ensure news_id is a string
                batch.update(news_ref, {'embedding': embedding_list})
                current_batch_operation_count +=1
            except Exception as e:
                print(f"Error preparing update for news_id {news_id}: {e}")
                # Optionally, decide if you want to skip this item or halt the batch

        if current_batch_operation_count > 0: # Only commit if there are operations in the batch
            try:
                batch.commit()
                updated_count += current_batch_operation_count 
                print(f"Successfully committed batch of {current_batch_operation_count} embedding updates. Total updated: {updated_count}")
            except Exception as e:
                print(f"Error committing batch (size {current_batch_operation_count}): {e}")
                # Handle commit error, e.g., log it, retry individual items, or raise
                # For simplicity, we're just printing here.
                # You might want to add more sophisticated error handling or retry logic.
        else:
            print("Skipping commit for an empty batch.")
            
    return updated_count

def get_group_item_count(group_id):
    """
    Get the count of news items assigned to a specific group in Firestore
    
    Args:
        group_id: The group ID to count items for
        
    Returns:
        int: The number of news items in the specified group
    """
    try:
        db = initialize_firebase()
        news_ref = db.collection('news')
        
        # Query for documents with this group ID and count them
        query = news_ref.where('group', '==', group_id)
        count = len(list(query.stream()))
        
        return count
    except Exception as e:
        print(f"Error counting items in group {group_id}: {str(e)}")
        return 0

def get_group_items(group_id):
    """
    Get all news items assigned to a specific group from Firestore
    
    Args:
        group_id: The group ID to get items for
        
    Returns:
        list: List of dictionaries containing news items
    """
    try:
        db = initialize_firebase()
        news_ref = db.collection('news')
        
        # Query for documents with this group ID
        query = news_ref.where('group', '==', group_id)
        docs = list(query.stream())
        
        # Convert to list of dictionaries with embeddings
        items = []
        for doc in docs:
            item = doc.to_dict()
            item['id'] = doc.id
            items.append(item)
            
        return items
    except Exception as e:
        print(f"Error retrieving items in group {group_id}: {str(e)}")
        return []