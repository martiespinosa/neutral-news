from datetime import datetime, timedelta
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
    ungrouped_query = db.collection('news').where('group', '==', None)
    ungrouped_news = list(ungrouped_query.stream())
    
    # 2. Obtener noticias recientes CON grupo (servirán como referencia)
    recent_grouped_query = db.collection('news').where('created_at', '>=', time_threshold).where('group', '!=', None)
    recent_grouped_news = list(recent_grouped_query.stream())
    
    # Preparar diccionario para todos los documentos
    all_docs = {doc.id: doc for doc in ungrouped_news + recent_grouped_news}
    
    # 3. Convertir documentos al formato de procesamiento
    combined_news = []
    
    for doc in all_docs.values():
        data = doc.to_dict()
        news_item = {
            "id": data["id"],
            "title": data["title"],
            "description": data["description"],
            "source_medium": data["sourceMedium"]
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
            new_group = item.get("group_number")
            
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

def store_neutral_news(group_number, neutralization_result, source_ids):
    """
    Almacena el resultado de la neutralización en la colección neutral_news.
    """
    try:
        db = initialize_firebase()

        if group_number is not None:
            group_number = int(float(group_number))
        
        neutral_news_ref = db.collection('neutral_news').document(str(group_number))
        neutral_news_data = {
            "group_number": group_number,
            "neutral_title": neutralization_result.get("neutral_title"),
            "neutral_description": neutralization_result.get("neutral_description"),
            "category": neutralization_result.get("category"),
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "source_ids": source_ids,
        }
        
        neutral_news_ref.set(neutral_news_data)
        print(f"Stored neutral news for group {group_number}")
        return True
        
    except Exception as e:
        print(f"Error in store_neutral_news: {str(e)}")
        return False
    
def update_existing_neutral_news(group_number, neutralization_result, source_ids):
    """
    Actualiza un documento existente de noticias neutrales en lugar de crear uno nuevo.
    """
    try:
        db = initialize_firebase()
        
        if group_number is not None:
            group_number = int(float(group_number))
        
        neutral_news_ref = db.collection('neutral_news').document(str(group_number))
        
        # Actualizamos solo los campos necesarios, manteniendo otros metadatos
        neutral_news_data = {
            "neutral_title": neutralization_result.get("neutral_title"),
            "neutral_description": neutralization_result.get("neutral_description"),
            "category": neutralization_result.get("category"),
            "updated_at": datetime.now(),
            "source_ids": source_ids,
        }
        
        neutral_news_ref.update(neutral_news_data)
        print(f"Updated existing neutral news for group {group_number}")
        return True
        
    except Exception as e:
        print(f"Error in update_existing_neutral_news: {str(e)}")
        return False

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
