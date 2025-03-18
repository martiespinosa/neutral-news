from firebase_functions import https_fn
from firebase_admin import initialize_app, auth
import json
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.neighbors import NearestNeighbors
from sklearn.cluster import DBSCAN
from scipy.sparse import lil_matrix

# Inicializar la aplicación Firebase
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
    
    # Si solo hay una noticia, asignar grupo 0 y devolver
    if len(df) <= 1:
        df["group_number"] = 0
        return df.to_dict(orient='records')
    
    # Generar embeddings
    model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    embeddings = model.encode(df["noticia_completa"].tolist(), convert_to_numpy=True)
    
    # Parámetros para el clustering
    eps = 0.1  # Umbral de distancia
    min_samples = 2  # Mínimo número de muestras en un cluster
    n_neighbors = min(3, len(df))  # Número de vecinos a considerar
    
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
    
    # Si no hay noticias agrupadas, devolver todas con grupos individuales
    if len(noticias_con_grupo) == 0:
        df["group_number"] = range(len(df))
        return df.to_dict(orient='records')
    
    # Agrupar por número de grupo
    grupos = noticias_con_grupo.groupby('group_number')
    
    # Filtrar grupos con noticias distintas
    grupos_validos = []
    for grupo, grupo_df in grupos:
        if grupo_df["noticia_completa"].nunique() > 1:
            grupos_validos.append(grupo_df)
    
    # Resultado final
    if grupos_validos:
        # Concatenar todos los grupos válidos
        resultado_final = pd.concat(grupos_validos)
        
        # Añadir noticias sin grupo con números de grupo únicos
        sin_grupo = df[~df.index.isin(resultado_final.index)]
        if len(sin_grupo) > 0:
            # Asignar nuevos números de grupo a partir del máximo existente
            max_grupo = resultado_final["group_number"].max() + 1
            sin_grupo["group_number"] = range(max_grupo, max_grupo + len(sin_grupo))
            resultado_final = pd.concat([resultado_final, sin_grupo])
    else:
        # Si no hay grupos válidos, devolver todo con grupo -1
        resultado_final = df
        
        # Si todas tienen grupo -1, asignar grupos incrementales
        if (resultado_final["group_number"] == -1).all():
            resultado_final["group_number"] = range(len(resultado_final))
    
    return resultado_final.to_dict(orient='records')

# Función para verificar el token de autenticación
async def verificar_autenticacion(req):
    """
    Verifica si la solicitud tiene un token válido de Firebase Authentication.
    """
    try:
        # Obtener el encabezado de autorización
        auth_header = req.headers.get('Authorization', '')

        # Verificar que el encabezado tiene el formato correcto
        if not auth_header.startswith('Bearer '):
            print("❌ Formato de autorización inválido")
            return None  # Cambiar de False a None para indicar autenticación fallida
        
        # Extraer el token
        token = auth_header.split('Bearer ')[1].strip()  # Eliminamos espacios extra

        # Verificar el token con Firebase Auth
        decoded_token = auth.verify_id_token(token)

        # Imprimir información del token para depuración
        print(f"✅ Token verificado correctamente: UID={decoded_token.get('uid')}")

        return decoded_token  # Devuelve el token decodificado en lugar de solo True
    except auth.ExpiredIdTokenError:
        print("❌ Error: El token ha expirado")
    except auth.InvalidIdTokenError:
        print("❌ Error: Token no válido")
    except auth.RevokedIdTokenError:
        print("❌ Error: El token ha sido revocado")
    except Exception as e:
        print(f"❌ Error al verificar token: {str(e)}")
        import traceback
        traceback.print_exc()

    return None  # Retornar None en cualquier error de autenticación

@https_fn.on_request(timeout_sec=540, memory=4096)
async def procesar_noticias(req: https_fn.Request) -> https_fn.Response:
    print("ℹ️ Procesando solicitud...")
    """
    Función HTTP que recibe una lista de noticias, las procesa y devuelve las agrupadas.
    """
    try:
        # Comprobar si es una solicitud GET para pruebas
        if req.method == 'GET':
            return https_fn.Response(
                json.dumps({
                    "message": "API de agrupación de noticias en funcionamiento. Envía un POST con una lista de noticias para procesarlas.",
                    "formato_esperado": [
                        {"titulo": "Título de la noticia 1", "cuerpo": "Cuerpo de la noticia 1"}, 
                        {"titulo": "Título de la noticia 2", "cuerpo": "Cuerpo de la noticia 2"}
                    ],
                    "autenticacion": "Se requiere un token de Firebase Auth en el encabezado 'Authorization: Bearer [token]'"
                }, ensure_ascii=False),
                content_type="application/json"
            )
        
        # Verificar la autenticación
        es_autenticado = await verificar_autenticacion(req)
        if not es_autenticado:
            return https_fn.Response(
                json.dumps({"error": "No autorizado. Se requiere un token válido de Firebase Auth."}, ensure_ascii=False),
                status_code=403,
                content_type="application/json"
            )
        
        # Obtener las noticias del cuerpo de la solicitud
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
        error_message = f"Error: {str(e)}"
        print(error_message)  # Esto aparecerá en los logs de Firebase
        return https_fn.Response(error_message, status_code=500)
