import os
import traceback
import time
from .storage import get_all_embeddings
from .storage import update_news_embedding
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
# Define a global model variable
_model = None
_nlp_modules_loaded = False

def _load_nlp_modules():
    """Lazily import NLP-related modules to speed up cold starts"""
    global _nlp_modules_loaded
    if not _nlp_modules_loaded:
        global np, pd, SentenceTransformer, NearestNeighbors, lil_matrix, DBSCAN, sort_graph_by_row_values

        import numpy as np
        import pandas as pd
        from sentence_transformers import SentenceTransformer
        from sklearn.neighbors import NearestNeighbors, sort_graph_by_row_values
        from scipy.sparse import lil_matrix
        from sklearn.cluster import DBSCAN

        _nlp_modules_loaded = True

def get_sentence_transformer_model(retry_count=3):
    """Get or initialize the sentence transformer model.
    In Cloud Functions, attempts to load from a bundled path first.
    Falls back to downloading if bundled load fails or if running locally.
    """
    _load_nlp_modules()

    global _model
    if _model is not None:
        return _model

    # model_name = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    # Path where the model is expected to be in the Docker image
    bundled_model_path = "/app/model"

    # --- Attempt 1: Load from bundled path if in Cloud Function ---
    if os.getenv("FUNCTION_TARGET"):
        print(f"ℹ️ Cloud Function environment detected. Attempting to load model from bundled path: {bundled_model_path}")
        try:
            if os.path.exists(bundled_model_path):
                _model = SentenceTransformer(bundled_model_path)
                print(f"✅ Model loaded successfully from bundled path: {bundled_model_path}")
                return _model
            else:
                 print(f"⚠️ Bundled model path not found: {bundled_model_path}")
        except Exception as e:
            print(f"⚠️ Failed to load model from bundled path {bundled_model_path}: {type(e).__name__}: {str(e)}")
            # print("ℹ️ Falling back to downloading the model.")  # Uncommented this line
            # If loading from bundled path fails, proceed to download logic below
    """
    # --- Attempt 2: Download model (Fallback or Local) ---
    cache_dir = None
    if os.getenv("FUNCTION_TARGET"):
        # Use /tmp for caching when downloading within Cloud Function (fallback scenario)
        cache_dir = "/tmp/sentence_transformers_cache"
        print(f"ℹ️ Using temporary cache directory for download: {cache_dir}")
        # Attempt to clear the cache directory before download
        if os.path.exists(cache_dir):
            print(f"ℹ️ Attempting to clear existing cache directory: {cache_dir}")
            try:
                shutil.rmtree(cache_dir)
                print(f"✅ Successfully cleared cache directory: {cache_dir}")
            except OSError as e:
                print(f"⚠️ Warning: Could not remove cache directory {cache_dir}: {e}")
        try:
            os.makedirs(cache_dir, exist_ok=True)
            print(f"✅ Ensured cache directory exists: {cache_dir}")
        except OSError as e:
             print(f"❌ Error creating cache directory {cache_dir}: {e}. Proceeding without specific cache folder.")
             cache_dir = None # Fallback to default library caching if creation fails
    else:
        print("ℹ️ Local environment detected. Using default cache for download.")

    # Retry loop for downloading
    for attempt in range(retry_count):
        try:
            print(f"ℹ️ Download Attempt {attempt + 1}/{retry_count}: Loading model '{model_name}'...")
            if cache_dir:
                 print(f"ℹ️ Using cache folder: {cache_dir}")
                 _model = SentenceTransformer(
                     model_name,
                     cache_folder=cache_dir
                 )
            else:
                 # Local development or cache creation failed
                 _model = SentenceTransformer(model_name)

            print(f"✅ Model '{model_name}' downloaded/loaded successfully.")
            break  # Success! Exit retry loop

        except (OSError, ImportError, Exception) as e: # Catch broader exceptions during download/load
            print(f"❌ Download Attempt {attempt + 1} failed: {type(e).__name__}: {str(e)}")
            # Log traceback for detailed debugging on later attempts
            if attempt > 0:
                traceback.print_exc()

            if isinstance(e, ImportError):
                 print("❌ Potential missing dependency. Ensure torch/tensorflow and transformers are installed.")

            if attempt == retry_count - 1:  # If this was the last attempt
                print(f"❌ Failed to load/download the model after {retry_count} attempts.")
                # Re-raise the last exception caught
                raise RuntimeError(
                    f"Failed to load/download the model after {retry_count} attempts. Last error: {str(e)}"
                ) from e

            # Exponential backoff
            wait_time = 2 ** attempt
            print(f"ℹ️ Retrying download in {wait_time} seconds...")
            time.sleep(wait_time)
    """
    return _model
def group_news(news_list: list) -> list:
    """
    Groups news based on their semantic similarity
    """
    try:
        print("ℹ️ Starting news grouping...")
        _load_nlp_modules()
        
        # Step 1: Setup DataFrame and handle references
        df, has_reference_news, should_return_early, early_result = setup_news_dataframe(news_list)
        if should_return_early:
            return early_result
        
        # Step 2: Process embeddings
        all_items_for_clustering_df, embeddings_norm = process_embeddings(df)
        
        # Step 3: Perform clustering if we have valid embeddings
        clustering_succeeded = perform_clustering(all_items_for_clustering_df, embeddings_norm, df, has_reference_news)
        if not clustering_succeeded:
            return df[["id", "group", "title", "scraped_description", "description", "source_medium"]].to_dict(orient='records')
        
        # Step 4: Assign final group IDs
        assign_group_ids(df, has_reference_news)
        
        # Step 5: Process results and handle deduplication
        result = process_results(df)
        
        print("✅ Grouping completed successfully")
        return result
    
    except Exception as e:
        print(f"❌ Error in group_news: {str(e)}")
        traceback.print_exc()
        if 'df' in locals() and isinstance(df, pd.DataFrame):
             return df[["id", "group", "title", "scraped_description", "description", "source_medium"]].to_dict(orient='records')
        return []

def setup_news_dataframe(news_list: list) -> tuple:
    """
    Initial setup of the DataFrame and handling of reference news
    Returns a tuple of (df, has_reference_news, should_return_early, early_result)
    """
    print("ℹ️ Converting List to DataFrame...")
    df = pd.DataFrame(news_list)

    if "id" not in df.columns or "title" not in df.columns or "scraped_description" not in df.columns:
        raise ValueError("The JSON must contain the columns 'id', 'title' and 'scraped_description' with the text of the news")
    
    df["group"] = None 
    
    print("ℹ️ Checking for existing groups...")
    has_reference_news = "existing_group" in df.columns
    if has_reference_news:
        df.loc[df["existing_group"].notna(), "group"] = df.loc[df["existing_group"].notna(), "existing_group"] # Assign existing groups to 'group' column
        reference_mask = df["existing_group"].notna() 
        df["is_reference"] = reference_mask # Mark reference news
        to_group_count = (~reference_mask).sum()
        if to_group_count == 0:
            print("ℹ️ All news items already have groups. No new grouping needed.")
            return df, has_reference_news, True, df[["id", "group", "title", "scraped_description", "description", "source_medium"]].to_dict(orient='records')
    else:
        df["is_reference"] = False
        to_group_count = len(df)
        
    print(f"ℹ️ Found {df['is_reference'].sum()} reference news and {to_group_count} news to group.")
    
    # Handle cases with very few items to group early
    items_to_potentially_group_df = df[~df["is_reference"]]
    if len(items_to_potentially_group_df) == 0 and has_reference_news:
        print("ℹ️ No new items to group, only reference news present.")
        return df, has_reference_news, True, df[["id", "group", "title", "scraped_description", "description", "source_medium"]].to_dict(orient='records')
    if len(items_to_potentially_group_df) <= 1 and not has_reference_news:
        print("ℹ️ Only one new item to group and no reference news. Assigning to group None.")
        df.loc[~df["is_reference"], "group"] = None
        return df, has_reference_news, True, df[["id", "group", "title", "scraped_description", "description", "source_medium"]].to_dict(orient='records')
    
    return df, has_reference_news, False, None

def process_embeddings(df: pd.DataFrame) -> tuple:
    """
    Process and generate embeddings for news items
    Returns tuple of (all_items_for_clustering_df, embeddings_norm)
    """
    all_items_for_clustering_df = df.copy()
    all_items_for_clustering_df['embedding_vector'] = None

    # STEP 1: Generate embeddings for items in df that need them
    df_needing_embeddings = pd.DataFrame(get_news_not_embedded(df.copy()))

    if not df_needing_embeddings.empty:
        print(f"ℹ️ Found {len(df_needing_embeddings)} items needing new embeddings.")
        print("ℹ️ Loading embeddings model...")
        model = get_sentence_transformer_model()
        
        print("ℹ️ Extracting titles and descriptions for new embeddings...")
        if not all(col in df_needing_embeddings.columns for col in ["title", "id"]):
             raise ValueError("DataFrame for new embeddings is missing 'title' or 'id'.")

        titles, descriptions = extract_titles_and_descriptions(df_needing_embeddings)
        df_needing_embeddings["noticia_completa"] = titles + " " + descriptions
        
        print("ℹ️ Generating new embeddings...")
        texts_to_encode = df_needing_embeddings["noticia_completa"].tolist()
        news_ids_for_new_embeddings = df_needing_embeddings["id"].tolist()
        
        if texts_to_encode:
            # Generate embeddings
            batch_size_embed = 256
            new_embeddings_list_np = []
            for i in range(0, len(texts_to_encode), batch_size_embed):
                batch_texts = texts_to_encode[i:min(i + batch_size_embed, len(texts_to_encode))]
                batch_embeddings_np = model.encode(batch_texts, convert_to_numpy=True, show_progress_bar=False)
                new_embeddings_list_np.append(batch_embeddings_np)
            
            if new_embeddings_list_np:
                new_embeddings_np = np.vstack(new_embeddings_list_np)
                print(f"✅ Generated {len(new_embeddings_np)} new embeddings.")

                # Store these new embeddings in Firestore
                embeddings_for_storage_list = [emb.tolist() for emb in new_embeddings_np]
                print("ℹ️ Saving new embeddings to Firestore...")
                update_news_embedding(news_ids_for_new_embeddings, embeddings_for_storage_list)
                print(f"✅ Saved new embeddings to Firestore.")

                # Add embeddings to dataframes
                for idx, news_id in enumerate(news_ids_for_new_embeddings):
                    current_embedding_np = new_embeddings_np[idx]
                    current_embedding_list = current_embedding_np.tolist()

                    # Update 'all_items_for_clustering_df.embedding_vector'
                    target_indices_all_items = all_items_for_clustering_df[all_items_for_clustering_df['id'] == news_id].index
                    for i_loc in target_indices_all_items:
                        all_items_for_clustering_df.at[i_loc, 'embedding_vector'] = [current_embedding_np]
                    
                    # Update 'df.embedding'
                    for idx in df.index[df['id'] == news_id]:
                        df.at[idx, 'embedding'] = current_embedding_list

    # STEP 2: Populate 'embedding_vector' for items with existing embeddings
    print("ℹ️ Populating existing embeddings for clustering...")
    for index, row in all_items_for_clustering_df.iterrows():
        if row['embedding_vector'] is None:
            if 'embedding' in row and row['embedding'] is not None and isinstance(row['embedding'], list) and len(row['embedding']) > 0:
                all_items_for_clustering_df.at[index, 'embedding_vector'] = [np.array(row['embedding'])]
            else:
                print(f"⚠️ Item with ID {row['id']} has no new or existing valid embedding. It will be excluded from clustering if this persists.")
                all_items_for_clustering_df.at[index, 'embedding_vector'] = [np.zeros(get_sentence_transformer_model().get_sentence_embedding_dimension())]

    print(f"ℹ️ Populated embeddings: {all_items_for_clustering_df['embedding_vector'].notna().sum()} out of {len(all_items_for_clustering_df)}")
    
    # Filter out rows without embeddings
    all_items_for_clustering_df.dropna(subset=['embedding_vector'], inplace=True)

    if all_items_for_clustering_df.empty:
        return all_items_for_clustering_df, None

    # Extract and normalize embedding vectors
    embeddings_for_clustering_np = np.vstack(all_items_for_clustering_df['embedding_vector'].apply(lambda x: x[0]).tolist())
    
    if embeddings_for_clustering_np.shape[0] == 0:
        return all_items_for_clustering_df, None
    
    print("ℹ️ Normalizing embeddings for cosine similarity...")
    norms = np.linalg.norm(embeddings_for_clustering_np, axis=1, keepdims=True)
    norms[norms == 0] = 1e-10
    embeddings_norm = embeddings_for_clustering_np / norms
    
    return all_items_for_clustering_df, embeddings_norm

def perform_clustering(all_items_for_clustering_df, embeddings_norm, df, has_reference_news):
    """
    Perform DBSCAN clustering and map results to the original dataframe
    """
    if embeddings_norm is None or embeddings_norm.shape[0] == 0:
        print("❌ No embeddings available for clustering.")
        return False
    
    print("ℹ️ Calculating nearest neighbors graph...")
    n_neighbors = min(5, embeddings_norm.shape[0])
    if n_neighbors < 2 and embeddings_norm.shape[0] > 1:
        n_neighbors = 2 
    elif embeddings_norm.shape[0] <= 1:
        print("ℹ️ Not enough samples to perform clustering. Assigning all to group 0 or existing groups.")
        if not has_reference_news and embeddings_norm.shape[0] == 1:
            all_items_for_clustering_df['group'] = 0
        # Update original df based on all_items_for_clustering_df's groups
        for index, row_clustered in all_items_for_clustering_df.iterrows():
            df.loc[df['id'] == row_clustered['id'], 'group'] = row_clustered['group']
        return False

    nbrs = NearestNeighbors(n_neighbors=n_neighbors, metric="cosine").fit(embeddings_norm)
    dist_matrix_sparse = nbrs.kneighbors_graph(embeddings_norm, n_neighbors=n_neighbors, mode='distance')
    
    print("ℹ️ Sorting sparse distance graph...")
    dist_matrix_sparse_sorted = sort_graph_by_row_values(dist_matrix_sparse)
    
    print("ℹ️ Applying DBSCAN algorithm...")
    eps = 0.25
    min_samples = 2
    
    clustering = DBSCAN(eps=eps, min_samples=min_samples, metric="precomputed")
    group_labels = clustering.fit_predict(dist_matrix_sparse_sorted)

    # Assign temp_group to clustering results
    all_items_for_clustering_df["temp_group"] = group_labels
    
    # Map temp_groups back to the original df
    id_to_temp_group_map = pd.Series(all_items_for_clustering_df.temp_group.values, index=all_items_for_clustering_df.id).to_dict()
    df['temp_group'] = df['id'].map(id_to_temp_group_map)
    
    return True
def assign_group_ids(df, has_reference_news):
    """
    Assign final group IDs based on DBSCAN clusters and reference groups
    """
    # Define large groups that need update reduction
    large_groups = [1, 2]
    
    # Set a time threshold for large groups (e.g., 24 hours)
    time_threshold = datetime.now() - timedelta(hours=24)
    
    # Track groups that have been assigned in this run to avoid duplicates
    groups_used_this_run = set()
    MIN_SUBDIVISION_SIZE = 5  # Minimum cluster size needed for subdivision
    
    if has_reference_news:
        print("ℹ️ Mapping new DBSCAN clusters to existing reference groups...")
        for new_db_group_id in df['temp_group'].dropna().unique():
            # Skip outliers
            if new_db_group_id == -1:
                df.loc[(df['temp_group'] == -1) & (df['existing_group'].isna()), 'group'] = None
                continue

            current_items = df[df['temp_group'] == new_db_group_id]
            reference_items = current_items[current_items['is_reference'] == True]
            
            if not reference_items.empty:
                group_counts = reference_items['existing_group'].value_counts()
                most_common_group = group_counts.idxmax()
                
                # Calculate max group ID to use for new groups if needed
                max_existing_group = df['existing_group'].dropna().max() if not df['existing_group'].dropna().empty else 0
                # Only consider numeric groups for max calculation to prevent type errors
                numeric_groups = pd.to_numeric(df['group'].dropna(), errors='coerce').dropna()
                max_assigned_new_group = numeric_groups.max() if not numeric_groups.empty else 0
                next_new_group_id = max(max_existing_group, max_assigned_new_group) + 1
                
                # STRATEGY 1: Try to find alternative groups for large groups
                if most_common_group in large_groups:
                    # Look for alternative groups that aren't in large_groups
                    alternative_found = False
                    if len(group_counts) > 1:
                        # Sort by count descending (but exclude large groups)
                        for group_id, count in sorted(group_counts.items(), key=lambda x: x[1], reverse=True):
                            if group_id not in large_groups:
                                target_existing_group = group_id
                                print(f"ℹ️ Using alternative group {target_existing_group} instead of large group {most_common_group}")
                                alternative_found = True
                                break
                    
                    # STRATEGY 2: If no alternative, check similarity threshold
                    if not alternative_found:
                        # Calculate average similarity within the cluster
                        texts = current_items['title'] + " " + current_items['scraped_description']
                        embeddings = np.array([np.array(emb) if isinstance(emb, list) else emb 
                                           for emb in current_items['embedding'].values if emb is not None])
                        
                        # Use a high threshold for large groups to prevent frequent updates
                        similarity_threshold = 0.9 if most_common_group in large_groups else 0.7
                        
                        if len(embeddings) >= 2:
                            # Calculate pairwise similarities
                            similarities = []
                            for i in range(len(embeddings)):
                                for j in range(i+1, len(embeddings)):
                                    sim = np.dot(embeddings[i], embeddings[j])
                                    similarities.append(sim)
                            
                            avg_similarity = sum(similarities) / len(similarities) if similarities else 0
                            
                            # Only assign to large group if similarity is very high
                            if avg_similarity > similarity_threshold:
                                target_existing_group = most_common_group
                                print(f"ℹ️ High similarity ({avg_similarity:.3f}) - assigning to large group {most_common_group}")
                            else:
                                # Create new group instead
                                target_existing_group = next_new_group_id
                                print(f"ℹ️ Low similarity ({avg_similarity:.3f}) - creating new group {next_new_group_id}")
                        else:
                            # Not enough embeddings to calculate similarity, use default assignment
                            target_existing_group = next_new_group_id
                    else:
                        # We found an alternative group already
                        pass
                        
                    # STRATEGY 3: Consider sub-clustering for large groups with enough items
                    if target_existing_group in large_groups and len(current_items) > MIN_SUBDIVISION_SIZE:
                        try:
                            # Extract embeddings for topic modeling
                            embeddings_for_topics = np.array([np.array(emb) if isinstance(emb, list) else emb 
                                                         for emb in current_items['embedding'].values if emb is not None])
                            
                            if len(embeddings_for_topics) > MIN_SUBDIVISION_SIZE: # Ensure enough items for sub-clustering
                                # Use K-means for sub-clustering (a simple topic modeling approach)
                                from sklearn.cluster import KMeans
                                num_topics = min(3, len(embeddings_for_topics) // 2)  # Reasonable number of sub-topics
                                
                                if num_topics >= 2:
                                    kmeans = KMeans(n_clusters=num_topics, random_state=42)
                                    subtopic_labels = kmeans.fit_predict(embeddings_for_topics)
                                    
                                    # Create mapping of item_id to subtopic
                                    item_to_subtopic = {item_id: subtopic for item_id, subtopic in 
                                                      zip(current_items['id'].values, subtopic_labels)}
                                    
                                    # FIXED: Use integer subgroups instead of hierarchical strings
                                    target_group_base = int(target_existing_group)
                                    # Create new groups for each subtopic
                                    for item_id, subtopic in item_to_subtopic.items():
                                        new_group_id = next_new_group_id + subtopic
                                        df.loc[df['id'] == item_id, 'group'] = new_group_id
                                    
                                    print(f"ℹ️ Subdivided large group {target_existing_group} into {num_topics} separate groups")
                                    continue  # Skip the regular assignment below
                        except Exception as e:
                            print(f"⚠️ Error in topic modeling: {str(e)}")
                            # Fall back to regular assignment
                else:
                    # Not a large group, use normal assignment
                    target_existing_group = most_common_group
                    
                # Regular assignment for cases not handled by strategies above
                df.loc[(df['temp_group'] == new_db_group_id) & (df['group'].isna()), 'group'] = target_existing_group
                print(f"ℹ️ Assigned DBSCAN group {new_db_group_id} to existing group {target_existing_group}.")
                
                # Track that we've used this group
                groups_used_this_run.add(target_existing_group)
            else:
                # Assign new unique group ID for clusters without reference items
                max_existing_group = df['existing_group'].dropna().max() if not df['existing_group'].dropna().empty else -1
                # Only consider numeric groups to avoid type errors
                numeric_groups = pd.to_numeric(df['group'].dropna(), errors='coerce').dropna()
                max_assigned_new_group = numeric_groups.max() if not numeric_groups.empty else -1
                next_new_group_id = max(max_existing_group, max_assigned_new_group) + 1
                df.loc[(df['temp_group'] == new_db_group_id) & (df['group'].isna()), 'group'] = next_new_group_id
    else:
        print("ℹ️ No reference news. Assigning DBSCAN groups directly.")
        df.loc[df['group'].isna(), 'group'] = df['temp_group']
        df.loc[df['group'] == -1, 'group'] = None

    # Ensure reference items keep original groups
    if has_reference_news:
        df.loc[df['is_reference'] == True, 'group'] = df['existing_group']

    # Clean up temp column
    df.drop(columns=['temp_group'], inplace=True, errors='ignore')

def process_results(df):
    """
    Process final results, handling deduplication and edge cases
    """
    result = []
    processed_ids_for_result = set()

    # Process news by final groups
    unique_final_groups = df["group"].dropna().unique()

    for group_id in unique_final_groups:
        group_df = df[df["group"] == group_id]
        
        # Handle single news item in group case
        if len(group_df) == 1 and not group_df.iloc[0]["is_reference"]:
            item_row = group_df.iloc[0]
            result.append({
                "id": item_row["id"], "group": None, "title": item_row["title"],
                "scraped_description": item_row["scraped_description"], 
                "description": item_row.get("description", ""),
                "source_medium": item_row["source_medium"]
            })
            processed_ids_for_result.add(item_row["id"])
            continue

        seen_media_in_group = set()
        current_group_items_for_result = []

        # Process reference items first
        reference_items_in_final_group = group_df[group_df["is_reference"] == True]
        for _, item_row in reference_items_in_final_group.iterrows():
            if item_row["source_medium"] not in seen_media_in_group:
                current_group_items_for_result.append({
                    "id": item_row["id"], 
                    "group": group_id, 
                    "title": item_row["title"],
                    "scraped_description": item_row["scraped_description"],
                    "description": item_row.get("description", ""),
                    "source_medium": item_row["source_medium"]
                })
                seen_media_in_group.add(item_row["source_medium"])
                processed_ids_for_result.add(item_row["id"])
        
        # Then non-reference items
        non_reference_items_in_final_group = group_df[group_df["is_reference"] == False]
        for _, item_row in non_reference_items_in_final_group.iterrows():
            if item_row["id"] not in processed_ids_for_result and item_row["source_medium"] not in seen_media_in_group:
                current_group_items_for_result.append({
                    "id": item_row["id"], 
                    "group": group_id, 
                    "title": item_row["title"],
                    "scraped_description": item_row["scraped_description"],
                    "description": item_row.get("description", ""),
                    "source_medium": item_row["source_medium"]
                })
                seen_media_in_group.add(item_row["source_medium"])
                processed_ids_for_result.add(item_row["id"])

        # Handle groups with fewer than 2 items after deduplication
        if len(current_group_items_for_result) < 2 and not any(item['id'] in reference_items_in_final_group['id'].values for item in current_group_items_for_result):
            for item_dict in current_group_items_for_result:
                item_dict["group"] = None
                result.append(item_dict)
        else:
            result.extend(current_group_items_for_result)

    # Add any remaining ungrouped items
    for index, row in df.iterrows():
        if row["id"] not in processed_ids_for_result:
            result.append({
                "id": row["id"], 
                "group": row["group"],
                "title": row["title"], 
                "scraped_description": row["scraped_description"],
                "description": row.get("description", ""),
                "source_medium": row["source_medium"]
            })
    
    # Final check for all items having None as group
    all_groups_are_none = all(r.get("group") is None for r in result)
    if all_groups_are_none and result:
        print("ℹ️ All items remained ungrouped after processing. Assigning unique group IDs as a fallback.")
        for i, item_dict in enumerate(result):
            item_dict["group"] = i

    return result

def extract_titles_and_descriptions(df_embeddings):
    titles = df_embeddings["title"].fillna("")
            
            # Prioritize 'scraped_description', then 'description', then empty string
            # Check if 'scraped_description' column exists
    if "scraped_description" in df_embeddings.columns:
        desc1 = df_embeddings["scraped_description"].fillna("")
    else:
        desc1 = pd.Series([""] * len(df_embeddings), index=df_embeddings.index) # Series of empty strings

            # Check if 'description' column exists
    if "description" in df_embeddings.columns:
        desc2 = df_embeddings["description"].fillna("")
    else:
        desc2 = pd.Series([""] * len(df_embeddings), index=df_embeddings.index) # Series of empty strings
                 
            # Use scraped_description if it's not empty, otherwise use description
            # If both are empty, it will result in an empty string for the description part.
    descriptions = desc1.where(desc1 != "", desc2)
    return titles,descriptions
def get_news_not_embedded(input_df: pd.DataFrame) -> list:
    """
    Filters a DataFrame to get news items that do not have an 'embedding' field 
    or where 'embedding' is null/NaN or an empty list/array.
    Returns a list of dictionaries for items needing embeddings.
    """
    news_needing_embedding = []
    
    for index, row in input_df.iterrows():
        embedding_value = row.get("embedding") 
        
        embedding_is_present_and_valid = False # Default to False

        if isinstance(embedding_value, (list, np.ndarray)):
            # It's a list or array, check if it's a valid, non-empty embedding
            if len(embedding_value) > 0:
                if isinstance(embedding_value, np.ndarray) and np.all(pd.isna(embedding_value)):
                    # It's an array of all NaNs, not valid
                    embedding_is_present_and_valid = False
                else:
                    # It's a non-empty list/array, not all NaNs
                    embedding_is_present_and_valid = True
            # else: it's an empty list/array, so embedding_is_present_and_valid remains False
        
        # If it's not a list/array, then it's a scalar (or None)
        # We only consider it "present and valid" if it passed the list/array checks above.
        # If it's None, or a scalar NaN, or any other scalar type (string, number),
        # it's not a valid embedding for our purposes here, so embedding_is_present_and_valid
        # would have remained False from its initialization or the list/array checks.

        if not embedding_is_present_and_valid:
            # This row needs an embedding because it's None, NaN, an empty list/array,
            # an array of all NaNs, or some other non-list/array scalar.
            data_dict = row.to_dict()

            # Ensure 'id' is present
            if "id" not in data_dict or pd.isna(data_dict.get("id")):
                # print(f"Warning: Item at index {index} missing 'id'. Skipping.")
                continue 

            # Ensure 'scraped_description' or 'description' is present
            if pd.isna(data_dict.get("scraped_description")) and pd.isna(data_dict.get("description")):
                # print(f"Warning: Item with ID {data_dict.get('id')} missing description. Skipping.")
                continue

            news_needing_embedding.append(data_dict)
            
    print(f"get_news_not_embedded: Identified {len(news_needing_embedding)} news items to process for embeddings.")
    return news_needing_embedding