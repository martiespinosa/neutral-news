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
        
        no_group_count = 0
        no_group_ids = []
        
        no_sources_count = 0
        no_sources_ids = []
        
        unchanged_group_count = 0
        unchanged_group_ids = []
        
        changed_group_count = 0
        changed_group_ids = []
        
        to_neutralize_count = 0
        to_neutralize_ids = []
        
        
        
        
        print(f"ℹ️ Processing {len(news_groups)} news groups for neutralization")
        for group in news_groups:   
            group_number = group.get('group')
            if group_number is not None:
                group_number = int(float(group_number))
                group['group'] = group_number

            sources = group.get('sources', [])
            
            if not group:
                no_group_count += 1
                no_group_ids.append(group_number)
                continue
            if not sources or len(sources) < 2:
                no_sources_count += 1
                no_sources_ids.append(group_number)
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
            to_neutralize_count += 1
            to_neutralize_ids.append(group_number)

        neutralized_count = 0
        neutralized_groups = []
        
        updated_count = 0
        updated_groups = []
        
        discarded_count = 0
        discarded_groups = []
        
        db = initialize_firebase()
        print(f"Groups unchanged: {unchanged_group_count}. IDs: {unchanged_group_ids}")
        print(f"Groups changed and will be updated: {changed_group_count}. IDs: {changed_group_ids}")
        print(f"Groups to neutralize: {len(groups_to_neutralize)}. IDs: {to_neutralize_ids}")
        print(f"Groups with no sources: {no_sources_count}. IDs: {no_sources_ids}")
        print(f"Groups with no group number: {no_group_count}. IDs: {no_group_ids}")
        
        print(f"ℹ️ Updating neutralization of {len(groups_to_update)} groups")
        for i in range(0, len(groups_to_update), batch_size):
            current_batch_to_update = groups_to_update[i:i+batch_size]
            
            if current_batch_to_update:
                valid_batch_for_update, discarded_in_update_batch = validate_batch_for_processing(current_batch_to_update)
                
                # Fix: Extract valid group IDs
                valid_group_ids = [group_info['group'] for group_info in valid_batch_for_update]
                
                # Fix: Compare group IDs correctly
                discarded_groups_in_batch = [group_info['group'] for group_info in current_batch_to_update 
                                             if group_info['group'] not in valid_group_ids]
                
                discarded_count += discarded_in_update_batch
                discarded_groups.extend(discarded_groups_in_batch)

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
                        updated_groups.append(group)
        
        print(f"ℹ️ Creating neutralization for {len(groups_to_neutralize)} groups")
        for i in range(0, len(groups_to_neutralize), batch_size):
            current_batch_to_neutralize = groups_to_neutralize[i:i+batch_size]
            
            if current_batch_to_neutralize:
                valid_batch_for_neutralization, discarded_in_neutralize_batch = validate_batch_for_processing(current_batch_to_neutralize)
                
                # Fix: Extract valid group IDs
                valid_group_ids = [group_info['group'] for group_info in valid_batch_for_neutralization]
                
                # Fix: Compare group IDs correctly
                discarded_groups_in_batch = [group_info['group'] for group_info in current_batch_to_neutralize 
                                             if group_info['group'] not in valid_group_ids]
                
                discarded_count += discarded_in_neutralize_batch
                discarded_groups.extend(discarded_groups_in_batch)

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
                        neutralized_groups.append(group)
        
        print(f"Created {neutralized_count}, updated {updated_count}, and discarded {discarded_count} neutral news groups")
        print(f"Neutralized groups: {neutralized_groups}")
        print(f"Updated groups: {updated_groups}")
        print(f"Discarded groups: {discarded_groups}")
        return neutralized_count + updated_count

    except Exception as e:
        print(f"Error in neutralize_and_more: {str(e)}")
        import traceback
        traceback.print_exc()
        return 0
    
def generate_neutral_analysis_batch(group_batch):
    """
    Genera análisis neutros para un batch de grupos de noticias usando la API de OpenAI.
    Handles token limits intelligently, only truncating when necessary.
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
    
    # Approximate tokens per character (for estimation)
    TOKEN_RATIO = 0.25  # ~4 characters per token
    MAX_TOKENS = 125000  # Safe limit below the 128K maximum
    
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
    
    system_token_estimate = len(system_message) * TOKEN_RATIO
    
    try:
        # Process each group individually for better token control
        for group_info in group_batch:
            group_id = group_info.get('group', 'unknown')
            sources = group_info.get('sources', [])
            
            # Filter valid sources
            valid_sources = []
            for source in sources:
                if 'id' in source and 'title' in source and 'scraped_description' in source and 'source_medium' in source:
                    valid_sources.append(source)
            
            if len(valid_sources) < 2:
                results.append(None)
                continue
                
            # Calculate average description length for this group
            avg_desc_length = sum(len(s['scraped_description']) for s in valid_sources) / len(valid_sources)
            
            # First, identify and handle outliers (sources with extremely long descriptions)
            for source in valid_sources:
                desc_len = len(source['scraped_description'])
                # If a source is 3x longer than average, truncate it to a reasonable length
                if desc_len > (avg_desc_length * 3) and desc_len > 10000:
                    truncated_length = int(max(avg_desc_length * 2, 10000))
                    source['scraped_description'] = source['scraped_description'][:truncated_length] + "... [truncated due to excessive length]"
                    
            # Now build the message with all sources
            sources_text = ""
            total_token_estimate = system_token_estimate
            
            # First pass: try to include all sources with minimal truncation
            for i, source in enumerate(valid_sources):
                source_text = f"Fuente {i+1}: {source['source_medium']}\n"
                source_text += f"Titular: {source['title']}\n"
                source_text += f"Descripción: {source['scraped_description']}\n\n"
                
                source_token_estimate = len(source_text) * TOKEN_RATIO
                
                # If this source would push us over the limit, we need to truncate
                if total_token_estimate + source_token_estimate > MAX_TOKENS:
                    # Calculate how many tokens we can still use
                    remaining_tokens = MAX_TOKENS - total_token_estimate
                    # Convert to chars (approximate)
                    remaining_chars = int(remaining_tokens / TOKEN_RATIO)
                    # Truncate source text to fit
                    truncated_text = source_text[:remaining_chars]
                    # Add truncation notice
                    truncated_text = truncated_text.rsplit('\n', 1)[0] + "\n... [truncated due to token limit]\n\n"
                    sources_text += truncated_text
                    
                    break  # Stop adding more sources after truncation
                else:
                    sources_text += source_text
                    total_token_estimate += source_token_estimate
            
            user_message = f"Analiza las siguientes fuentes de noticias:\n\n{sources_text}"
            
            # Final token check
            final_estimate = (len(user_message) + len(system_message)) * TOKEN_RATIO
            if final_estimate > MAX_TOKENS:
                
                # If still too large, take more drastic measures
                # Try again, but only include a subset of sources (at least 2)
                if len(valid_sources) > 2:
                    # Sort sources by length (shortest first)
                    valid_sources.sort(key=lambda x: len(x.get('scraped_description', '')))
                    
                    # Only use the necessary number of sources
                    sources_text = ""
                    total_token_estimate = system_token_estimate
                    included_count = 0
                    
                    for i, source in enumerate(valid_sources):
                        source_text = f"Fuente {i+1}: {source['source_medium']}\n"
                        source_text += f"Titular: {source['title']}\n"
                        
                        # Truncate very long descriptions more aggressively
                        desc = source['scraped_description']
                        if len(desc) > 5000:
                            desc = desc[:5000] + "... [truncated due to length]"
                            
                        source_text += f"Descripción: {desc}\n\n"
                        
                        source_token_estimate = len(source_text) * TOKEN_RATIO
                        
                        if total_token_estimate + source_token_estimate < MAX_TOKENS:
                            sources_text += source_text
                            total_token_estimate += source_token_estimate
                            included_count += 1
                        else:
                            # If we already have 2+ sources, stop here
                            if included_count >= 2:
                                break
                                
                            # Otherwise, we need this source but must truncate it
                            remaining_tokens = MAX_TOKENS - total_token_estimate
                            remaining_chars = int(remaining_tokens / TOKEN_RATIO)
                            
                            if remaining_chars > 500:  # If we can include at least some meaningful content
                                truncated_text = source_text[:remaining_chars]
                                truncated_text = truncated_text.rsplit('\n', 1)[0] + "\n... [truncated due to token limit]\n\n"
                                sources_text += truncated_text
                                included_count += 1
                            break
                    
                    user_message = f"Analiza las siguientes fuentes de noticias:\n\n{sources_text}"
            
            # Call OpenAI API with retries
            max_retries = 3
            retry_count = 0
            result = None
            
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
                    result = result_json
                    break  # Success
                    
                except Exception as e:
                    if "context_length_exceeded" in str(e) and len(valid_sources) > 2:
                        # Token limit error despite our precautions - reduce sources further
                        # Sort sources by length (shortest first)
                        valid_sources.sort(key=lambda x: len(x.get('scraped_description', '')))
                        
                        # Reduce to just the 2 smallest sources
                        sources_text = ""
                        for i in range(min(2, len(valid_sources))):
                            source = valid_sources[i]
                            sources_text += f"Fuente {i+1}: {source['source_medium']}\n"
                            sources_text += f"Titular: {source['title']}\n"
                            
                            # Truncate descriptions to ensure we fit
                            desc = source['scraped_description']
                            if i == 0 and len(desc) > 5000:
                                desc = desc[:5000] + "... [truncated]"
                            elif i == 1 and len(desc) > 3000:
                                desc = desc[:3000] + "... [truncated]"
                                
                            sources_text += f"Descripción: {desc}\n\n"
                        
                        user_message = f"Analiza las siguientes fuentes de noticias:\n\n{sources_text}"
                        print(f"⚠️ Emergency reduction to 2 sources for group {group_id} after token error")
                        continue  # Try again with reduced content
                    
                    # For other errors, use standard retry
                    retry_count += 1
                    print(f"Error in API call (attempt {retry_count}/{max_retries}): {type(e).__name__}: {str(e)}")
                    
                    if retry_count < max_retries:
                        import time
                        wait_time = 2 ** retry_count  # 2, 4, 8 seconds
                        print(f"Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                    else:
                        print(f"Max retries reached for group {group_id}, giving up")
                        import traceback
                        traceback.print_exc()
            
            results.append(result)
                
        return results
        
    except Exception as e:
        print(f"Error in generate_neutral_analysis_batch: {str(e)}")
        import traceback
        traceback.print_exc()
        return [None] * len(group_batch)

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
        group_id = group_info_to_validate.get('group', 'unknown')
        sources_to_validate = group_info_to_validate.get('sources', [])
        valid_sources_count = 0
        valid_sources = []
        
        print(f"Validating group {group_id} with {len(sources_to_validate)} sources")
        
        for source in sources_to_validate:
            title = source.get('title', '')
            description = source.get('scraped_description', '')
            
            # Stricter validation - handles whitespace only strings too
            if title and title.strip() and description and description.strip():
                valid_sources_count += 1
                valid_sources.append(source)
        
        print(f"Group {group_id}: Found {valid_sources_count} valid sources out of {len(sources_to_validate)}")
        
        if valid_sources_count >= 2:
            valid_groups_in_batch.append(group_info_to_validate)
        else:
            discarded_count += 1
            print(f"⚠️ Discarding group {group_id}: Only {valid_sources_count} valid sources (need at least 2)")
            
    return valid_groups_in_batch, discarded_count