from openai import OpenAI
import os, json
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from threading import Lock

from src.storage import store_neutral_news, update_news_with_neutral_scores, update_existing_neutral_news
from .config import initialize_firebase
from google.cloud import firestore
MIN_VALID_SOURCES = 3  # Minimum number of valid sources required

# Rate limiter class to manage API call rate limiting
class RateLimiter:
    def __init__(self, calls_per_minute=500):
        self.calls_per_minute = calls_per_minute
        self.call_count = 0
        self.call_time = time.time()
        self.lock = Lock()
    
    def check_limit(self, group_id="unknown"):
        """Check if we're over the rate limit and handle accordingly"""
        with self.lock:
            current_time = time.time()
            elapsed = current_time - self.call_time
            
            # Reset counter after 60 seconds
            if elapsed > 60:
                self.call_count = 0
                self.call_time = current_time
                
            # If we've made too many calls in the last minute, sleep
            if self.call_count >= self.calls_per_minute:
                sleep_time = max(0, 60 - elapsed)
                print(f"⏳ Rate limiting: sleeping for {sleep_time:.2f}s before processing group {group_id}")
                time.sleep(sleep_time)
                self.call_count = 0
                self.call_time = time.time()
                
            self.call_count += 1

    def force_cooldown(self):
        """Force a cooldown period after hitting an API limit"""
        with self.lock:
            self.call_time = time.time()
            self.call_count = self.calls_per_minute  # This will trigger a sleep on the next call

# Create a single instance of the rate limiter
api_rate_limiter = RateLimiter()

def neutralize_and_more(news_groups, batch_size=5):
    """
    Coordina el proceso de neutralización de grupos de noticias y actualiza Firestore.
    Procesa los grupos en paralelo usando ThreadPoolExecutor para optimizar el rendimiento.
    """
    if not news_groups:
        print("No news groups to neutralize")
        return 0
    
    db = initialize_firebase()
    
    try:
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
            if not sources or len(sources) < MIN_VALID_SOURCES:
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
        
        updated_neutral_scores_count = 0
        updated_neutral_scores_news = []
        
        print(f"Groups unchanged: {unchanged_group_count}. IDs: {unchanged_group_ids}")
        print(f"Groups changed and will be updated: {changed_group_count}. IDs: {changed_group_ids}")
        print(f"Groups to neutralize: {len(groups_to_neutralize)}. IDs: {to_neutralize_ids}")
        
        # Maximum number of workers for the thread pool
        # OpenAI API can handle multiple concurrent requests - adjust based on your rate limits
        MAX_WORKERS = 50  # Starting higher - can be adjusted based on API behavior
        
        skipped_update_count = 0
        skipped_update_groups = []

        # Define a function to process a single group (either update or neutralize)
        def process_group(group_info, is_update=False):
            try:
                group = group_info.get('group')
                sources = group_info.get('sources', [])
                source_ids = group_info.get('source_ids', [])
                
                # Generate neutral analysis for this single group
                response = generate_neutral_analysis_single(group_info, is_update)
                
                if response is None:
                    return {"success": False, "error": "API limit or quota exceeded", "group": group}
                
                # Unpack the response
                skipped = False
                if isinstance(response, tuple) and len(response) == 2:
                    result, sources_to_unassign = response
                elif isinstance(response, tuple) and len(response) == 3:
                    result, sources_to_unassign, skipped = response
                else:
                    result = response
                    sources_to_unassign = {}
                    
                if not result:
                    return {"success": False, "error": "No result generated", "group": group}
                    
                # Process the result based on whether this is an update or new neutralization
                if is_update:
                    success = update_existing_neutral_news(group, result, source_ids, sources_to_unassign, skipped)
                else:
                    success = store_neutral_news(group, result, source_ids, sources_to_unassign)
                
                # Initialize scores_result to avoid UnboundLocalError
                scores_result = None
                if not skipped:
                    scores_result = update_news_with_neutral_scores(sources, result, sources_to_unassign)
                
                return {
                    "success": success,
                    "is_update": is_update,
                    "skipped": skipped,
                    "group": group,
                    "scores_result": scores_result
                }
                
            except Exception as e:
                print(f"Error processing group {group_info.get('group')}: {str(e)}")
                import traceback
                traceback.print_exc()
                return {"success": False, "error": str(e), "group": group_info.get('group')}
        
        # Process all groups asynchronously using ThreadPoolExecutor
        print(f"ℹ️ Processing {len(groups_to_update)} updates and {len(groups_to_neutralize)} new neutralizations with {MAX_WORKERS} workers")
        MAX_WORKERS = min(MAX_WORKERS, len(groups_to_update) + len(groups_to_neutralize))
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Submit all update tasks
            update_futures = {
                executor.submit(process_group, group, True): group 
                for group in groups_to_update
            }
            
            # Submit all neutralization tasks  
            neutralize_futures = {
                executor.submit(process_group, group, False): group
                for group in groups_to_neutralize
            }
            
            # Process update results as they complete
            for future in as_completed(update_futures):
                result = future.result()
                if result["success"]:
                    if result.get("skipped", False):
                        # This was a skipped update
                        skipped_update_count += 1
                        skipped_update_groups.append(result["group"])
                    else:
                        # This was a completed update
                        updated_count += 1
                        updated_groups.append(result["group"])
                        
                        if result.get("scores_result"):
                            count, news_ids = result["scores_result"]
                            updated_neutral_scores_count += count
                            updated_neutral_scores_news.extend(news_ids)
            
            # Process neutralization results as they complete
            for future in as_completed(neutralize_futures):
                result = future.result()
                if result["success"]:
                    neutralized_count += 1
                    neutralized_groups.append(result["group"])
                    
                    if result.get("scores_result"):
                        count, news_ids = result["scores_result"]
                        updated_neutral_scores_count += count
                        updated_neutral_scores_news.extend(news_ids)
        
        print(f"Created {neutralized_count}, updated {updated_count} neutral news groups, skipped {skipped_update_count} updates, updated {updated_neutral_scores_count} regular news with neutral scores")
        print(f"Neutralized groups: {neutralized_groups}")
        print(f"Groups updated with new neutralization: {updated_groups}")
        print(f"Groups with skipped updates: {skipped_update_groups}")
        print(f"Updated neutral scores for news: {updated_neutral_scores_news}")
        return neutralized_count + updated_count

    except Exception as e:
        print(f"Error in neutralize_and_more: {str(e)}")
        import traceback
        traceback.print_exc()
        return 0

def generate_neutral_analysis_single(group_info, is_update):
    """
    Process a single group for neutral analysis.
    This is extracted from generate_neutral_analysis_batch to work with one group at a time.
    """
    if not group_info:
        return None
    
    # Create base dictionary for source IDs to unassign
    group_dict = {}
    group_id = group_info.get('group', 'unknown')
    sources = group_info.get('sources', [])
    
    # Use the rate limiter instead of global variables
    api_rate_limiter.check_limit(group_id)

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
    
    SOURCES_LIMIT = 16  # Maximum number of sources to process
    try:
        valid_sources = []
        for source in sources:
            if 'id' in source and 'title' in source and 'scraped_description' in source and 'source_medium' in source:
                valid_sources.append(source)
        
        if len(valid_sources) < MIN_VALID_SOURCES:
            print(f"⚠️ Not enough valid sources for group {group_id}. Skipping.")
            return None
            
        # Select only one source per press medium (the most recently published)
        sources_by_medium = {}
        sources_to_delete = []
        
        for source in valid_sources:
            medium = source.get('source_medium')
            
            # Check for date fields (try different possible field names)
            published_date = source.get('pub_date') or source.get('created_at')
            
            if medium:
                # If we already have a source for this medium
                if medium in sources_by_medium:
                    existing_source = sources_by_medium[medium]
                    existing_date = existing_source.get('pub_date') or existing_source.get('created_at')
                    
                    # Compare dates to keep the most recent one
                    if published_date and existing_date and published_date > existing_date:
                        # This source is newer, so the existing one should be deleted
                        sources_to_delete.append(existing_source)
                        sources_by_medium[medium] = source
                    else:
                        # The existing source is newer or no date comparison possible
                        sources_to_delete.append(source)
                else:
                    # First source for this medium
                    sources_by_medium[medium] = source
        
        # Update overridden sources to remove group assignment
        if sources_to_delete:
            db = initialize_firebase()
            for source in sources_to_delete:
                source_id = source.get('id')
                if source_id:
                    try:
                        db.collection('news').document(source_id).update({
                            'group': None,
                            'updated_at': None
                        })
                        # Also handle neutral news doc
                        if is_update:
                            neutral_doc_ref = db.collection('neutral_news').document(str(group_id))
                            neutral_doc_ref.update({
                                'source_ids': firestore.ArrayRemove([source_id])
                            })
                        # Add to dictionary for later removal
                        if str(group_id) not in group_dict:
                            group_dict[str(group_id)] = []
                        group_dict[str(group_id)].append(source_id)
                    except Exception as e:
                        print(f"  Failed to update news item {source_id}: {str(e)}")
        
        # Use deduplicated sources 
        valid_sources = list(sources_by_medium.values())
        print(f"ℹ️ Selected {len(valid_sources)} sources (one per media) from {len(sources)} original sources for group {group_id}")

        # If we're updating an existing neutralization, check if update is really needed
        if is_update:
            # Retrieve the existing document to compare sources
            try:
                db = initialize_firebase()
                neutral_doc_ref = db.collection('neutral_news').document(str(group_id))
                neutral_doc = neutral_doc_ref.get()
                
                if neutral_doc.exists:
                    existing_data = neutral_doc.to_dict()
                    existing_source_ids = set(existing_data.get('source_ids', []))
                    current_source_ids = {source.get('id') for source in valid_sources if source.get('id')}
                    
                    # Get number of sources in each set
                    existing_count = len(existing_source_ids)
                    current_count = len(current_source_ids)
                    
                    # Calculate how many sources have changed (added or removed)
                    changed_sources = existing_source_ids.symmetric_difference(current_source_ids)
                    change_ratio = len(changed_sources) / max(existing_count, 1)
                    
                    # Define thresholds for significant source count increase
                    significant_increase = (
                        (existing_count >= 3 and existing_count < 6 and current_count >= 6) or
                        (existing_count >= 6 and existing_count < 9 and current_count >= 9) or
                        (existing_count >= 9 and existing_count < 12 and current_count >= 12)
                    )
                    
                    # Skip update if neither condition is met
                    if change_ratio < 0.5 and not significant_increase:
                        print(f"ℹ️ Skipping update for group {group_id}: Only {len(changed_sources)}/{existing_count} sources changed ({change_ratio:.2%}), not significant.")
                        
                        # Find sources in existing but not in current - mark for unassignment
                        removed_sources = existing_source_ids - current_source_ids
                        if removed_sources:
                            if str(group_id) not in group_dict:
                                group_dict[str(group_id)] = []
                            group_dict[str(group_id)].extend(list(removed_sources))
                            print(f"ℹ️ Marked {len(removed_sources)} sources for unassignment from group {group_id}")
                        
                        # Return existing data to avoid regeneration
                        skipped = True
                        return existing_data, group_dict, skipped
                    else:
                        print(f"ℹ️ Update needed for group {group_id}: {len(changed_sources)}/{existing_count} sources changed ({change_ratio:.2%}), significant: {significant_increase}")
                        
                        # Find sources in existing but not in current - mark for unassignment
                        removed_sources = existing_source_ids - current_source_ids
                        if removed_sources:
                            if str(group_id) not in group_dict:
                                group_dict[str(group_id)] = []
                            group_dict[str(group_id)].extend(list(removed_sources))
                            print(f"ℹ️ Marked {len(removed_sources)} removed sources for unassignment from group {group_id}")
            except Exception as e:
                print(f"Error checking update necessity: {str(e)}")
                # Continue with update in case of error
        
        # Apply source limit after deduplication
        if len(valid_sources) > SOURCES_LIMIT:
            # Mark removed sources for unassignment
            removed_sources = valid_sources[SOURCES_LIMIT:]
            for source in removed_sources:
                source_id = source.get('id')
                if source_id:
                    if str(group_id) not in group_dict:
                        group_dict[str(group_id)] = []
                    if source_id not in group_dict[str(group_id)]:
                        group_dict[str(group_id)].append(source_id)
            
            valid_sources = valid_sources[:SOURCES_LIMIT]
            print(f"ℹ️ Limiting to {SOURCES_LIMIT} sources, marked {len(removed_sources)} excess sources for unassignment")
            
        if len(valid_sources) < MIN_VALID_SOURCES:
            # Handle case with insufficient sources after deduplication
            print(f"⚠️ Not enough valid sources after deduplication for group {group_id}. Skipping.")
            
            # Unassign the group from any remaining source
            if len(valid_sources) == 1:
                remaining_source = valid_sources[0]
                source_id = remaining_source.get('id')
                if source_id:
                    try:
                        db = initialize_firebase()
                        db.collection('news').document(source_id).update({
                            'group': None,
                            'updated_at': None
                        })
                        # Also handle neutral news doc
                        if is_update:
                            neutral_doc_ref = db.collection('neutral_news').document(str(group_id))
                            neutral_doc_ref.update({
                                'source_ids': firestore.ArrayRemove([source_id])
                            })
                        # Add to dictionary
                        if str(group_id) not in group_dict:
                            group_dict[str(group_id)] = []
                        group_dict[str(group_id)].append(source_id)
                        print(f"  Unassigned group from the only remaining source {source_id}")
                    except Exception as e:
                        print(f"  Failed to unassign group from source {source_id}: {str(e)}")
            
            return None

        # Calculate average description length for this group
        avg_desc_length = sum(len(s['scraped_description']) for s in valid_sources) / len(valid_sources)
        
        # Handle outliers (sources with extremadamente long descriptions)
        for source in valid_sources:
            desc_len = len(source['scraped_description'])
            if desc_len > (avg_desc_length * 3) and desc_len > 10000:
                truncated_length = int(max(avg_desc_length * 2, 10000))
                source['scraped_description'] = source['scraped_description'][:truncated_length] + "... [truncated due to excessive length]"
        
        # Prepare sources text for API call
        sources_text = ""
        for i, source in enumerate(valid_sources):
            source_text = f"Fuente {i+1}: {source['source_medium']}\n"
            source_text += f"Titular: {source['title']}\n"
            source_text += f"Descripción: {source['scraped_description']}\n\n"
            sources_text += source_text
        
        user_message = f"Analiza las siguientes fuentes de noticias:\n\n{sources_text}"
        
        # Call OpenAI API with retries
        max_retries = 3
        retry_count = 0
        result = None
        
        while retry_count < max_retries:
            try:
                print(f"ℹ️ Generating neutral analysis for group {group_id} (attempt {retry_count + 1})")
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
                error_message = str(e)
                
                # Check for rate limit/quota errors
                if "429" in error_message or "insufficient_quota" in error_message or "rate_limit" in error_message:
                    print(f"⛔ Rate limit or quota exceeded for group {group_id}. Stopping processing.")
                    # Use the rate limiter's force_cooldown method instead of manipulating globals
                    api_rate_limiter.force_cooldown()
                    return None
                
                # Handle token limit errors
                if "context_length_exceeded" in str(e) and len(valid_sources) > MIN_VALID_SOURCES:
                    # Take just 3 shortest sources with aggressive truncation
                    valid_sources.sort(key=lambda x: len(x.get('scraped_description', '')))
                    
                    sources_text = ""
                    for i in range(min(3, len(valid_sources))):
                        source = valid_sources[i]
                        sources_text += f"Fuente {i+1}: {source['source_medium']}\n"
                        sources_text += f"Titular: {source['title']}\n"
                        
                        # Very aggressive truncation
                        desc = source['scraped_description']
                        if i == 0 and len(desc) > 5000:
                            desc = desc[:5000] + "... [truncated]"
                        elif i == 1 and len(desc) > 3000:
                            desc = desc[:3000] + "... [truncated]"
                            
                        sources_text += f"Descripción: {desc}\n\n"
                    
                    user_message = f"Analiza las siguientes fuentes de noticias:\n\n{sources_text}"
                    print(f"⚠️ Emergency reduction to 3 sources for group {group_id} after token error")
                    continue  # Try again with reduced content
                
                # Standard retry with backoff
                retry_count += 1
                print(f"Error in API call (attempt {retry_count}/{max_retries}): {type(e).__name__}: {error_message}")
                
                if retry_count < max_retries:
                    wait_time = 2 ** retry_count  # 2, 4, 8 seconds
                    print(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    print(f"Max retries reached for group {group_id}, giving up")
                    import traceback
                    traceback.print_exc()
        
        return result, group_dict
        
    except Exception as e:
        print(f"Error in generate_neutral_analysis_single for group {group_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

# Keep the batch function as a wrapper that calls the single function for each item
def generate_neutral_analysis_batch(group_batch, is_update):
    """Wrapper function that calls generate_neutral_analysis_single for each item in batch"""
    if not group_batch:
        return []
    
    results = []
    combined_dict = {}
    
    for group_info in group_batch:
        response = generate_neutral_analysis_single(group_info, is_update)
        
        if response is None:
            # If we hit a rate limit, stop processing the batch
            return None
            
        # Unpack the response
        if isinstance(response, tuple) and len(response) == 2:
            result, sources_to_unassign = response
            # Merge dictionaries
            for group_id, source_ids in sources_to_unassign.items():
                if group_id not in combined_dict:
                    combined_dict[group_id] = []
                combined_dict[group_id].extend(source_ids)
        else:
            result = response
            
        results.append(result)
    
    return results, combined_dict