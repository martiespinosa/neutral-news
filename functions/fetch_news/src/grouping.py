import os
import traceback
import time
from .storage import get_all_embeddings
from .storage import update_news_embedding
from .storage import get_news_not_embedded
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
        # Load NLP modules when needed, not at import time
        _load_nlp_modules()
        
        # Convert to DataFrame
        print("ℹ️ Converting List to DataFrame...")
        df = pd.DataFrame(news_list)

        # Check that the required columns exist
        if "id" not in df.columns or "title" not in df.columns or "scraped_description" not in df.columns:
            raise ValueError("The JSON must contain the columns 'id', 'title' and 'scraped_description' with the text of the news")
        
        # Prepare column for new groups
        df["group"] = None 
        
        print("ℹ️ Checking for existing groups...")
        # Preserve existing groups
        has_reference_news = "existing_group" in df.columns
        if has_reference_news:
            # Copy existing groups to group
            df.loc[df["existing_group"].notna(), "group"] = df.loc[df["existing_group"].notna(), "existing_group"]
            
            # Identify news that already have a group (references) and those that don't (to group)
            reference_mask = df["existing_group"].notna()
            df["is_reference"] = reference_mask
            
            # Count how many news items need to be grouped
            to_group_count = (~reference_mask).sum()
            
            # If all news already have a group, there's nothing to do
            if to_group_count == 0:
                return df[["id", "group"]].to_dict(orient='records')
        else:
            df["is_reference"] = False
        print(f"ℹ️ Found {df['is_reference'].sum()} reference news and {len(df[~df['is_reference']])} news to group.")
        
        print("ℹ️ Assigning a new group to news without a reference...")
        # If there's only one news item to group, assign a new group
        if len(df[~df["is_reference"]]) <= 1 and not has_reference_news:
            df.loc[~df["is_reference"], "group"] = 0
            return df[["id", "group"]].to_dict(orient='records')
        
        df_embeddings = pd.DataFrame(get_news_not_embedded(df))        

        # STEP 1: Generate embeddings for new news items only
        if len(df_embeddings) > 0:
            print("ℹ️ Loading embeddings model...")

            # Get model with retry support
            model = get_sentence_transformer_model()
            
            print("ℹ️ Extracting titles and descriptions...")
            titles, descriptions = extract_titles_and_descriptions(df_embeddings)
            df_embeddings["noticia_completa"] = titles + " " + descriptions
            
            print("ℹ️ Generating embeddings for new news items...")
            texts_to_encode = df_embeddings["noticia_completa"].tolist()
            news_ids = df_embeddings["id"].tolist()  # Extract IDs to pair with embeddings
            total_texts = len(texts_to_encode)
            batch_size = 256
            embeddings_list = []
            processed_ids = []  # To store IDs in the same order as embeddings
            start_time_embed = time.time()
            processed_count = 0
            next_log_percentage = 10 # Start logging at 10%

            for i in range(0, total_texts, batch_size):
                batch = texts_to_encode[i:min(i + batch_size, total_texts)]
                batch_ids = news_ids[i:min(i + batch_size, total_texts)]  # Get corresponding IDs for the batch
                # Ensure model.encode is called without its internal progress bar for cleaner logs
                batch_embeddings = model.encode(
                    batch,
                    convert_to_numpy=True,
                    show_progress_bar=False  # Disable sentence-transformers internal bar
                )
                embeddings_list.append(batch_embeddings)
                processed_ids.extend(batch_ids)  # Append batch IDs to the processed list
                processed_count = min(i + batch_size, total_texts)

                # Check if the current progress crossed the next logging threshold
                current_percentage = (processed_count / total_texts) * 100
                if current_percentage >= next_log_percentage:
                    elapsed_time = time.time() - start_time_embed
                    log_perc = int(next_log_percentage)
                    print(f"⏳ Embeddings: {log_perc}% complete ({processed_count}/{total_texts} texts). Time elapsed: {elapsed_time:.2f} seconds.")
                    next_log_percentage = min(log_perc + 10, 100)
                    while current_percentage >= next_log_percentage and next_log_percentage <= 100:
                        next_log_percentage += 10

            # Concatenate embeddings from all batches
            if embeddings_list:
                new_embeddings = np.vstack(embeddings_list)
                end_time_embed = time.time()
                # Final log message remains useful
                print(f"✅ Embeddings generated for {total_texts} texts in {end_time_embed - start_time_embed:.2f} seconds.")
                
                # Save the raw embeddings to Firestore
                embeddings_for_storage = [emb.tolist() for emb in new_embeddings]
                
                print("ℹ️ Saving new embeddings to Firestore...")
                updated_count = update_news_embedding(processed_ids, embeddings_for_storage)
                print(f"✅ Successfully saved {updated_count} embeddings to Firestore.")
            
        # STEP 2: Fetch ALL embeddings from storage (including the ones we just saved)
        print("ℹ️ Fetching ALL embeddings from storage...")
        embeddings_data = get_all_embeddings()
        
        if not embeddings_data or len(embeddings_data) == 0:
            print("❌ No embeddings available for clustering")
            return df[["id", "group"]].to_dict(orient='records')
            
        # Convert embeddings data to numpy array
        embeddings = np.array(embeddings_data)
        
        # STEP 3: Normalize ALL embeddings
        print("ℹ️ Normalizing ALL embeddings for cosine similarity...")
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1e-10  # Avoid division by zero
        embeddings_norm = embeddings / norms
        
        print("ℹ️ Calculating nearest neighbors graph...")
        # Nearest neighbors model
        n_neighbors = min(5, len(df))  # Number of neighbors to consider
        # Ensure n_neighbors is not larger than the number of samples
        effective_n_neighbors = min(n_neighbors, embeddings_norm.shape[0])
        nbrs = NearestNeighbors(n_neighbors=effective_n_neighbors, metric="cosine").fit(embeddings_norm)

        # Build sparse distance matrix directly using kneighbors_graph
        # mode='distance' gives the cosine distance (1 - similarity), which DBSCAN needs
        dist_matrix_sparse = nbrs.kneighbors_graph(
            embeddings_norm,
            n_neighbors=effective_n_neighbors,
            mode='distance'
        )
        # Sort the sparse graph for DBSCAN efficiency
        print("ℹ️ Sorting sparse distance graph...")
        dist_matrix_sparse_sorted = sort_graph_by_row_values(dist_matrix_sparse)
        
        print("ℹ️ Applying DBSCAN algorithm...")
        # Parameters for clustering
        eps = 0.25  # Distance threshold
        min_samples = 2  # Minimum number of samples in a cluster
        
        # Apply DBSCAN with the precomputed *sorted* sparse distance matrix
        clustering = DBSCAN(eps=eps, min_samples=min_samples, metric="precomputed")
        # Pass the sorted graph directly
        group_labels = clustering.fit_predict(dist_matrix_sparse_sorted)

        # Assign groups only to news that don't have one
        temp_group_column = "temp_group"
        df[temp_group_column] = group_labels
        
        # Map new groups to existing ones when there are matches
        if has_reference_news:
            group_mapping = {}
            for new_group in np.unique(group_labels):
                if new_group == -1:  # Skip noise/outliers
                    continue
                    
                # Find news in this new temporary group
                group_items = df[df[temp_group_column] == new_group]
                
                # Check if any have an existing group
                ref_items = group_items[group_items["is_reference"]]
                if len(ref_items) > 0:
                    existing_groups = ref_items["existing_group"].unique()
                    
                    # If there are multiple existing groups, choose the most frequent
                    if len(existing_groups) > 1:
                        counts = ref_items["existing_group"].value_counts()
                        most_common = counts.idxmax()
                        group_mapping[new_group] = most_common
                    else:
                        group_mapping[new_group] = existing_groups[0]
            
            # Apply the mapping where necessary
            for idx, row in df.iterrows():
                if not row["is_reference"]:
                    temp_group = row[temp_group_column]
                    if temp_group in group_mapping:
                        # Use mapped existing group
                        df.at[idx, "group"] = group_mapping[temp_group]
                    elif temp_group != -1:
                        # Create new group for clusters without mapping
                        # Find the maximum existing group and add 1
                        if df["group"].notna().any():
                            max_group = df["group"].max()
                            if max_group is not None:
                                new_group_id = int(max_group) + 1
                            else:
                                new_group_id = 0
                        else:
                            new_group_id = 0
                            
                        # Assign new ID to the entire cluster
                        mask = (df[temp_group_column] == temp_group) & (~df["is_reference"])
                        df.loc[mask, "group"] = new_group_id
        else:
            # If there are no reference news, simply assign DBSCAN groups
            df["group"] = df[temp_group_column]
            df.loc[df["group"] == -1, "group"] = None
        
        # New post-processing to remove duplicates by medium
        result = []
        
        # Process news by groups
        for group in df["group"].unique():
            if pd.isna(group):
                continue
                
            # Filter news in this group
            group_df = df[df["group"] == group]
            
            # If there's only one news item in the group and it's not a reference, leave it ungrouped
            if len(group_df) < 2 and not any(group_df["is_reference"]):
                for _, row in group_df.iterrows():
                    result.append({
                        "id": row["id"],
                        "group": group,
                        "title": row["title"],
                        "scraped_description": row["scraped_description"],
                        "source_medium": row["source_medium"]
                    })
                continue
            
            # Track seen media
            seen_media = set()
            filtered_group = []
            
            # First include reference news
            for _, row in group_df[group_df["is_reference"]].iterrows():
                if row["source_medium"] not in seen_media:
                    seen_media.add(row["source_medium"])
                    filtered_group.append(row)
            
            # Then include new news
            for _, row in group_df[~group_df["is_reference"]].iterrows():
                if row["source_medium"] not in seen_media:
                    seen_media.add(row["source_medium"])
                    filtered_group.append(row)
            
            # If there are fewer than 2 news items after removing duplicates, ignore group
            # unless there are already reference news
            if len(filtered_group) < 2 and not any(row["is_reference"] for row in filtered_group):
                for row in filtered_group:
                    result.append({
                        "id": row["id"],
                        "group": None,
                        "title": row["title"],
                        "scraped_description": row["scraped_description"],
                        "source_medium": row["source_medium"]
                    })
            else:
                for row in filtered_group:
                    result.append({
                        "id": row["id"],
                        "group": group,
                        "title": row["title"],
                        "scraped_description": row["scraped_description"],
                        "source_medium": row["source_medium"]
                    })
        
        # Include news that were left ungrouped (outliers)
        for _, row in df[pd.isna(df["group"])].iterrows():
            result.append({
                "id": row["id"],
                "group": None,
                "title": row["title"],
                "scraped_description": row["scraped_description"],
                "source_medium": row["source_medium"]
            })
        
        # If no groups with more than one news item remain, assign individual groups
        if not any(r["group"] is not None for r in result):
            for i, r in enumerate(result):
                r["group"] = i

        print("✅ Grouping completed successfully")
        return result
    
    except Exception as e:
        print(f"❌ Error in group_news: {str(e)}")
        traceback.print_exc()
        raise

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
