import os
import traceback
from .storage import update_news_embedding, get_group_item_count, get_group_items, get_all_group_ids
import pandas as pd
import numpy as np

_model = None
_nlp_modules_loaded = False
MIN_VALID_SOURCES = 3

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
    return _model
def group_news(news_for_grouping: list) -> list:
    """
    Groups news based on their semantic similarity
    """
    try:
        print("ℹ️ Starting news grouping...")
        _load_nlp_modules()
        
        # Step 1: Setup DataFrame and handle references
        df, has_reference_news, should_return_early, early_result = setup_news_dataframe(news_for_grouping)
        if should_return_early:
            return early_result
        
        # Step 2: Process embeddings
        all_items_for_clustering_df, embeddings_norm = process_embeddings(df)
        
        # Step 3: Perform clustering if we have valid embeddings
        clustering_succeeded = perform_clustering(all_items_for_clustering_df, embeddings_norm, df, has_reference_news)
        if not clustering_succeeded:
            # Include existing_group in the early return
            result_columns = ["id", "group", "title", "scraped_description", "description", "source_medium"]
            if has_reference_news and "existing_group" in df.columns:
                result_columns.append("existing_group")
            return df[result_columns].to_dict(orient='records')
        
        # Step 4: Assign final group IDs
        assign_group_ids(df, has_reference_news)
        
        # Step 5: Process results and handle deduplication - preserve existing_group when present
        result = process_results(df, has_reference_news)
        
        print("✅ Grouping completed successfully")
        return result
    
    except Exception as e:
        print(f"❌ Error in group_news: {str(e)}")
        traceback.print_exc()
        if 'df' in locals() and isinstance(df, pd.DataFrame):
            result_columns = ["id", "group", "title", "scraped_description", "description", "source_medium"]
            if "existing_group" in df.columns:
                result_columns.append("existing_group")
            return df[result_columns].to_dict(orient='records')
        return []

def setup_news_dataframe(news_for_grouping: list) -> tuple:
    """
    Initial setup of the DataFrame and handling of reference news
    Returns a tuple of (df, has_reference_news, should_return_early, early_result)
    """
    df = pd.DataFrame(news_for_grouping)

    if "id" not in df.columns or "title" not in df.columns or "scraped_description" not in df.columns:
        raise ValueError("The JSON must contain the columns 'id', 'title' and 'scraped_description' with the text of the news")
    
    df["group"] = None 
    
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
    if n_neighbors < MIN_VALID_SOURCES and embeddings_norm.shape[0] > 1:
        n_neighbors = MIN_VALID_SOURCES 
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
    eps = 0.2125
    min_samples = MIN_VALID_SOURCES
    
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
    Assign final group IDs based on DBSCAN clusters and reference groups.
    Ensures no group exceeds MAX_GROUP_SIZE by subdividing when necessary.
    """
    # Configuration constants
    MAX_GROUP_SIZE = 25  # Maximum number of news items per group
    MIN_SUBDIVISION_SIZE = 5  # Minimum cluster size needed for subdivision
    SIMILARITY_THRESHOLD = 0.85  # Higher threshold for stricter clustering
    
    
    # Handle DBSCAN outliers first
    if has_reference_news:
        df.loc[(df['temp_group'] == -1) & (df['existing_group'].isna()), 'group'] = None
    else:
        df.loc[df['temp_group'] == -1, 'group'] = None
    
    # Initialize a set to track assigned groups
    all_group_ids = get_all_group_ids()
    # Process each DBSCAN cluster
    for db_cluster_id in df['temp_group'].dropna().unique():
        if db_cluster_id == -1:  # Skip outliers (already handled)
            continue
            
        # Get all items in this cluster
        cluster_items = df[df['temp_group'] == db_cluster_id]
        
        # Skip empty clusters (shouldn't happen but just in case)
        if cluster_items.empty:
            continue
            
        # Process with or without reference news
        if has_reference_news:
            _process_cluster_with_references(df, cluster_items, db_cluster_id, 
                                            MAX_GROUP_SIZE, MIN_SUBDIVISION_SIZE, 
                                            SIMILARITY_THRESHOLD, all_group_ids)
        else:
            _process_cluster_without_references(df, cluster_items, db_cluster_id, 
                                              MAX_GROUP_SIZE, MIN_SUBDIVISION_SIZE, all_group_ids)

    # Ensure reference items keep their original groups
    if has_reference_news:
        df.loc[df['is_reference'] == True, 'group'] = df['existing_group']
        
    # Clean up temporary column
    df.drop(columns=['temp_group'], inplace=True, errors='ignore')


def _process_cluster_with_references(df, cluster_items, db_cluster_id, 
                                    MAX_GROUP_SIZE, MIN_SUBDIVISION_SIZE, 
                                    SIMILARITY_THRESHOLD, all_group_ids):
    """Process a cluster that has reference news items."""
    # Find reference items in this cluster
    reference_items = cluster_items[cluster_items['is_reference'] == True]
    
    if reference_items.empty:
        # No reference items - check if subdivision is needed first
        next_group_id = _get_next_available_group_id(df, all_group_ids)
        
        if len(cluster_items) > MAX_GROUP_SIZE and len(cluster_items) > MIN_SUBDIVISION_SIZE:
            # Large enough for subdivision - directly create subgroups
            _subdivide_group(df, cluster_items, next_group_id, MAX_GROUP_SIZE, MIN_SUBDIVISION_SIZE)
            print(f"ℹ️ DBSCAN cluster {db_cluster_id} was subdivided based on new group ID {next_group_id}")
        else:
            # Not large enough for subdivision - assign single group ID
            df.loc[(df['temp_group'] == db_cluster_id) & (df['group'].isna()), 'group'] = next_group_id
            print(f"ℹ️ Assigned DBSCAN cluster {db_cluster_id} to new group {next_group_id}")
    else:
        # We have reference items - determine which group to use
        group_counts = reference_items['existing_group'].value_counts()
        target_group = group_counts.idxmax()  # Most common reference group
        
        # Get the total count of items in this target group from Firestore
        # This includes items not in our current dataframe
        total_items_in_group_from_db = get_group_item_count(target_group)
        
        # Count new non-reference items we're going to add
        new_non_reference_items = len(cluster_items[~cluster_items['is_reference']])
        
        # Calculate total items after assignment
        total_items_after_assignment = total_items_in_group_from_db + new_non_reference_items
        print(f"ℹ️ Target group {target_group} has {total_items_in_group_from_db} existing items in database")
        
        # Check if subdivision is needed based on total size
        if total_items_after_assignment > MAX_GROUP_SIZE and len(cluster_items) > MIN_SUBDIVISION_SIZE:
            print(f"ℹ️ Target group {target_group} would have {total_items_after_assignment} items after assignment, exceeding limit of {MAX_GROUP_SIZE}")
            
            # For subdivision, we need to get all existing items in this group
            # We'll handle this in the _subdivide_group function
            _subdivide_group_with_firestore(df, cluster_items, target_group, MAX_GROUP_SIZE, MIN_SUBDIVISION_SIZE, db_cluster_id)
        else:
            # Check if we should create a new group based on similarity
            similarity = _calculate_group_similarity(cluster_items)
            
            if similarity < SIMILARITY_THRESHOLD:
                # Low similarity - create a new group
                next_group_id = _get_next_available_group_id(df, all_group_ids)
                df.loc[(df['temp_group'] == db_cluster_id) & (df['group'].isna()), 'group'] = next_group_id
                target_group = next_group_id
                print(f"ℹ️ Low similarity ({similarity:.3f}) - created new group {next_group_id}")
            else:
                # High similarity - assign to target group
                df.loc[(df['temp_group'] == db_cluster_id) & (df['group'].isna()), 'group'] = target_group
                print(f"ℹ️ High similarity ({similarity:.3f}) - assigned to group {target_group}")
                
        all_group_ids.add(target_group)


def _process_cluster_without_references(df, cluster_items, db_cluster_id, 
                                       MAX_GROUP_SIZE, MIN_SUBDIVISION_SIZE, all_group_ids):
    """Process a cluster when there are no reference news items."""
        # Check if we need to subdivide this group
    next_group_id = _get_next_available_group_id(df, all_group_ids)
    if len(cluster_items) > MAX_GROUP_SIZE and len(cluster_items) > MIN_SUBDIVISION_SIZE:
        _subdivide_group(df, cluster_items, next_group_id, MAX_GROUP_SIZE, MIN_SUBDIVISION_SIZE)
    else: 
        df.loc[(df['temp_group'] == db_cluster_id) & (df['group'].isna()), 'group'] = next_group_id
        print(f"ℹ️ Assigned DBSCAN cluster {db_cluster_id} to new group {next_group_id}")

def _get_next_available_group_id(df, all_group_ids):
    """Calculate the next available group ID, ignoring 7-digit subdivision IDs."""
    # Get maximum existing group ID from database
    max_existing_group = 0
    
    # Retrieve all group IDs from the database
    if all_group_ids:
        # Convert to numeric, ignoring non-numeric values - convert set to list first
        numeric_ids = pd.to_numeric(pd.Series(list(all_group_ids)), errors='coerce').dropna()
        
        if not numeric_ids.empty:
            # Filter out 7-digit IDs (subdivision IDs)
            regular_ids = numeric_ids[numeric_ids < 1000000]
            if not regular_ids.empty:
                max_existing_group = regular_ids.max()
    
    # Also check the current DataFrame for any newly assigned IDs not yet in the database
    max_assigned_group = 0
    if 'group' in df.columns and not df['group'].dropna().empty:
        # Filter to only numeric values and exclude 7-digit IDs
        numeric_groups = pd.to_numeric(df['group'].dropna(), errors='coerce').dropna()
        if not numeric_groups.empty:
            # Filter out 7-digit IDs (subdivision IDs)
            regular_ids = numeric_groups[numeric_groups < 1000000]
            if not regular_ids.empty:
                max_assigned_group = regular_ids.max()
    
    # Return next available ID
    return max(int(max_existing_group), int(max_assigned_group)) + 1


def _calculate_group_similarity(items):
    """Calculate average cosine similarity between all embeddings in a group."""
    # Extract embeddings
    embeddings = np.array([
        np.array(emb) if isinstance(emb, list) else emb 
        for emb in items['embedding'].values 
        if emb is not None
    ])
    
    # If we don't have at least two embeddings, return default value
    if len(embeddings) < MIN_VALID_SOURCES:
        return 0.5  # Default middle value
        
    # Calculate pairwise similarities
    similarities = []
    for i in range(len(embeddings)):
        for j in range(i+1, len(embeddings)):
            sim = np.dot(embeddings[i], embeddings[j])
            similarities.append(sim)
    
    # Return average similarity
    return sum(similarities) / len(similarities) if similarities else 0.5


def _subdivide_group(df, items, base_group_id, MAX_GROUP_SIZE, MIN_SUBDIVISION_SIZE):
    """Subdivide a large group into smaller groups using K-means clustering."""
    try:
        # Extract embeddings
        embeddings = np.array([
            np.array(emb) if isinstance(emb, list) else emb 
            for emb in items['embedding'].values 
            if emb is not None
        ])
        
        if len(embeddings) < MIN_SUBDIVISION_SIZE:
            print(f"⚠️ Not enough valid embeddings to subdivide group {base_group_id}")
            return
        
        # Import K-means
        from sklearn.cluster import KMeans
        
        # Calculate number of subgroups needed
        # Aim for groups of ~8 items each, with at least 2 groups
        target_size = 8
        num_subgroups = max(2, len(items) // target_size)
        
        # Limit to a reasonable number
        num_subgroups = min(num_subgroups, 5)
        
        # Perform K-means clustering
        kmeans = KMeans(n_clusters=num_subgroups, random_state=42)
        subtopic_labels = kmeans.fit_predict(embeddings)
        
        # Create mapping from item ID to subtopic
        item_to_subtopic = {
            item_id: int(subtopic) 
            for item_id, subtopic in zip(items['id'].values, subtopic_labels)
        }
        
        # Use 7-digit IDs derived from the base_group_id
        base_id = _generate_base_id(df, base_group_id, num_subgroups)
        
        # Evaluate quality of each cluster before assigning group IDs
        created_groups = _evaluate_cluster_quality(df, items, subtopic_labels, embeddings, item_to_subtopic, base_id)
        
        if created_groups:
            min_id = min(created_groups)
            max_id = max(created_groups)
            print(f"ℹ️ Subdivided group {base_group_id} into {len(created_groups)} quality groups (IDs: {min_id}-{max_id})")
            print(f"ℹ️ Created groups: {sorted(created_groups)}")
        else:
            print(f"⚠️ No quality subgroups found for group {base_group_id}. Items remain in original group.")
            # Keep items in the original group
            df.loc[df['id'].isin(items['id']), 'group'] = base_group_id
        
    except Exception as e:
        print(f"⚠️ Error in group subdivision: {str(e)}")
        traceback.print_exc()
        # Fall back to not subdividing

def _evaluate_cluster_quality(df, items, subtopic_labels, embeddings, item_to_subtopic, base_id):
    """
    Evaluate the quality of each cluster and only create groups for good clusters.
    Returns a list of group IDs that were actually created.
    """
    SIMILARITY_THRESHOLD = 0.65  # Minimum average similarity required for a cluster
    MIN_CLUSTER_SIZE = 2  # Minimum number of items needed in a cluster
    
    # Track created groups
    created_groups = []
    
    # Count items per cluster
    unique_subtopics = np.unique(subtopic_labels)
    print(f"ℹ️ K-means created {len(unique_subtopics)} clusters")
    
    # For each cluster, evaluate quality
    for subtopic in unique_subtopics:
        # Get embeddings for this cluster
        cluster_indices = [i for i, label in enumerate(subtopic_labels) if label == subtopic]
        cluster_embeddings = embeddings[cluster_indices]
        
        # Skip clusters that are too small
        if len(cluster_embeddings) < MIN_CLUSTER_SIZE:
            print(f"ℹ️ Cluster {subtopic} skipped: too small ({len(cluster_embeddings)} items)")
            continue
        
        # Calculate average pairwise similarity within cluster
        similarities = []
        for i in range(len(cluster_embeddings)):
            for j in range(i+1, len(cluster_embeddings)):
                sim = np.dot(cluster_embeddings[i], cluster_embeddings[j])
                similarities.append(sim)
        
        if not similarities:
            avg_similarity = 0
        else:
            avg_similarity = sum(similarities) / len(similarities)
        
        # Create group only if similarity is above threshold
        if avg_similarity >= SIMILARITY_THRESHOLD:
            new_group_id = base_id + subtopic
            
            # Get IDs of items in this cluster
            cluster_item_ids = [item_id for item_id, label in item_to_subtopic.items() if label == subtopic]
            
            # Assign group ID to these items
            df.loc[df['id'].isin(cluster_item_ids), 'group'] = new_group_id
            created_groups.append(new_group_id)
            
            print(f"✅ Created group {new_group_id} with {len(cluster_item_ids)} items (similarity: {avg_similarity:.3f})")
        else:
            print(f"⚠️ Rejected cluster {subtopic} due to low similarity: {avg_similarity:.3f} < {SIMILARITY_THRESHOLD}")
            # Items in rejected clusters will keep their original group
            # They'll be handled by the main function if no groups were created
    
    return created_groups

def _generate_base_id(df, base_group_id, num_subgroups):
    """Generate a consistent base ID for subgroups"""
    base_id = 7777777
    try:
        base_group_id_int = int(base_group_id)
        # Convert to string to get the first digits
        base_group_str = str(base_group_id_int)
        
        # If base_group_id has more than 7 digits already, use it as is
        if len(base_group_str) >= 7:
            base_id = base_group_id_int
        else:
            # Take the first digits and append zeros to get a 7-digit number
            # For example: 42 -> 4200000, 123 -> 1230000
            first_digits = base_group_str
            zeros_needed = 7 - len(first_digits)
            base_id = int(first_digits + '0' * zeros_needed)
    except (ValueError, TypeError):
        # Fallback if base_group_id can't be converted to int
        base_id = 7777777
        print(f"⚠️ Could not derive base_id from {base_group_id}, using default {base_id}")
    
    # Check if any existing groups already use IDs in this range
    target_range_end = base_id + num_subgroups
    if 'group' in df.columns and not df['group'].dropna().empty:
        # Convert to numeric, ignoring errors
        numeric_groups = pd.to_numeric(df['group'].dropna(), errors='coerce').dropna()
        
        # Check for conflicts in the range we want to use
        conflicting_ids = numeric_groups[(numeric_groups >= base_id) & (numeric_groups < target_range_end)]
        if not conflicting_ids.empty:
            # If there's a conflict, find a new base_id
            base_id = max(base_id, int(conflicting_ids.max()) + 1)
            print(f"⚠️ ID conflict detected. Using new base_id: {base_id}")
    
    return base_id

def _subdivide_group_with_firestore(df, new_items, group_id, MAX_GROUP_SIZE, MIN_SUBDIVISION_SIZE, db_cluster_id):
    """
    Subdivide a group that includes items from Firestore and items in the current dataframe
    
    Args:
        df: The current dataframe
        new_items: New items to be added to the group
        group_id: The target group ID
        MAX_GROUP_SIZE: Maximum allowed group size
        MIN_SUBDIVISION_SIZE: Minimum size for subdivision
        db_cluster_id: The ID of the database cluster
    """
    try:
        # Get existing items from Firestore
        existing_items = get_group_items(group_id)
        print(f"ℹ️ Retrieved {len(existing_items)} existing items from group {group_id} in Firestore")
        
        # Convert to DataFrame with the same structure as our working dataframe
        if existing_items:
            existing_df = pd.DataFrame(existing_items)
            
            # Mark all items from Firestore as "reference news" since they're already grouped
            # This ensures they're treated correctly during the subdivision process
            existing_df['is_reference'] = True
            
            # Create a combined DataFrame of both existing and new items
            # Include non-reference items from new_items for subdivision
            new_non_reference_items = new_items[~new_items['is_reference']]
            
            # Also add the reference items but mark them as reference
            # This ensures they're included in the clustering but maintain their status
            new_reference_items = new_items[new_items['is_reference']].copy()
            
            # Combine all items
            combined_items = pd.concat([existing_df, new_non_reference_items, new_reference_items], ignore_index=True)
        else:
            # If no existing items, just use the new items
            combined_items = new_items.copy()
        
        # Now proceed with subdivision on the combined items
        if len(combined_items) > MIN_SUBDIVISION_SIZE:
            _subdivide_group(df, combined_items, group_id, MAX_GROUP_SIZE, MIN_SUBDIVISION_SIZE)
            print(f"ℹ️ Subdivided group {group_id} with items from Firestore and current batch")
        else:
            # Not enough items for subdivision after all, just assign to the group
            df.loc[(df['temp_group'] == db_cluster_id) & (df['group'].isna()), 'group'] = group_id
            print(f"ℹ️ Not enough items for subdivision after combining with existing. Assigned to group {group_id}")
            
    except Exception as e:
        print(f"⚠️ Error in Firestore-based group subdivision: {str(e)}")
        traceback.print_exc()  # Print the full traceback to help with debugging
        # Fall back to not subdividing
        df.loc[(df['temp_group'] == db_cluster_id) & (df['group'].isna()), 'group'] = group_id

def process_results(df, has_reference_news=False):
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
            result_item = {
                "id": item_row["id"], "group": None, "title": item_row["title"],
                "scraped_description": item_row["scraped_description"], 
                "description": item_row.get("description", ""),
                "source_medium": item_row["source_medium"]
            }
            
            # Include existing_group if present
            if has_reference_news and "existing_group" in item_row and pd.notna(item_row["existing_group"]):
                result_item["existing_group"] = item_row["existing_group"]
                
            result.append(result_item)
            processed_ids_for_result.add(item_row["id"])
            continue

        seen_media_in_group = set()
        current_group_items_for_result = []

        # Process reference items first
        reference_items_in_final_group = group_df[group_df["is_reference"] == True]
        for _, item_row in reference_items_in_final_group.iterrows():
            if item_row["source_medium"] not in seen_media_in_group:
                result_item = {
                    "id": item_row["id"], 
                    "group": group_id, 
                    "title": item_row["title"],
                    "scraped_description": item_row["scraped_description"],
                    "description": item_row.get("description", ""),
                    "source_medium": item_row["source_medium"]
                }
                
                # Include existing_group for reference items
                if has_reference_news and "existing_group" in item_row and pd.notna(item_row["existing_group"]):
                    result_item["existing_group"] = item_row["existing_group"]
                    
                current_group_items_for_result.append(result_item)
                seen_media_in_group.add(item_row["source_medium"])
                processed_ids_for_result.add(item_row["id"])
        
        # Then non-reference items
        non_reference_items_in_final_group = group_df[group_df["is_reference"] == False]
        for _, item_row in non_reference_items_in_final_group.iterrows():
            if item_row["id"] not in processed_ids_for_result and item_row["source_medium"] not in seen_media_in_group:
                result_item = {
                    "id": item_row["id"], 
                    "group": group_id, 
                    "title": item_row["title"],
                    "scraped_description": item_row["scraped_description"],
                    "description": item_row.get("description", ""),
                    "source_medium": item_row["source_medium"]
                }
                
                # Track existing_group when available (might be None/NaN)
                if has_reference_news and "existing_group" in item_row and pd.notna(item_row["existing_group"]):
                    result_item["existing_group"] = item_row["existing_group"]
                    
                current_group_items_for_result.append(result_item)
                seen_media_in_group.add(item_row["source_medium"])
                processed_ids_for_result.add(item_row["id"])

        # Handle groups with fewer than 2 items after deduplication
        if len(current_group_items_for_result) < MIN_VALID_SOURCES and not any(item['id'] in reference_items_in_final_group['id'].values for item in current_group_items_for_result):
            for item_dict in current_group_items_for_result:
                item_dict["group"] = None
                result.append(item_dict)
        else:
            result.extend(current_group_items_for_result)

    # Add any remaining ungrouped items
    for index, row in df.iterrows():
        if row["id"] not in processed_ids_for_result:
            result_item = {
                "id": row["id"], 
                "group": row["group"],
                "title": row["title"], 
                "scraped_description": row["scraped_description"],
                "description": row.get("description", ""),
                "source_medium": row["source_medium"]
            }
            
            # Include existing_group if present
            if has_reference_news and "existing_group" in row and pd.notna(row["existing_group"]):
                result_item["existing_group"] = row["existing_group"]
                
            result.append(result_item)
    
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
        
        embedding_is_present_and_valid = False

        if isinstance(embedding_value, (list, np.ndarray)):
            if len(embedding_value) > 0:
                if isinstance(embedding_value, np.ndarray) and np.all(pd.isna(embedding_value)):
                    embedding_is_present_and_valid = False
                else:
                    embedding_is_present_and_valid = True

        if not embedding_is_present_and_valid:
            data_dict = row.to_dict()

            if "id" not in data_dict or pd.isna(data_dict.get("id")):
                continue 

            if pd.isna(data_dict.get("scraped_description")) and pd.isna(data_dict.get("description")):
                continue

            news_needing_embedding.append(data_dict)
            
    print(f"ℹ️ Identified {len(news_needing_embedding)} news items to process for embeddings.")
    return news_needing_embedding