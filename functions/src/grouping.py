import numpy as np
import pandas as pd
import traceback

def agrupar_noticias(noticias_json):
    """
    Agrupa noticias basándose en su similitud semántica
    """
    try:
        print("ℹ️ Starting news grouping...")
        # Convert to DataFrame
        df = pd.DataFrame(noticias_json)
                
        # Check that the required columns exist
        if "id" not in df.columns or "titulo" not in df.columns or "cuerpo" not in df.columns:
            raise ValueError("The JSON must contain the columns 'id', 'titulo' and 'cuerpo' with the text of the news")
        
        # Preparar columna para grupos nuevos
        df["group_number"] = None
        
        # Preservar los grupos existentes
        has_reference_news = "existing_group" in df.columns
        if has_reference_news:
            # Copiar grupos existentes a group_number
            df.loc[df["existing_group"].notna(), "group_number"] = df.loc[df["existing_group"].notna(), "existing_group"]
            
            # Identificar noticias que ya tienen grupo (referencias) y las que no (a agrupar)
            reference_mask = df["existing_group"].notna()
            df["is_reference"] = reference_mask
            
            # Contar cuántas noticias necesitan ser agrupadas
            to_group_count = (~reference_mask).sum()
            
            # Si todas las noticias ya tienen grupo, no hay nada que hacer
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
        
        # Concatenate 'titulo' and 'cuerpo' into a new column 'noticia_completa'
        df["noticia_completa"] = df["titulo"].fillna("") + " " + df["cuerpo"].fillna("")
        
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
                
        # Asignar grupos solo a las noticias que no tengan uno
        temp_group_column = "temp_group"
        df[temp_group_column] = group_labels
        
        # Mapear nuevos grupos a los existentes cuando haya coincidencias
        if has_reference_news:
            group_mapping = {}
            for new_group in np.unique(group_labels):
                if new_group == -1:  # Saltar ruido/outliers
                    continue
                    
                # Buscar noticias de este nuevo grupo temporal
                group_items = df[df[temp_group_column] == new_group]
                
                # Verificar si alguna tiene un grupo existente
                ref_items = group_items[group_items["is_reference"]]
                if len(ref_items) > 0:
                    existing_groups = ref_items["existing_group"].unique()
                    
                    # Si hay más de un grupo existente, elegir el más frecuente
                    if len(existing_groups) > 1:
                        counts = ref_items["existing_group"].value_counts()
                        most_common = counts.idxmax()
                        group_mapping[new_group] = most_common
                    else:
                        group_mapping[new_group] = existing_groups[0]
            
            # Aplicar el mapeo donde sea necesario
            for idx, row in df.iterrows():
                if not row["is_reference"]:
                    temp_group = row[temp_group_column]
                    if temp_group in group_mapping:
                        # Usar grupo existente mapeado
                        df.at[idx, "group_number"] = group_mapping[temp_group]
                    elif temp_group != -1:
                        # Crear nuevo grupo para clusters sin mapeo
                        # Encontrar el máximo grupo existente y añadir 1
                        if df["group_number"].notna().any():
                            max_group = df["group_number"].max()
                            if max_group is not None:
                                new_group_id = int(max_group) + 1
                            else:
                                new_group_id = 0
                        else:
                            new_group_id = 0
                            
                        # Asignar nuevo ID a todo el cluster
                        mask = (df[temp_group_column] == temp_group) & (~df["is_reference"])
                        df.loc[mask, "group_number"] = new_group_id
        else:
            # Si no hay noticias de referencia, simplemente asignar los grupos de DBSCAN
            df["group_number"] = df[temp_group_column]
        
        # Nuevo post-procesamiento para eliminar duplicados por medio
        result = []
        
        # Procesar noticias por grupos
        for group in df["group_number"].unique():
            if pd.isna(group):
                continue
                
            # Filtrar noticias de este grupo
            group_df = df[df["group_number"] == group]
            
            # Si solo hay una noticia en el grupo y no es de referencia, dejarla sin grupo
            if len(group_df) < 2 and not any(group_df["is_reference"]):
                for _, row in group_df.iterrows():
                    result.append({"id": row["id"], "group_number": None})
                continue
            
            # Rastrear medios ya vistos
            seen_media = set()
            filtered_group = []
            
            # Primero incluir las noticias de referencia
            for _, row in group_df[group_df["is_reference"]].iterrows():
                if row["source_medium"] not in seen_media:
                    seen_media.add(row["source_medium"])
                    filtered_group.append(row)
            
            # Luego las noticias nuevas
            for _, row in group_df[~group_df["is_reference"]].iterrows():
                if row["source_medium"] not in seen_media:
                    seen_media.add(row["source_medium"])
                    filtered_group.append(row)
            
            # Si quedan menos de 2 noticias después de eliminar duplicados, ignorar grupo
            # excepto si ya hay noticias de referencia
            if len(filtered_group) < 2 and not any(row["is_reference"] for row in filtered_group):
                for row in filtered_group:
                    result.append({"id": row["id"], "group_number": None})
            else:
                for row in filtered_group:
                    result.append({"id": row["id"], "group_number": group})
        
        # Incluir noticias que quedaron sin grupo (outliers)
        for _, row in df[pd.isna(df["group_number"])].iterrows():
            result.append({"id": row["id"], "group_number": None})
        
        # Si no quedaron grupos con más de una noticia, asignar grupos individuales
        if not any(r["group_number"] is not None for r in result):
            for i, r in enumerate(result):
                r["group_number"] = i

        print("✅ Grouping completed successfully")
        return result
    
    except Exception as e:
        print(f"❌ Error in agrupar_noticias: {str(e)}")
        traceback.print_exc()
        raise