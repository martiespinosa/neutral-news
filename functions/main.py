from firebase_functions import https_fn
from firebase_admin import initialize_app, auth
import json
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.neighbors import NearestNeighbors
from sklearn.cluster import DBSCAN
from scipy.sparse import lil_matrix
import traceback

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
    try:
        print("ℹ️ Iniciando agrupación de noticias...")
        # Convertir a DataFrame
        df = pd.DataFrame(noticias_json)
        
        # Verificar que existe la columna necesaria
        if "id" not in df.columns or "titulo" not in df.columns or "cuerpo" not in df.columns:
            raise ValueError("El JSON debe contener las columnas 'id', 'titulo' y 'cuerpo' con el texto de las noticias")
        
        # Concatenar 'titulo' y 'cuerpo' en una nueva columna 'noticia_completa'
        df["noticia_completa"] = df["titulo"].fillna("") + " " + df["cuerpo"].fillna("")
        
        # Si solo hay una noticia, asignar grupo 0 y devolver
        if len(df) <= 1:
            df["group_number"] = 0
            # Eliminar la columna noticia_completa para evitar problemas de serialización
            return df[["id", "group_number"]].to_dict(orient='records')
        
        # Generar embeddings
        print("ℹ️ Cargando modelo de embeddings...")
        # Establecer cache_folder para asegurar que Firebase Functions tiene permisos de escritura
        model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", 
                                    cache_folder="/tmp/sentence_transformers")
        
        print("ℹ️ Generando embeddings...")
        embeddings = model.encode(df["noticia_completa"].tolist(), convert_to_numpy=True)
        
        # Liberar memoria del modelo después de usarlo
        del model
        import gc
        gc.collect()
        
        # Parámetros para el clustering
        eps = 0.1  # Umbral de distancia
        min_samples = 2  # Mínimo número de muestras en un cluster
        n_neighbors = min(3, len(df))  # Número de vecinos a considerar
        
        print("ℹ️ Normalizando embeddings...")
        # Normalizar embeddings para usar similitud coseno
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        # Evitar división por cero
        norms[norms == 0] = 1e-10
        embeddings_norm = embeddings / norms
        
        print("ℹ️ Calculando vecinos más cercanos...")
        # Modelo de vecinos más cercanos
        nbrs = NearestNeighbors(n_neighbors=n_neighbors, metric="cosine").fit(embeddings_norm)
        
        # Obtener distancias y vecinos más cercanos
        distances, indices = nbrs.kneighbors(embeddings_norm)
        
        # Convertir similitud a distancia (DBSCAN usa distancia)
        distances = 1 - distances
        
        print("ℹ️ Construyendo matriz de distancias...")
        # Construir matriz de distancias
        num_embeddings = embeddings.shape[0]
        sparse_matrix = lil_matrix((num_embeddings, num_embeddings))
        
        for i in range(num_embeddings):
            for j in range(n_neighbors):
                # Guardar la similitud en la matriz dispersa
                sparse_matrix[i, indices[i, j]] = 1 - distances[i, j]
        
        print("ℹ️ Aplicando algoritmo DBSCAN...")
        # Aplicar DBSCAN con la matriz dispersa
        clustering = DBSCAN(eps=eps, min_samples=min_samples, metric="precomputed")
        
        # Asignar grupos a las noticias
        df["group_number"] = clustering.fit_predict(sparse_matrix.tocsr())
        
        # Limpiar memoria
        del embeddings, embeddings_norm, sparse_matrix
        gc.collect()
        
        # Filtrar grupos válidos (con más de una noticia)
        noticias_con_grupo = df[df["group_number"] != -1]
        
        # Si no hay noticias agrupadas, devolver todas con grupos individuales
        if len(noticias_con_grupo) == 0:
            df["group_number"] = range(len(df))
            # Eliminar la columna noticia_completa para evitar problemas de serialización
            df = df.drop(columns=["noticia_completa"])
            return df.to_dict(orient='records')
        
        print("ℹ️ Procesando grupos finales...")
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
        
        # Convertir los números de grupo a enteros para asegurar serialización JSON correcta
        resultado_final["group_number"] = resultado_final["group_number"].astype(int)
        
        # Eliminar la columna noticia_completa para evitar problemas de serialización
        resultado_final = resultado_final.drop(columns=["noticia_completa"])
        
        print("✅ Agrupación completada correctamente")
        return resultado_final[["id", "group_number"]].to_dict(orient='records')
    except Exception as e:
        print(f"❌ Error en agrupar_noticias: {str(e)}")
        traceback.print_exc()
        raise

# Función para verificar el token de autenticación
def verificar_autenticacion(req):
    """
    Verifica si la solicitud tiene un token válido de Firebase Authentication.
    """
    try:
        # Obtener el encabezado de autorización
        auth_header = req.headers.get('Authorization', '')

        # Verificar que el encabezado tiene el formato correcto
        if not auth_header.startswith('Bearer '):
            print("❌ Formato de autorización inválido")
            return None
        
        # Extraer el token
        token = auth_header.split('Bearer ')[1].strip()

        # Verificar el token con Firebase Auth
        decoded_token = auth.verify_id_token(token)

        # Imprimir información del token para depuración
        print(f"✅ Token verificado correctamente: UID={decoded_token.get('uid')}")

        return decoded_token
    except auth.ExpiredIdTokenError:
        print("❌ Error: El token ha expirado")
    except auth.InvalidIdTokenError:
        print("❌ Error: Token no válido")
    except auth.RevokedIdTokenError:
        print("❌ Error: El token ha sido revocado")
    except Exception as e:
        print(f"❌ Error al verificar token: {str(e)}")
        traceback.print_exc()

    return None

@https_fn.on_request(timeout_sec=300, memory=4096)
def procesar_noticias(req: https_fn.Request) -> https_fn.Response:
    """
    Función HTTP que recibe una lista de noticias, las procesa y devuelve las agrupadas.
    """
    print("ℹ️ Procesando solicitud...")
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
        es_autenticado = verificar_autenticacion(req)
        if not es_autenticado:
            return https_fn.Response(
                json.dumps({"error": "No autorizado. Se requiere un token válido de Firebase Auth."}, ensure_ascii=False),
                status=403,
                content_type="application/json"
            )
        
        # Obtener las noticias del cuerpo de la solicitud
        try:
            noticias = req.get_json()
        except Exception as e:
            return https_fn.Response(
                json.dumps({"error": f"Error al procesar el JSON: {str(e)}"}, ensure_ascii=False),
                status=400,
                content_type="application/json"
            )
        
        if noticias is None:
            return https_fn.Response(
                json.dumps({"error": "No se recibieron noticias. El cuerpo debe ser un array JSON."}, ensure_ascii=False),
                status=400,
                content_type="application/json"
            )
        
        if not isinstance(noticias, list):
            return https_fn.Response(
                json.dumps({"error": "El formato recibido no es válido. Se espera un array de noticias."}, ensure_ascii=False),
                status=400,
                content_type="application/json"
            )
        
        # Validar longitud para evitar problemas de memoria
        if len(noticias) > 500:
            return https_fn.Response(
                json.dumps({"error": "El número máximo de noticias permitido es 500."}, ensure_ascii=False),
                status=400,
                content_type="application/json"
            )
        
        # Llamar a la función para agrupar las noticias
        print(f"ℹ️ Procesando {len(noticias)} noticias...")
        noticias_agrupadas = agrupar_noticias(noticias)
        
        # Devolver las noticias agrupadas como respuesta
        return https_fn.Response(
            json.dumps(noticias_agrupadas, ensure_ascii=False, indent=2),
            content_type="application/json",
            status=200
        )
    
    except Exception as e:
        error_message = f"Error: {str(e)}"
        print(f"❌ Error en procesar_noticias: {error_message}")
        traceback.print_exc()
        return https_fn.Response(
            json.dumps({"error": error_message}, ensure_ascii=False),
            status=500,
            content_type="application/json"
        )
