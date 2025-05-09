from datetime import datetime, timedelta
from urllib.parse import urlparse, unquote
from .config import initialize_firebase

def store_news_in_firestore(news_list):
    """
    Store news items in Firestore database
    """
    db = initialize_firebase()
    batch = db.batch()
    news_count = 0
    current_batch = 0
    
    for news in news_list:
        # Check if this news already exists in the database by URL
        existing_news_query = db.collection('news').where('link', '==', news.link).limit(1)
        existing_news = [doc for doc in existing_news_query.stream()]
        
        if not existing_news:
            # Create a new document in the 'news' collection
            news_ref = db.collection('news').document(news.id)
            batch.set(news_ref, news.to_dict())
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

def get_news_for_grouping():
    """
    Get news items for grouping process
    """
    db = initialize_firebase()
    time_threshold = datetime.now() - timedelta(hours=24)
    
    # 1. Obtener noticias sin grupo (candidatas a ser agrupadas)
    # Change from filter to where
    ungrouped_query = db.collection('news').where('group', '==', None)
    ungrouped_news = list(ungrouped_query.stream())
    
    # 2. Obtener noticias recientes CON grupo (servirán como referencia)
    # Change from filter to where
    recent_grouped_query = db.collection('news').where(
        'created_at', '>=', time_threshold
    ).where(
        'group', '!=', None
    )
    recent_grouped_news = list(recent_grouped_query.stream())
    
    # Preparar diccionario para todos los documentos
    all_docs = {doc.id: doc for doc in ungrouped_news + recent_grouped_news}
    
    # 3. Convertir documentos al formato de procesamiento
    combined_news = []
    
    for doc in all_docs.values():
        data = doc.to_dict()
        
        # Use scraped_description if available, otherwise fall back to description
        description_text = ""
        if "scraped_description" in data:
            description_text = data["scraped_description"]
        elif "description" in data:
            description_text = data["description"]
        else:
            continue  # Skip if neither field is present
        
        news_item = {
            "id": data["id"],
            "title": data["title"],
            "scraped_description": description_text,
            "source_medium": data["source_medium"],
            "embedding": data["embedding"] if "embedding" in data else None,
        }
        
        # Añadir grupo existente si lo tiene
        if data.get("group") is not None:
            news_item["existing_group"] = data["group"]
        
        combined_news.append(news_item)
    
    print(f"Got {len(ungrouped_news)} news to group and {len(recent_grouped_news)} reference news")
    return combined_news, all_docs

def update_groups_in_firestore(grouped_news, news_docs):
    """
    Update group assignments in Firestore
    """
    db = initialize_firebase()
    batch = db.batch()
    updated_count = 0
    current_batch = 0
        
    for item in grouped_news:
        doc_id = item["id"]
        
        if doc_id in news_docs:
            doc = news_docs[doc_id]
            doc_data = doc.to_dict()
            doc_ref = doc.reference
            
            # Solo actualizar si la noticia no tenía grupo o si el grupo ha cambiado
            current_group = doc_data.get("group")
            new_group = item.get("group")
            
            # Convertir a entero si no es None
            if new_group is not None:
                new_group = int(float(new_group))
                
            # Solo actualizar si es necesario
            if current_group != new_group:                
                batch.update(doc_ref, {"group": new_group})
                updated_count += 1
                current_batch += 1
                
                # Firebase has a 500 operation limit per batch
                if current_batch >= 450:
                    batch.commit()
                    batch = db.batch()
                    current_batch = 0
    
    # Final batch commit if there are pending operations
    if current_batch > 0:
        batch.commit()
    
    return updated_count

def update_news_with_neutral_scores(sources, neutralization_result):
    """
    Actualiza las noticias originales con sus puntuaciones de neutralidad.
    """
    try:
        db = initialize_firebase()
        batch = db.batch()
        updated_count = 0
        
        source_ratings = neutralization_result.get("source_ratings", [])
        for rating in source_ratings:
            source_medium = rating.get("source_medium")
            neutral_score = rating.get("rating")
            
            # Buscar las noticias correspondientes
            for source in sources:
                if source.get("source_medium") == source_medium:
                    news_id = source.get("id")
                    if news_id:
                        news_ref = db.collection('news').document(news_id)
                        batch.update(news_ref, {"neutral_score": neutral_score})
                        updated_count += 1
        
        # Commit the batch
        if updated_count > 0:
            batch.commit()
        
        return updated_count
        
    except Exception as e:
        print(f"Error in update_news_with_neutral_scores: {str(e)}")
        return 0

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

def store_neutral_news(group, neutralization_result, source_ids):
    """
    Almacena el resultado de la neutralización en la colección neutral_news.
    """
    try:
        db = initialize_firebase()

        if group is not None:
            group = int(float(group))

        oldest_pub_date = get_oldest_pub_date(source_ids, db)

        image_url, image_medium = get_most_neutral_image(
            source_ids, 
            neutralization_result.get("source_ratings", [])
        )
        
        neutral_news_ref = db.collection('neutral_news').document(str(group))
        neutral_news_data = {
            "group": group,
            "neutral_title": neutralization_result.get("neutral_title"),
            "neutral_description": neutralization_result.get("neutral_description"),
            "category": neutralization_result.get("category"),
            "relevance": neutralization_result.get("relevance"),
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "date": oldest_pub_date,
            "image_url": image_url,
            "image_medium": image_medium,
            "source_ids": source_ids,
        }
        
        neutral_news_ref.set(neutral_news_data)
        return True
        
    except Exception as e:
        print(f"Error in store_neutral_news: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
def update_existing_neutral_news(group, neutralization_result, source_ids):
    """
    Actualiza un documento existente de noticias neutrales en lugar de crear uno nuevo.
    """
    try:
        db = initialize_firebase()
        
        if group is not None:
            group = int(float(group))

        image_url, image_medium = get_most_neutral_image(
            source_ids, 
            neutralization_result.get("source_ratings", [])
        )
        
        neutral_news_ref = db.collection('neutral_news').document(str(group))
        
        # Actualizamos solo los campos necesarios, manteniendo otros metadatos
        neutral_news_data = {
            "neutral_title": neutralization_result.get("neutral_title"),
            "neutral_description": neutralization_result.get("neutral_description"),
            "category": neutralization_result.get("category"),
            "relevance": neutralization_result.get("relevance"),
            "updated_at": datetime.now(),
            "image_url": image_url,
            "image_medium": image_medium,
            "source_ids": source_ids,
        }

        if image_url:
            neutral_news_data["image_url"] = image_url
        
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
    
def get_oldest_pub_date(source_ids, db):
    """
    Obtiene la fecha de publicación más antigua de una lista de IDs de noticias.
    Maneja múltiples formatos de fecha comunes en feeds RSS.
    """
    pub_dates = []
    
    # Lista de formatos de fecha posibles
    date_formats = [
        "%a, %d %b %Y %H:%M:%S %z",     # Sat, 03 May 2025 18:07:56 +0200
        "%d %b %Y %H:%M:%S %z",         # 03 May 2025 13:09:49 +0200
        "%Y-%m-%dT%H:%M:%S%z",          # 2025-05-03T18:07:56+0200
        "%Y-%m-%d %H:%M:%S%z",          # 2025-05-03 18:07:56+0200
        "%a, %d %b %Y %H:%M:%S",        # Sin zona horaria
        "%d %b %Y %H:%M:%S",            # Sin zona horaria
        "%Y-%m-%dT%H:%M:%S",            # ISO sin zona horaria
        "%Y-%m-%d %H:%M:%S"             # Sin zona horaria
    ]

    for news_id in source_ids:
        doc = db.collection("news").document(news_id).get()
        if doc.exists:
            data = doc.to_dict()
            pub_date_str = data.get("pub_date")
            
            if pub_date_str:
                parsed = False
                
                for date_format in date_formats:
                    try:
                        cleaned_date_str = pub_date_str
                        if "+0000" not in pub_date_str and "-0000" not in pub_date_str:
                            for tz in [" GMT", " UTC", " UT", " Z"]:
                                if pub_date_str.endswith(tz):
                                    cleaned_date_str = pub_date_str.replace(tz, " +0000")
                                    break
                        
                        pub_date = datetime.strptime(cleaned_date_str, date_format)
                        pub_dates.append(pub_date)
                        parsed = True
                        break
                    except ValueError:
                        continue
                
                if not parsed:
                    print(f"No se pudo parsear la fecha: {pub_date_str}")
    
    return min(pub_dates) if pub_dates else datetime.now()

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
def get_all_embeddings():
    """
    Get all embeddings from the 'news' collection
    """
    db = initialize_firebase()
    
    # Query for all news items
    all_news_query = db.collection('news')
    
    # Get the documents
    all_news_docs = list(all_news_query.stream())
    
    # Convert to a list of dictionaries
    all_news = [doc.to_dict() for doc in all_news_docs]
    
    # Extract embeddings
    embeddings = [news.get("embedding") for news in all_news if news.get("embedding") is not None]
    
    return embeddings
