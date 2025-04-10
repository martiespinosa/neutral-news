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
            "titulo": data["title"],
            "cuerpo": data["description"],
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
                new_group = int(new_group)
                
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
    
    print(f"Actualizados grupos para {updated_count} noticias en Firestore")
    return updated_count

def store_neutralized_groups(grouped_news, news_docs):
    """
    Store neutralized news groups in Firestore
    """
    db = initialize_firebase()
    batch = db.batch()
    neutralized_count = 0
    current_batch = 0
    
    groups = {}
    for item in grouped_news:
        group_num = item["group_number"]
        if group_num is not None:
            if group_num not in groups:
                groups[group_num] = []
            groups[group_num].append(item["id"])
    
    for group_num, news_ids in groups.items():
        if len(news_ids) < 2:
            continue
        
        titles = []
        descriptions = []
        for news_id in news_ids:
            if news_id in news_docs:
                doc_data = news_docs[news_id].to_dict()
                titles.append(doc_data["title"])
                descriptions.append(doc_data["description"])
        
        from .neutralization import neutralize_texts
        neutral_title = neutralize_texts(titles, "título")
        neutral_desc = neutralize_texts(descriptions, "descripción")
        
        group_ref = db.collection('neutralized_groups').document(str(group_num))
        group_data = {
            "group_number": int(group_num),
            "news_ids": news_ids,
            "neutral_title": neutral_title,
            "neutral_description": neutral_desc,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        batch.set(group_ref, group_data, merge=True)
        neutralized_count += 1
        current_batch += 1
        
        if current_batch >= 450:
            batch.commit()
            batch = db.batch()
            current_batch = 0
    
    if current_batch > 0:
        batch.commit()
    
    print(f"Neutralized and stored {neutralized_count} groups in Firestore")
    return neutralized_count

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