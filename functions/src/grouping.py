import numpy as np
import pandas as pd
import traceback

def group_news(noticias_json):
    """
    Groups news based on their semantic similarity
    """
    try:
        print("ℹ️ Starting news grouping...")
        # Convert to DataFrame
        df = pd.DataFrame(noticias_json)
                
        # Check that the required columns exist
        if "id" not in df.columns or "title" not in df.columns or "description" not in df.columns:
            raise ValueError("The JSON must contain the columns 'id', 'title' and 'description' with the text of the news")
        
        # Prepare column for new groups
        df["group_number"] = None
        
        # Preserve existing groups
        has_reference_news = "existing_group" in df.columns
        if has_reference_news:
            # Copy existing groups to group_number
            df.loc[df["existing_group"].notna(), "group_number"] = df.loc[df["existing_group"].notna(), "existing_group"]
            
            # Identify news that already have a group (references) and those that don't (to group)
            reference_mask = df["existing_group"].notna()
            df["is_reference"] = reference_mask
            
            # Count how many news items need to be grouped
            to_group_count = (~reference_mask).sum()
            
            # If all news already have a group, there's nothing to do
            if to_group_count == 0:
                return df[["id", "group_number"]].to_dict(orient='records')
        else:
            df["is_reference"] = False
        
        # If there's only one news item to group, assign a new group
        if len(df[~df["is_reference"]]) <= 1 and not has_reference_news:
            df.loc[~df["is_reference"], "group_number"] = 0
            return df[["id", "group_number"]].to_dict(orient='records')
        
        # Generate embeddings
        print("ℹ️ Loading embeddings model...")
        from sentence_transformers import SentenceTransformer
        
        # Concatenate 'title' and 'description' into a new column 'noticia_completa'
        df["noticia_completa"] = df["title"].fillna("") + " " + df["description"].fillna("")
        
        model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", 
                                    cache_folder="/tmp/sentence_transformers")
        
        print("ℹ️ Generating embeddings...")
        embeddings = model.encode(df["noticia_completa"].tolist(), convert_to_numpy=True)
                
        # Parameters for clustering
        eps = 0.25  # Distance threshold
        min_samples = 2  # Minimum number of samples in a cluster
        n_neighbors = min(5, len(df))  # Number of neighbors to consider
        
        print("ℹ️ Normalizing embeddings...")
        # Normalize embeddings to use cosine similarity
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1e-10
        embeddings_norm = embeddings / norms
        
        print("ℹ️ Calculating nearest neighbors...")
        from sklearn.neighbors import NearestNeighbors
        from scipy.sparse import lil_matrix
        from sklearn.cluster import DBSCAN
        
        # Nearest neighbors model
        nbrs = NearestNeighbors(n_neighbors=n_neighbors, metric="cosine").fit(embeddings_norm)
        
        # Get distances and nearest neighbors
        distances, indices = nbrs.kneighbors(embeddings_norm)
        
        # Convert similarity to distance (DBSCAN uses distance)
        distances = 1 - distances
        
        print("ℹ️ Building distance matrix...")
        # Build distance matrix
        num_embeddings = embeddings.shape[0]
        sparse_matrix = lil_matrix((num_embeddings, num_embeddings))
        
        for i in range(num_embeddings):
            for j in range(n_neighbors):
                # Save similarity in sparse matrix
                sparse_matrix[i, indices[i, j]] = 1 - distances[i, j]
        
        print("ℹ️ Applying DBSCAN algorithm...")
        # Apply DBSCAN with sparse matrix
        clustering = DBSCAN(eps=eps, min_samples=min_samples, metric="precomputed")
        group_labels = clustering.fit_predict(sparse_matrix.tocsr())
                
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
                        df.at[idx, "group_number"] = group_mapping[temp_group]
                    elif temp_group != -1:
                        # Create new group for clusters without mapping
                        # Find the maximum existing group and add 1
                        if df["group_number"].notna().any():
                            max_group = df["group_number"].max()
                            if max_group is not None:
                                new_group_id = int(max_group) + 1
                            else:
                                new_group_id = 0
                        else:
                            new_group_id = 0
                            
                        # Assign new ID to the entire cluster
                        mask = (df[temp_group_column] == temp_group) & (~df["is_reference"])
                        df.loc[mask, "group_number"] = new_group_id
        else:
            # If there are no reference news, simply assign DBSCAN groups
            df["group_number"] = df[temp_group_column]
            df.loc[df["group_number"] == -1, "group_number"] = None
        
        # New post-processing to remove duplicates by medium
        result = []
        
        # Process news by groups
        for group in df["group_number"].unique():
            if pd.isna(group):
                continue
                
            # Filter news in this group
            group_df = df[df["group_number"] == group]
            
            # If there's only one news item in the group and it's not a reference, leave it ungrouped
            if len(group_df) < 2 and not any(group_df["is_reference"]):
                for _, row in group_df.iterrows():
                    result.append({
                        "id": row["id"],
                        "group_number": group,
                        "title": row["title"],
                        "description": row["description"],
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
                        "group_number": None,
                        "title": row["title"],
                        "description": row["description"],
                        "source_medium": row["source_medium"]
                    })
            else:
                for row in filtered_group:
                    result.append({
                        "id": row["id"],
                        "group_number": group,
                        "title": row["title"],
                        "description": row["description"],
                        "source_medium": row["source_medium"]
                    })
        
        # Include news that were left ungrouped (outliers)
        for _, row in df[pd.isna(df["group_number"])].iterrows():
            result.append({
                "id": row["id"],
                "group_number": None,
                "title": row["title"],
                "description": row["description"],
                "source_medium": row["source_medium"]
            })
        
        # If no groups with more than one news item remain, assign individual groups
        if not any(r["group_number"] is not None for r in result):
            for i, r in enumerate(result):
                r["group_number"] = i

        print("✅ Grouping completed successfully")
        return result
    
    except Exception as e:
        print(f"❌ Error in group_news: {str(e)}")
        traceback.print_exc()
        raise