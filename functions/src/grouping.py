import numpy as np
import pandas as pd
import traceback
from sentence_transformers import SentenceTransformer
from sklearn.neighbors import NearestNeighbors
from scipy.sparse import lil_matrix
from sklearn.cluster import DBSCAN

def validate_input(noticias_json):
    """
    Validates the input JSON and converts it to a DataFrame.
    """
    df = pd.DataFrame(noticias_json)
    if "id" not in df.columns or "title" not in df.columns or "description" not in df.columns:
        raise ValueError("The JSON must contain the columns 'id', 'title' and 'description' with the text of the news")
    return df

def prepare_groups(df):
    """
    Prepares the DataFrame for grouping by handling existing groups and references.
    """
    df["group"] = None
    has_reference_news = "existing_group" in df.columns
    if has_reference_news:
        df.loc[df["existing_group"].notna(), "group"] = df.loc[df["existing_group"].notna(), "existing_group"]
        reference_mask = df["existing_group"].notna()
        df["is_reference"] = reference_mask
        if (~reference_mask).sum() == 0:
            return df, True
    else:
        df["is_reference"] = False
    return df, False

def generate_embeddings(df):
    """
    Generates embeddings for the news using SentenceTransformer.
    """
    print("ℹ️ Loading embeddings model...")
    df["noticia_completa"] = df["title"].fillna("") + " " + df["description"].fillna("")
    model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", 
                                cache_folder="/tmp/sentence_transformers")
    print("ℹ️ Generating embeddings...")
    embeddings = model.encode(df["noticia_completa"].tolist(), convert_to_numpy=True)
    return embeddings

def normalize_embeddings(embeddings):
    """
    Normalizes embeddings for cosine similarity.
    """
    print("ℹ️ Normalizing embeddings...")
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1e-10
    return embeddings / norms

def build_distance_matrix(embeddings_norm, n_neighbors):
    """
    Builds a sparse distance matrix using nearest neighbors.
    """
    print("ℹ️ Calculating nearest neighbors...")
    nbrs = NearestNeighbors(n_neighbors=n_neighbors, metric="cosine").fit(embeddings_norm)
    distances, indices = nbrs.kneighbors(embeddings_norm)
    distances = 1 - distances  # Convert similarity to distance
    print("ℹ️ Building distance matrix...")
    num_embeddings = embeddings_norm.shape[0]
    sparse_matrix = lil_matrix((num_embeddings, num_embeddings))
    for i in range(num_embeddings):
        for j in range(n_neighbors):
            sparse_matrix[i, indices[i, j]] = 1 - distances[i, j]
    return sparse_matrix

def apply_dbscan(sparse_matrix, eps, min_samples):
    """
    Applies the DBSCAN clustering algorithm.
    """
    print("ℹ️ Applying DBSCAN algorithm...")
    clustering = DBSCAN(eps=eps, min_samples=min_samples, metric="precomputed")
    return clustering.fit_predict(sparse_matrix.tocsr())

def map_groups(df, group_labels, has_reference_news):
    """
    Maps new groups to existing ones when there are matches.
    """
    temp_group_column = "temp_group"
    df[temp_group_column] = group_labels
    if has_reference_news:
        group_mapping = {}
        for new_group in np.unique(group_labels):
            if new_group == -1:
                continue
            group_items = df[df[temp_group_column] == new_group]
            ref_items = group_items[group_items["is_reference"]]
            if len(ref_items) > 0:
                existing_groups = ref_items["existing_group"].unique()
                if len(existing_groups) > 1:
                    counts = ref_items["existing_group"].value_counts()
                    most_common = counts.idxmax()
                    group_mapping[new_group] = most_common
                else:
                    group_mapping[new_group] = existing_groups[0]
        for idx, row in df.iterrows():
            if not row["is_reference"]:
                temp_group = row[temp_group_column]
                if temp_group in group_mapping:
                    df.at[idx, "group"] = group_mapping[temp_group]
                elif temp_group != -1:
                    max_group = df["group"].max() if df["group"].notna().any() else -1
                    new_group_id = int(max_group) + 1
                    mask = (df[temp_group_column] == temp_group) & (~df["is_reference"])
                    df.loc[mask, "group"] = new_group_id
    else:
        df["group"] = df[temp_group_column]
        df.loc[df["group"] == -1, "group"] = None
    return df

def post_process_groups(df):
    """
    Post-processes groups to remove duplicates and handle outliers.
    """
    result = []
    for group in df["group"].unique():
        if pd.isna(group):
            continue
        group_df = df[df["group"] == group]
        if len(group_df) < 2 and not any(group_df["is_reference"]):
            for _, row in group_df.iterrows():
                result.append({
                    "id": row["id"],
                    "group": None,
                    "title": row["title"],
                    "description": row["description"],
                    "source_medium": row["source_medium"]
                })
            continue
        seen_media = set()
        filtered_group = []
        for _, row in group_df[group_df["is_reference"]].iterrows():
            if row["source_medium"] not in seen_media:
                seen_media.add(row["source_medium"])
                filtered_group.append(row)
        for _, row in group_df[~group_df["is_reference"]].iterrows():
            if row["source_medium"] not in seen_media:
                seen_media.add(row["source_medium"])
                filtered_group.append(row)
        if len(filtered_group) < 2 and not any(row["is_reference"] for row in filtered_group):
            for row in filtered_group:
                result.append({
                    "id": row["id"],
                    "group": None,
                    "title": row["title"],
                    "description": row["description"],
                    "source_medium": row["source_medium"]
                })
        else:
            for row in filtered_group:
                result.append({
                    "id": row["id"],
                    "group": group,
                    "title": row["title"],
                    "description": row["description"],
                    "source_medium": row["source_medium"]
                })
    for _, row in df[pd.isna(df["group"])].iterrows():
        result.append({
            "id": row["id"],
            "group": None,
            "title": row["title"],
            "description": row["description"],
            "source_medium": row["source_medium"]
        })
    if not any(r["group"] is not None for r in result):
        for i, r in enumerate(result):
            r["group"] = i
    return result

def group_news(noticias_json):
    """
    Groups news based on their semantic similarity.
    """
    try:
        print("ℹ️ Starting news grouping...")
        df = validate_input(noticias_json)
        df, all_grouped = prepare_groups(df)
        if all_grouped:
            return df[["id", "group"]].to_dict(orient='records')
        embeddings = generate_embeddings(df)
        embeddings_norm = normalize_embeddings(embeddings)
        sparse_matrix = build_distance_matrix(embeddings_norm, n_neighbors=min(5, len(df)))
        group_labels = apply_dbscan(sparse_matrix, eps=0.25, min_samples=2)
        df = map_groups(df, group_labels, "existing_group" in df.columns)
        result = post_process_groups(df)
        print("✅ Grouping completed successfully")
        return result
    except Exception as e:
        print(f"❌ Error in group_news: {str(e)}")
        traceback.print_exc()
        raise