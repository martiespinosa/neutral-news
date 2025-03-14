import json
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.neighbors import NearestNeighbors
from sklearn.cluster import DBSCAN
from scipy.sparse import lil_matrix
from firebase_functions import https_fn
from firebase_admin import initialize_app

initialize_app()

def agrupar_noticias(noticias_json):
    """
    Agrupa noticias basándose en sus similitudes semánticas.
    
    Args:
        noticias_json (list): Lista de diccionarios con noticias
        
    Returns:
        list: Lista de diccionarios con las noticias agrupadas, incluyendo el número de grupo
    """
    # Convertir a DataFrame
    df = pd.DataFrame(noticias_json)
    
    # Verificar que existe la columna necesaria
    if "titulo" not in df.columns or "cuerpo" not in df.columns:
        raise ValueError("El JSON debe contener las columnas 'titulo' y 'cuerpo' con el texto de las noticias")
    
    # Concatenar 'titulo' y 'cuerpo' en una nueva columna 'noticia_completa'
    df["noticia_completa"] = df["titulo"] + " " + df["cuerpo"]
    
    # Generar embeddings
    model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    embeddings = model.encode(df["noticia_completa"].tolist(), convert_to_numpy=True)
    
    # Parámetros para el clustering
    eps = 0.1  # Umbral de distancia
    min_samples = 2  # Mínimo número de muestras en un cluster
    n_neighbors = 3  # Número de vecinos a considerar
    
    # Normalizar embeddings para usar similitud coseno
    embeddings_norm = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
    
    # Modelo de vecinos más cercanos
    nbrs = NearestNeighbors(n_neighbors=n_neighbors, metric="cosine").fit(embeddings_norm)
    
    # Obtener distancias y vecinos más cercanos
    distances, indices = nbrs.kneighbors(embeddings_norm)
    
    # Convertir similitud a distancia (DBSCAN usa distancia)
    distances = 1 - distances
    
    # Construir matriz de distancias
    num_embeddings = embeddings.shape[0]
    sparse_matrix = lil_matrix((num_embeddings, num_embeddings))
    
    for i in range(num_embeddings):
        for j in range(n_neighbors):
            # Guardar la similitud en la matriz dispersa
            sparse_matrix[i, indices[i, j]] = 1 - distances[i, j]
    
    # Aplicar DBSCAN con la matriz dispersa
    clustering = DBSCAN(eps=eps, min_samples=min_samples, metric="precomputed")
    
    # Asignar grupos a las noticias
    df["group_number"] = clustering.fit_predict(sparse_matrix.tocsr())
    
    # Filtrar grupos válidos (con más de una noticia)
    noticias_con_grupo = df[df["group_number"] != -1]
    grupos = noticias_con_grupo.groupby('group_number')
    
    # Filtrar grupos con noticias distintas
    grupos_validos = []
    for grupo, grupo_df in grupos:
        if grupo_df["noticia_completa"].nunique() > 1:
            grupos_validos.append(grupo_df)
    
    # Resultado final
    if grupos_validos:
        resultado_final = pd.concat(grupos_validos)
    else:
        # Si no hay grupos válidos, devolver todo con grupo -1
        resultado_final = df
    
    return resultado_final.to_dict(orient='records')

# Exponer la función como endpoint HTTP
@https_fn.on_request()
def procesar_noticias(req: https_fn.Request) -> https_fn.Response:
    """
    Función HTTP que recibe una lista de noticias, las procesa y devuelve las agrupadas.
    """
    try:
        # Obtener las noticias del cuerpo de la solicitud (en formato JSON)
        noticias = req.get_json()
        
        if noticias is None:
            return https_fn.Response("No se recibieron noticias", status_code=400)
        
        # Llamar a la función para agrupar las noticias
        noticias_agrupadas = agrupar_noticias(noticias)
        
        # Devolver las noticias agrupadas como respuesta
        return https_fn.Response(
            json.dumps(noticias_agrupadas, ensure_ascii=False, indent=2),
            content_type="application/json",
            status_code=200
        )
    except Exception as e:
        return https_fn.Response(f"Error: {str(e)}", status_code=500)
