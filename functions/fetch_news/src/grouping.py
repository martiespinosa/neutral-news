import os
import traceback
import time
from .storage import get_all_embeddings
from .storage import update_news_embedding
import pandas as pd
import numpy as np
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
def group_news(news_list: list):
    """
    Groups news based on their semantic similarity
    """
    try:
        print("ℹ️ Starting news grouping...")
        _load_nlp_modules()
        
        print("ℹ️ Converting List to DataFrame...")
        df = pd.DataFrame(news_list)

        if "id" not in df.columns or "title" not in df.columns or "scraped_description" not in df.columns:
            raise ValueError("The JSON must contain the columns 'id', 'title' and 'scraped_description' with the text of the news")
        
        df["group"] = None 
        
        print("ℹ️ Checking for existing groups...")
        has_reference_news = "existing_group" in df.columns
        if has_reference_news:
            df.loc[df["existing_group"].notna(), "group"] = df.loc[df["existing_group"].notna(), "existing_group"]
            reference_mask = df["existing_group"].notna()
            df["is_reference"] = reference_mask
            to_group_count = (~reference_mask).sum()
            if to_group_count == 0:
                print("ℹ️ All news items already have groups. No new grouping needed.")
                return df[["id", "group", "title", "scraped_description", "source_medium"]].to_dict(orient='records')
        else:
            df["is_reference"] = False
            
        print(f"ℹ️ Found {df['is_reference'].sum()} reference news and {len(df[~df['is_reference']])} news to group.")
        
        # Handle cases with very few items to group early
        items_to_potentially_group_df = df[~df["is_reference"]]
        if len(items_to_potentially_group_df) == 0 and has_reference_news:
            print("ℹ️ No new items to group, only reference news present.")
            return df[["id", "group", "title", "scraped_description", "source_medium"]].to_dict(orient='records')
        if len(items_to_potentially_group_df) <= 1 and not has_reference_news:
            print("ℹ️ Only one new item to group and no reference news. Assigning to group 0.")
            df.loc[~df["is_reference"], "group"] = 0
            return df[["id", "group", "title", "scraped_description", "source_medium"]].to_dict(orient='records')

        # Prepare a DataFrame that will hold all items from the input 'df'
        # and their corresponding embeddings.
        # We need to ensure the order of embeddings matches the order of 'df'.
        
        all_items_for_clustering_df = df.copy()
        all_items_for_clustering_df['embedding_vector'] = None # Initialize column for actual vectors

        # STEP 1: Generate embeddings for items in df that need them
        # get_news_not_embedded filters 'df' to find items missing embeddings
        df_needing_embeddings = pd.DataFrame(get_news_not_embedded(df.copy())) # Pass a copy to avoid modification issues

        if not df_needing_embeddings.empty:
            print(f"ℹ️ Found {len(df_needing_embeddings)} items needing new embeddings.")
            print("ℹ️ Loading embeddings model...")
            model = get_sentence_transformer_model()
            
            print("ℹ️ Extracting titles and descriptions for new embeddings...")
            # Ensure 'df_needing_embeddings' has the necessary columns
            if not all(col in df_needing_embeddings.columns for col in ["title", "id"]):
                 raise ValueError("DataFrame for new embeddings is missing 'title' or 'id'.")

            titles, descriptions = extract_titles_and_descriptions(df_needing_embeddings)
            df_needing_embeddings["noticia_completa"] = titles + " " + descriptions
            
            print("ℹ️ Generating new embeddings...")
            texts_to_encode = df_needing_embeddings["noticia_completa"].tolist()
            news_ids_for_new_embeddings = df_needing_embeddings["id"].tolist()
            
            if texts_to_encode:
                # Generate embeddings (using your existing batching logic)
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

                    # Add these newly generated embeddings to our main 'all_items_for_clustering_df'
                    # and to the original 'df'
                    for idx, news_id in enumerate(news_ids_for_new_embeddings):
                        current_embedding_np = new_embeddings_np[idx]
                        current_embedding_list = current_embedding_np.tolist()

                        # Update 'all_items_for_clustering_df.embedding_vector'
                        # Each cell should store a list containing the numpy array: [np.array(...)]
                        target_indices_all_items = all_items_for_clustering_df[all_items_for_clustering_df['id'] == news_id].index
                        for i_loc in target_indices_all_items:
                            all_items_for_clustering_df.at[i_loc, 'embedding_vector'] = [current_embedding_np]
                        
                        # Update 'df.embedding'
                        # Each cell should store the flat list of floats: [float, float, ...]
                        df.loc[df['id'] == news_id, 'embedding'] = current_embedding_list


        # STEP 2: Populate 'embedding_vector' for items in 'all_items_for_clustering_df'
        # that already had embeddings (from the input 'news_list'/'df')
        print("ℹ️ Populating existing embeddings for clustering...")
        for index, row in all_items_for_clustering_df.iterrows():
            if row['embedding_vector'] is None: # If not populated by new embeddings
                if 'embedding' in row and row['embedding'] is not None and isinstance(row['embedding'], list) and len(row['embedding']) > 0:
                    all_items_for_clustering_df.at[index, 'embedding_vector'] = [np.array(row['embedding'])]
                else:
                    # This case should ideally be caught by get_news_not_embedded if an item truly needs an embedding
                    print(f"⚠️ Item with ID {row['id']} has no new or existing valid embedding. It will be excluded from clustering if this persists.")
                    all_items_for_clustering_df.at[index, 'embedding_vector'] = [np.zeros(get_sentence_transformer_model().get_sentence_embedding_dimension())] # Placeholder, or handle exclusion

        # Filter out rows where embedding_vector could not be set (should be rare if logic is correct)
        all_items_for_clustering_df.dropna(subset=['embedding_vector'], inplace=True)
        
        if all_items_for_clustering_df.empty:
            print("❌ No items with embeddings available for clustering.")
            return df[["id", "group", "title", "scraped_description", "source_medium"]].to_dict(orient='records')

        # Extract the list of embedding vectors for clustering
        # The 'embedding_vector' column now stores lists containing single numpy arrays. We need to stack them.
        embeddings_for_clustering_np = np.vstack(all_items_for_clustering_df['embedding_vector'].apply(lambda x: x[0]).tolist())

        if embeddings_for_clustering_np.shape[0] == 0:
            print("❌ No embeddings available for clustering after processing.")
            return df[["id", "group", "title", "scraped_description", "source_medium"]].to_dict(orient='records')
        
        # STEP 3: Normalize embeddings for cosine similarity
        print("ℹ️ Normalizing embeddings for cosine similarity...")
        norms = np.linalg.norm(embeddings_for_clustering_np, axis=1, keepdims=True)
        norms[norms == 0] = 1e-10
        embeddings_norm = embeddings_for_clustering_np / norms
        
        print("ℹ️ Calculating nearest neighbors graph...")
        n_neighbors = min(5, embeddings_norm.shape[0])
        if n_neighbors < 2 and embeddings_norm.shape[0] > 1 : # DBSCAN needs at least 2 samples for meaningful neighbors
            n_neighbors = 2 
        elif embeddings_norm.shape[0] <=1: # Not enough samples to cluster
             print("ℹ️ Not enough samples to perform clustering. Assigning all to group 0 or existing groups.")
             if not has_reference_news and embeddings_norm.shape[0] == 1:
                 all_items_for_clustering_df['group'] = 0
             # Update original df based on all_items_for_clustering_df's groups
             for index, row_clustered in all_items_for_clustering_df.iterrows():
                 df.loc[df['id'] == row_clustered['id'], 'group'] = row_clustered['group']
             return df[["id", "group", "title", "scraped_description", "source_medium"]].to_dict(orient='records')


        nbrs = NearestNeighbors(n_neighbors=n_neighbors, metric="cosine").fit(embeddings_norm)
        dist_matrix_sparse = nbrs.kneighbors_graph(embeddings_norm, n_neighbors=n_neighbors, mode='distance')
        
        print("ℹ️ Sorting sparse distance graph...")
        dist_matrix_sparse_sorted = sort_graph_by_row_values(dist_matrix_sparse)
        
        print("ℹ️ Applying DBSCAN algorithm...")
        eps = 0.25
        min_samples = 2
        
        clustering = DBSCAN(eps=eps, min_samples=min_samples, metric="precomputed")
        group_labels = clustering.fit_predict(dist_matrix_sparse_sorted)

        # Now, group_labels has the same length as all_items_for_clustering_df
        all_items_for_clustering_df["temp_group"] = group_labels
        
        # Map these temp_groups back to the original df
        # Create a mapping from id to temp_group
        id_to_temp_group_map = pd.Series(all_items_for_clustering_df.temp_group.values, index=all_items_for_clustering_df.id).to_dict()

        # Apply this map to the original df
        # For items in df that were clustered, assign their new temp_group
        # For items in df that were NOT in all_items_for_clustering_df (e.g. excluded due to no embedding), their group remains as is (likely None or existing_group)
        df['temp_group'] = df['id'].map(id_to_temp_group_map)


        # --- Start of existing group mapping and post-processing logic ---
        # This part needs to operate on 'df' which now has 'temp_group' for clustered items
        # and 'group' for pre-existing groups.

        if has_reference_news:
            print("ℹ️ Mapping new DBSCAN clusters to existing reference groups...")
            # Iterate over unique temporary DBSCAN groups
            for new_db_group_id in df['temp_group'].dropna().unique():
                if new_db_group_id == -1: # Outliers from DBSCAN
                    # For items marked as outliers by DBSCAN, if they don't have an existing_group, set their final group to None
                    df.loc[(df['temp_group'] == -1) & (df['existing_group'].isna()), 'group'] = None
                    continue

                # News items belonging to this new DBSCAN group
                current_dbscan_group_items_df = df[df['temp_group'] == new_db_group_id]

                # Of these, find items that are references (have an existing_group)
                reference_items_in_dbscan_group = current_dbscan_group_items_df[current_dbscan_group_items_df['is_reference'] == True]

                if not reference_items_in_dbscan_group.empty:
                    # If there are reference items, find the most common existing_group among them
                    # (or the first one if you prefer, assuming references in a DBSCAN cluster should share the same original group)
                    target_existing_group = reference_items_in_dbscan_group['existing_group'].mode()[0]
                    
                    # Assign all items in this DBSCAN group (that don't already have a group) to this target_existing_group
                    df.loc[(df['temp_group'] == new_db_group_id) & (df['group'].isna()), 'group'] = target_existing_group
                else:
                    # No reference items in this DBSCAN group. This is a new cluster of non-reference items.
                    # We need to assign a new, unique group ID to them.
                    # These new group IDs must not conflict with existing_group IDs or other new group IDs.
                    # Find the max existing group ID and max new group ID assigned so far.
                    max_existing_group = df['existing_group'].dropna().max() if not df['existing_group'].dropna().empty else -1
                    max_assigned_new_group = df.loc[df['temp_group'] != new_db_group_id, 'group'].dropna().max() if not df.loc[df['temp_group'] != new_db_group_id, 'group'].dropna().empty else -1
                    next_new_group_id = max(max_existing_group, max_assigned_new_group) + 1
                    
                    df.loc[(df['temp_group'] == new_db_group_id) & (df['group'].isna()), 'group'] = next_new_group_id
        else: # No reference news at all
            print("ℹ️ No reference news. Assigning DBSCAN groups directly.")
            # Assign DBSCAN groups to items that don't have a group yet (which is all of them in this branch)
            df.loc[df['group'].isna(), 'group'] = df['temp_group']
            # DBSCAN outliers (-1) become None (ungrouped)
            df.loc[df['group'] == -1, 'group'] = None


        # Ensure all items that were initially reference items retain their original group
        if has_reference_news:
            df.loc[df['is_reference'] == True, 'group'] = df['existing_group']

        # Clean up temp column
        df.drop(columns=['temp_group'], inplace=True, errors='ignore')
        
        # --- Start of existing post-processing logic (remove duplicates by medium, etc.) ---
        # This logic should now correctly use the 'group' column populated above.
        result = []
        processed_ids_for_result = set()

        # Process news by final groups
        unique_final_groups = df["group"].dropna().unique()

        for group_id in unique_final_groups:
            group_df = df[df["group"] == group_id]
            
            # If there's only one news item in the group AND it's not a reference item,
            # AND it wasn't part of a larger DBSCAN cluster that got reduced to 1 by deduplication,
            # then consider making it ungrouped (group = None).
            # This needs careful thought: if DBSCAN put it alone, it's an outlier.
            # If it was with others but deduplication isolated it, it might still be related.
            # For now, if a group has only one non-reference item, let's ungroup it.
            if len(group_df) == 1 and not group_df.iloc[0]["is_reference"]:
                item_row = group_df.iloc[0]
                result.append({
                    "id": item_row["id"], "group": None, "title": item_row["title"],
                    "scraped_description": item_row["scraped_description"], "source_medium": item_row["source_medium"]
                })
                processed_ids_for_result.add(item_row["id"])
                continue # Move to the next group_id

            seen_media_in_group = set()
            current_group_items_for_result = []

            # Prioritize reference items for deduplication
            reference_items_in_final_group = group_df[group_df["is_reference"] == True]
            for _, item_row in reference_items_in_final_group.iterrows():
                if item_row["source_medium"] not in seen_media_in_group:
                    current_group_items_for_result.append({
                        "id": item_row["id"], "group": group_id, "title": item_row["title"],
                        "scraped_description": item_row["scraped_description"], "source_medium": item_row["source_medium"]
                    })
                    seen_media_in_group.add(item_row["source_medium"])
                    processed_ids_for_result.add(item_row["id"])
            
            # Add non-reference items, avoiding duplicate media
            non_reference_items_in_final_group = group_df[group_df["is_reference"] == False]
            for _, item_row in non_reference_items_in_final_group.iterrows():
                if item_row["id"] not in processed_ids_for_result: # Ensure not already added as a reference
                    if item_row["source_medium"] not in seen_media_in_group:
                        current_group_items_for_result.append({
                            "id": item_row["id"], "group": group_id, "title": item_row["title"],
                            "scraped_description": item_row["scraped_description"], "source_medium": item_row["source_medium"]
                        })
                        seen_media_in_group.add(item_row["source_medium"])
                        processed_ids_for_result.add(item_row["id"])

            # If after deduplication, a group has less than 2 items AND no reference items were part of it,
            # then ungroup these items.
            if len(current_group_items_for_result) < 2 and not any(item['id'] in reference_items_in_final_group['id'].values for item in current_group_items_for_result):
                for item_dict in current_group_items_for_result:
                    item_dict["group"] = None # Ungroup them
                    result.append(item_dict)
            else:
                result.extend(current_group_items_for_result)

        # Add any remaining items from df that were not processed (e.g., initially ungrouped and stayed ungrouped)
        for index, row in df.iterrows():
            if row["id"] not in processed_ids_for_result:
                result.append({
                    "id": row["id"], "group": row["group"], # Use its current group (could be None)
                    "title": row["title"], "scraped_description": row["scraped_description"],
                    "source_medium": row["source_medium"]
                })
        
        # Final check: if no groups were formed (all items have group=None),
        # assign unique group IDs to each item to prevent errors downstream if groups are expected.
        # This is a fallback.
        all_groups_are_none = all(r.get("group") is None for r in result)
        if all_groups_are_none and result:
            print("ℹ️ All items remained ungrouped after processing. Assigning unique group IDs as a fallback.")
            for i, item_dict in enumerate(result):
                item_dict["group"] = i


        print("✅ Grouping completed successfully")
        return result
    
    except Exception as e:
        print(f"❌ Error in group_news: {str(e)}")
        traceback.print_exc()
        # Instead of re-raising, return the current state of df or an empty list
        # to allow the main process to continue if possible, or handle more gracefully.
        # For now, returning what might be partially processed.
        if 'df' in locals() and isinstance(df, pd.DataFrame):
             return df[["id", "group", "title", "scraped_description", "source_medium"]].to_dict(orient='records')
        return [] # Fallback if df is not defined

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