from openai import OpenAI
import os, json

from src.storage import store_neutral_news, update_news_with_neutral_scores, update_existing_neutral_news
from .config import initialize_firebase

def neutralize_and_more(news_groups, batch_size=5):
    """
    Coordina el proceso de neutralización de grupos de noticias y actualiza Firestore.
    Procesa los grupos en batches para optimizar las llamadas a la API.
    """
    if not news_groups:
        print("No news groups to neutralize")
        return 0
    
    db = initialize_firebase()
    
    try:
        # Filtrar grupos que necesitan neutralización
        groups_to_neutralize = []
        groups_to_update = []
        
        unchanged_group_count = 0
        changed_group_count = 0
        unchanged_group_ids = []
        changed_group_ids = []
        
        print(f"ℹ️ Processing {len(news_groups)} news groups for neutralization")
        for group in news_groups:   
            group_number = group.get('group')
            if group_number is not None:
            # Normalizar a entero
                group_number = int(float(group_number))
                group['group'] = group_number

            sources = group.get('sources', [])
            
            if not group or not sources or len(sources) < 2:
                continue
                
            # Extraer los IDs de las noticias actuales
            current_source_ids = [source.get('id') for source in sources if source.get('id')]
            current_source_ids.sort()  # Ordenar para comparación consistente
            
            # Verificar si ya existe una neutralización para este grupo
            neutral_doc_ref = db.collection('neutral_news').document(str(group_number))
            neutral_doc = neutral_doc_ref.get()
            
            if neutral_doc.exists:
                # El grupo ya tiene una neutralización, verificar si ha cambiado
                existing_data = neutral_doc.to_dict()
                existing_source_ids = existing_data.get('source_ids', [])
                
                if existing_source_ids:
                    existing_source_ids.sort()  # Ordenar para comparación consistente
                    
                    # Si los IDs son iguales, no es necesario volver a neutralizar
                    if current_source_ids == existing_source_ids:
                        unchanged_group_count += 1
                        unchanged_group_ids.append(group_number)
                        continue
                    else:
                        # Los IDs son diferentes, necesitamos actualizar este documento existente
                        changed_group_count += 1
                        changed_group_ids.append(group_number)
                        groups_to_update.append({
                            'group': group_number,
                            'sources': sources,
                            'source_ids': current_source_ids,
                            'existing_doc': existing_data
                        })
                        continue
            
            # Si llegamos aquí, necesitamos crear un nuevo documento
            groups_to_neutralize.append({
                'group': group_number,
                'sources': sources,
                'source_ids': current_source_ids
            })
        
        
        neutralized_count = 0
        updated_count = 0
        db = initialize_firebase()
        total_discarded_groups_count = 0 # New counter for discarded groups
        print(f"Groups unchanged: {unchanged_group_count}. IDs: {unchanged_group_ids}")
        print(f"Groups changed and will be updated: {changed_group_count}. IDs: {changed_group_ids}")
        
        print(f"ℹ️ Updating neutralization of {len(groups_to_update)} groups")
        for i in range(0, len(groups_to_update), batch_size):
            current_batch_to_update = groups_to_update[i:i+batch_size]
            
            if current_batch_to_update:
                valid_batch_for_update, discarded_in_update_batch = validate_batch_for_processing(current_batch_to_update)
                total_discarded_groups_count += discarded_in_update_batch

                if valid_batch_for_update:
                    results = generate_neutral_analysis_batch(valid_batch_for_update)
                    
                    for result, group_info in zip(results, valid_batch_for_update):
                        if not result:
                            continue
                            
                        group = group_info['group']
                        sources = group_info['sources']
                        source_ids = group_info['source_ids']
                        
                        # Actualizar el documento existente en neutral_news
                        update_existing_neutral_news(group, result, source_ids)
                        
                        # Actualizar las noticias originales con su puntuación de neutralidad
                        update_news_with_neutral_scores(sources, result)
                        
                        updated_count += 1
        
        print(f"ℹ️ Creating neutralization for {len(groups_to_neutralize)} groups")
        for i in range(0, len(groups_to_neutralize), batch_size):
            current_batch_to_neutralize = groups_to_neutralize[i:i+batch_size]
            
            if current_batch_to_neutralize:
                valid_batch_for_neutralization, discarded_in_neutralize_batch = validate_batch_for_processing(current_batch_to_neutralize)
                total_discarded_groups_count += discarded_in_neutralize_batch

                if valid_batch_for_neutralization:
                    results = generate_neutral_analysis_batch(valid_batch_for_neutralization)
                    
                    for result, group_info in zip(results, valid_batch_for_neutralization): # Iterate over the validated batch
                        if not result:
                            continue
                            
                        group = group_info['group']
                        sources = group_info['sources']
                        source_ids = group_info['source_ids']
                        
                        # Guardar el resultado en la colección neutral_news con los IDs de fuente
                        store_neutral_news(group, result, source_ids)
                        
                        # Actualizar las noticias originales con su puntuación de neutralidad
                        update_news_with_neutral_scores(sources, result)
                        
                        neutralized_count += 1
        
        print(f"Created {neutralized_count}, updated {updated_count}, and discarded {total_discarded_groups_count} neutral news groups")
        return neutralized_count + updated_count
        
    except Exception as e:
        print(f"Error in neutralize_and_more: {str(e)}")
        import traceback
        traceback.print_exc()
        return 0
    
def generate_neutral_analysis_batch(group_batch):
    """
    Genera análisis neutros para un batch de grupos de noticias usando la API de OpenAI.
    """
    if not group_batch:
        return []
        
    results = []
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY environment variable not set.")
        raise ValueError("OpenAI API Key not configured.")
        
    api_key = api_key.strip()
    client = OpenAI(api_key=api_key)
    
    system_message = """
    Eres un analista de noticias imparcial. Te voy a pasar varios titulares y descripciones
    de una misma noticia contada por diferentes medios. Tu tarea:

    1. Generar un titular neutral CONCISO (entre 8-14 palabras máximo). El titular debe ser directo, 
       informativo y capturar la esencia de la noticia.
    
    2. Crear una descripción neutral estructurada en párrafos cortos (máximo 50 palabras por párrafo), con un límite aproximado 
       de 250 palabras en total. El primer párrafo debe contener la información más importante.
    
    3. Evaluar cada fuente con una puntuación de neutralidad (0 a 100).
    
    4. Asignar una categoría entre: Economía, Política, Ciencia, Tecnología, Cultura, Sociedad, Deportes, 
       Internacional, Entretenimiento, Otros.
       
    5. Evaluar la relevancia de la noticia en una escala del 1 al 5, donde:
       1 = Muy baja relevancia (interés muy local o limitado / publicidad o propaganda)
       2 = Baja relevancia (interés limitado a ciertos grupos)
       3 = Relevancia media (interés general pero sin gran impacto)
       4 = Alta relevancia (interés amplio con posible impacto social/político/económico)
       5 = Muy alta relevancia (gran impacto social/político/económico, noticia de primer nivel)

    Devuelve SOLO un JSON con esta estructura (sin explicaciones adicionales):
    {
        "neutral_title": "...",
        "neutral_description": "...",
        "category": "...",
        "relevance": X,
        "source_ratings": [
            {"source_medium": "...", "rating": X},
            ...
        ]
    }
    """
    
    try:
        messages_list = []
        
        for group_info in group_batch:
            sources = group_info.get('sources', [])
            sources_text = ""
            
            for i, source in enumerate(sources):
                if 'id' not in source or 'title' not in source or 'scraped_description' not in source or 'source_medium' not in source:
                    continue
                    
                sources_text += f"Fuente {i+1}: {source['source_medium']}\n"
                sources_text += f"Titular: {source['title']}\n"
                sources_text += f"Descripción: {source['scraped_description']}\n\n"
                
            if sources_text:
                user_message = f"Analiza las siguientes fuentes de noticias:\n\n{sources_text}"
                messages_list.append([
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ])
            else:
                # Si no hay texto de fuentes válido, añadir None al resultado
                results.append(None)
                
        # Realizar las llamadas a la API en paralelo
        for messages in messages_list:
            max_retries = 3
            retry_count = 0
            result = None
            
            while retry_count < max_retries:
                try:
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=messages,
                        temperature=0.3,
                        response_format={"type": "json_object"}
                    )
                    
                    result_json = json.loads(response.choices[0].message.content)
                    result = result_json
                    break  # Si la llamada fue exitosa, salimos del bucle
                    
                except Exception as e:
                    retry_count += 1
                    print(f"Error in API call (attempt {retry_count}/{max_retries}): {type(e).__name__}: {str(e)}")
                    
                    if retry_count < max_retries:
                        # Esperar antes de reintentar (backoff exponencial)
                        import time
                        wait_time = 2 ** retry_count  # 2, 4, 8 segundos
                        print(f"Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                    else:
                        print("Max retries reached, giving up on this request")
                        import traceback
                        traceback.print_exc()
            
            results.append(result)
                
        return results
        
    except Exception as e:
        print(f"Error in generate_neutral_analysis_batch: {str(e)}")
        import traceback
        traceback.print_exc()
        return [None] * len(group_batch)

def generate_neutral_analysis(sources):
    """
    Genera un análisis neutro de un grupo de noticias usando la API de OpenAI.
    """
    system_message = """
    Eres un analista de noticias imparcial. Te voy a pasar varios titulares y descripciones 
    de una misma noticia contada por diferentes medios. Tu tarea:
    
    1. Generar un titular neutral CONCISO (entre 8-14 palabras máximo). El titular debe ser directo, 
       informativo y capturar la esencia de la noticia.
    
    2. Crear una descripción neutral estructurada en párrafos cortos (máximo 50 palabras por párrafo), con un límite aproximado 
       de 250 palabras en total. El primer párrafo debe contener la información más importante.
    
    3. Evaluar cada fuente con una puntuación de neutralidad (0 a 100).
    
    4. Asignar una categoría entre: Economía, Política, Ciencia, Tecnología, Cultura, Sociedad, Deportes, 
       Internacional, Entretenimiento, Otros.
       
    5. Evaluar la relevancia de la noticia en una escala del 1 al 5, donde:
       1 = Muy baja relevancia (interés muy local o limitado / publicidad o propaganda)
       2 = Baja relevancia (interés limitado a ciertos grupos)
       3 = Relevancia media (interés general pero sin gran impacto)
       4 = Alta relevancia (interés amplio con posible impacto social/político/económico)
       5 = Muy alta relevancia (gran impacto social/político/económico, noticia de primer nivel)

    Devuelve SOLO un JSON con esta estructura (sin explicaciones adicionales):
    {
        "neutral_title": "...",
        "neutral_description": "...",
        "category": "...",
        "relevance": X,
        "source_ratings": [
            {"source_medium": "...", "rating": X},
            ...
        ]
    }
    """

    sources_text = ""
    for i, source in enumerate(sources):
        if 'id' not in source or 'title' not in source or 'scraped_description' not in source or 'source_medium' not in source:
            continue
        sources_text += f"Fuente {i+1}: {source['source_medium']}\n"
        sources_text += f"Titular: {source['title']}\n"
        sources_text += f"Descripción: {source['scraped_description']}\n\n"

    if not sources_text:
        return None

    user_message = f"Analiza las siguientes fuentes de noticias:\n\n{sources_text}"
    
    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            api_key = api_key.strip()
        client = OpenAI(api_key=api_key)
        
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": user_message}
                    ],
                    temperature=0.3,
                    response_format={"type": "json_object"}
                )
                
                result_json = json.loads(response.choices[0].message.content)
                return result_json
                
            except Exception as e:
                retry_count += 1
                print(f"Error in API call (attempt {retry_count}/{max_retries}): {type(e).__name__}: {str(e)}")
                
                if retry_count < max_retries:
                    # Esperar antes de reintentar (backoff exponencial)
                    import time
                    wait_time = 2 ** retry_count  # 2, 4, 8 segundos
                    print(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    print("Max retries reached, giving up on this request")
                    import traceback
                    traceback.print_exc()
                    return None
    
    except Exception as e:
        print(f"Error in generate_neutral_analysis: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def validate_batch_for_processing(batch_to_validate):
    """
    Validates a batch of groups to ensure they have enough valid sources.
    A valid source must have a non-empty title and scraped_description.
    A group is valid if it has at least 2 valid sources.
    Returns a list of valid groups and the count of discarded groups.
    """
    valid_groups_in_batch = []
    discarded_count = 0
    if not batch_to_validate:
        return [], 0

    for group_info_to_validate in batch_to_validate:
        sources_to_validate = group_info_to_validate.get('sources', [])
        valid_sources_count = 0
        for source in sources_to_validate:
            title = source.get('title', '')
            description = source.get('scraped_description', '') # Assuming 'scraped_description' is the field for content
            if title and description: # Checks if both are non-empty
                valid_sources_count += 1
        
        if valid_sources_count >= 2:
            valid_groups_in_batch.append(group_info_to_validate)
        else:
            discarded_count += 1
            group_id_to_skip = group_info_to_validate.get('group', 'Unknown')
            print(f"ℹ️ Discarding group {group_id_to_skip} for processing: requires at least 2 sources with non-empty title and description. Found {valid_sources_count}.")
    return valid_groups_in_batch, discarded_count