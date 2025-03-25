import requests
import xml.etree.ElementTree as ET
import json
import uuid
import firebase_admin
from firebase_admin import credentials, auth, firestore
from firebase_functions import https_fn, scheduler_fn
from datetime import datetime, timedelta
import traceback

# Inicializar la app de Firebase
try:
    app = firebase_admin.get_app()
except ValueError:
    cred = credentials.ApplicationDefault()
    app = firebase_admin.initialize_app(cred)

# Inicializar Firestore
db = firestore.client()

# Clase para almacenar información sobre un medio
class PressMedia:
    def __init__(self, name, link):
        self.name = name
        self.link = link

# Enumerar los medios disponibles (adaptado de tu código Swift)
class Media:
    EL_PAIS = "elPais"
    EL_MUNDO = "elMundo"
    LA_VANGUARDIA = "laVanguardia"
    EL_PERIODICO = "elPeriodico"
    
    @staticmethod
    def get_all():
        return [Media.EL_PAIS, Media.EL_MUNDO, Media.LA_VANGUARDIA, Media.EL_PERIODICO]
    
    @staticmethod
    def get_press_media(medium):
        media_map = {
            Media.EL_PAIS: PressMedia("El País", "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada"),
            Media.EL_MUNDO: PressMedia("El Mundo", "https://e00-elmundo.uecdn.es/elmundo/rss/portada.xml"),
            Media.LA_VANGUARDIA: PressMedia("La Vanguardia", "https://www.lavanguardia.com/rss/home.xml"),
            Media.EL_PERIODICO: PressMedia("El Periódico", "https://www.elperiodico.com/es/rss/rss_portada.xml")
        }
        return media_map.get(medium)

# Clase para representar una noticia
class News:
    def __init__(self, title, description, category, image_url, link, pub_date, source_medium):
        self.id = str(uuid.uuid4())
        self.title = title
        self.description = description
        self.category = category
        self.image_url = image_url
        self.link = link
        self.pub_date = pub_date
        self.source_medium = source_medium
        self.group = None  # Inicialmente sin grupo
        self.created_at = datetime.now()

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "imageUrl": self.image_url,
            "link": self.link,
            "pubDate": self.pub_date,
            "sourceMedium": self.source_medium,
            "group": self.group,
            "created_at": self.created_at
        }

# Función auxiliar para normalizar strings
def normalize_string(s):
    return s.lower().strip()

# Función para parsear el XML de los RSS
def parse_xml(data, medium):
    news_list = []
    root = ET.fromstring(data)
    
    # Buscar namespace para media content (algunos RSS lo utilizan)
    namespaces = {'media': 'http://search.yahoo.com/mrss/'}
    
    # Buscar todos los elementos 'item' en el RSS
    for item in root.findall('.//item'):
        title = item.find('title')
        title_text = title.text.strip() if title is not None and title.text else ""
        
        description = item.find('description')
        description_text = description.text.strip() if description is not None and description.text else ""
        
        link = item.find('link')
        link_text = link.text.strip() if link is not None and link.text else ""
        
        pub_date = item.find('pubDate')
        pub_date_text = pub_date.text.strip() if pub_date is not None and pub_date.text else ""
        
        # Buscar categorías
        categories = []
        for category in item.findall('category'):
            if category.text:
                categories.append(category.text.strip())
        
        # Buscar imagen (varios métodos diferentes según el formato del RSS)
        image_url = ""
        # Método 1: usando namespace media
        media_content = item.find('.//media:content', namespaces)
        if media_content is not None and 'url' in media_content.attrib:
            image_url = media_content.attrib['url']
        
        # Método 2: buscar en enclosure
        if not image_url:
            enclosure = item.find('enclosure')
            if enclosure is not None and 'url' in enclosure.attrib and 'type' in enclosure.attrib:
                if enclosure.attrib['type'].startswith('image/'):
                    image_url = enclosure.attrib['url']
        
        # Método 3: buscar en el contenido HTML
        if not image_url and description_text:
            import re
            img_pattern = re.compile(r'<img[^>]+src="([^">]+)"')
            img_match = img_pattern.search(description_text)
            if img_match:
                image_url = img_match.group(1)
        
        # Determinar categoría
        final_category = "sinCategoria"  # Categoría por defecto
        if categories:
            # Aquí podrías implementar una lógica más compleja para mapear categorías
            final_category = categories[0]
        
        # Crear objeto News
        news_item = News(
            title_text,
            description_text,
            final_category,
            image_url,
            link_text,
            pub_date_text,
            medium
        )
        
        # Verificar si ya existe esta noticia (por URL)
        if not any(news.link == news_item.link for news in news_list):
            news_list.append(news_item)
    
    return news_list

# Función para guardar noticias en Firestore
def store_news_in_firestore(news_list):
    batch = db.batch()
    news_count = 0
    current_batch = 0
    
    for news in news_list:
        # Verificar si esta noticia ya existe en la base de datos por URL
        existing_news_query = db.collection('news').where('link', '==', news.link).limit(1)
        existing_news = [doc for doc in existing_news_query.stream()]
        
        if not existing_news:
            # Crear un nuevo documento en la colección 'news'
            news_ref = db.collection('news').document(news.id)
            batch.set(news_ref, news.to_dict())
            news_count += 1
            current_batch += 1
            
            # Firebase tiene un límite de 500 operaciones por lote
            if current_batch >= 450:
                batch.commit()
                batch = db.batch()
                current_batch = 0
    
    # Commit final del lote si hay operaciones pendientes
    if current_batch > 0:
        batch.commit()
    
    print(f"Guardadas {news_count} nuevas noticias en Firestore")
    return news_count

# Función para obtener noticias de Firestore para agruparlas
def get_news_for_grouping():
    # Obtener noticias que aún no tienen grupo asignado
    # o que fueron creadas en las últimas 24 horas
    time_threshold = datetime.now() - timedelta(hours=24)
    
    # Query para noticias sin grupo o recientes
    query = db.collection('news').where('group', '==', None)
    ungrouped_news = list(query.stream())
    
    recent_query = db.collection('news').where('created_at', '>=', time_threshold)
    recent_news = list(recent_query.stream())
    
    # Combinar y eliminar duplicados
    all_docs = {doc.id: doc for doc in ungrouped_news + recent_news}
    
    # Convertir documentos a formato requerido por la API de agrupación
    news_for_grouping = []
    for doc in all_docs.values():
        data = doc.to_dict()
        news_for_grouping.append({
            "id": data["id"],
            "titulo": data["title"],
            "cuerpo": data["description"]
        })
    
    print(f"Obtenidas {len(news_for_grouping)} noticias para agrupar")
    return news_for_grouping, all_docs

# Función para actualizar los grupos en Firestore
def update_groups_in_firestore(grouped_news, news_docs):
    batch = db.batch()
    updated_count = 0
    current_batch = 0
    
    for item in grouped_news:
        doc_id = item["id"]
        group_number = item["group_number"]
        
        if doc_id in news_docs:
            doc = news_docs[doc_id]
            doc_ref = doc.reference
            batch.update(doc_ref, {"group": group_number})
            updated_count += 1
            current_batch += 1
            
            # Firebase tiene un límite de 500 operaciones por lote
            if current_batch >= 450:
                batch.commit()
                batch = db.batch()
                current_batch = 0
    
    # Commit final del lote si hay operaciones pendientes
    if current_batch > 0:
        batch.commit()
    
    print(f"Actualizados grupos para {updated_count} noticias en Firestore")
    return updated_count

# Función para enviar las noticias al backend para agruparlas
def group_news():
    try:
        # Obtener noticias para agrupar
        news_for_grouping, news_docs = get_news_for_grouping()
        
        if not news_for_grouping:
            print("No hay noticias para agrupar")
            return 0
        
        # URL del backend de agrupación
        backend_url = "https://us-central1-neutralnews-ca548.cloudfunctions.net/procesar_noticias"
        
        # Obtener un token para autenticación
        custom_token = auth.create_custom_token("rss-scheduler-service")
        id_token_response = requests.post(
            "https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken",
            params={"key": "AIzaSyAa7UEFyITdwErrRdtV_h7GMZcZrIL_xwY"},
            json={"token": custom_token.decode('utf-8'), "returnSecureToken": True}
        )
        
        id_token_data = id_token_response.json()
        if "idToken" not in id_token_data:
            print(f"Error al obtener ID token: {id_token_data}")
            return 0
        
        id_token = id_token_data["idToken"]
        
        # Configurar la solicitud HTTP
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {id_token}"
        }
        
        # Realizar la solicitud HTTP
        print(f"Enviando {len(news_for_grouping)} noticias al backend para agrupar...")
        response = requests.post(
            backend_url,
            headers=headers,
            json=news_for_grouping
        )
        
        # Procesar la respuesta
        if response.status_code >= 200 and response.status_code < 300:
            # Decodificar la respuesta
            grouped_news = response.json()
            print(f"Noticias agrupadas recibidas del backend: {len(grouped_news)}")
            
            # Actualizar los grupos en Firestore
            updated_count = update_groups_in_firestore(grouped_news, news_docs)
            return updated_count
        else:
            print(f"Error HTTP {response.status_code}: {response.text}")
            return 0
    except Exception as e:
        print(f"Error en group_news: {str(e)}")
        traceback.print_exc()
        return 0

# Función para cargar RSS de todos los medios
def fetch_all_rss():
    all_news = []
    
    # Obtener noticias para cada medio
    for medium in Media.get_all():
        press_media = Media.get_press_media(medium)
        if not press_media:
            print(f"Medio no válido: {medium}")
            continue
        
        try:
            print(f"Cargando RSS para {press_media.name}...")
            response = requests.get(press_media.link)
            response.raise_for_status()  # Lanzar excepción si hay error HTTP
            
            # Parsear el XML y obtener las noticias
            medium_news = parse_xml(response.text, medium)
            all_news.extend(medium_news)
            print(f"Parseadas {len(medium_news)} noticias para {press_media.name}")
        except Exception as e:
            print(f"Error al cargar RSS para {press_media.name}: {str(e)}")
            traceback.print_exc()
    
    return all_news

# Función principal para cargar RSS (programada para ejecutarse cada hora)
@scheduler_fn.on_schedule(schedule="every 1 hours")
def fetch_and_store_rss(event: scheduler_fn.ScheduledEvent) -> None:
    try:
        print("Iniciando carga periódica de RSS...")
        
        # Obtener todas las noticias de los RSS
        all_news = fetch_all_rss()
        print(f"Total de noticias obtenidas: {len(all_news)}")
        
        # Guardar las noticias en Firestore
        if all_news:
            stored_count = store_news_in_firestore(all_news)
            print(f"Se guardaron {stored_count} nuevas noticias")
        else:
            print("No se encontraron noticias para guardar")
        
        # Procesar y agrupar las noticias
        print("Iniciando agrupación de noticias...")
        updated_count = group_news()
        print(f"Se actualizaron grupos para {updated_count} noticias")
        
        print("Procesamiento de RSS completado correctamente")
        return None
    except Exception as e:
        print(f"Error en fetch_and_store_rss: {str(e)}")
        traceback.print_exc()
        return None

# Función programada específicamente para agrupar noticias (puede ejecutarse con más frecuencia)
@scheduler_fn.on_schedule(schedule="every 1 hours")
def scheduled_group_news(event: scheduler_fn.ScheduledEvent) -> None:
    try:
        print("Iniciando agrupación programada de noticias...")
        updated_count = group_news()
        print(f"Se actualizaron grupos para {updated_count} noticias")
        return None
    except Exception as e:
        print(f"Error en scheduled_group_news: {str(e)}")
        traceback.print_exc()
        return None

# Endpoint HTTP para pruebas manuales de carga de RSS
@https_fn.on_request()
def fetch_rss_manually(req: https_fn.Request) -> https_fn.Response:
    try:
        print("Iniciando carga manual de RSS...")
        
        # Obtener todas las noticias de los RSS
        all_news = fetch_all_rss()
        print(f"Total de noticias obtenidas: {len(all_news)}")
        
        # Guardar las noticias en Firestore
        if all_news:
            stored_count = store_news_in_firestore(all_news)
            print(f"Se guardaron {stored_count} nuevas noticias")
        
        # Procesar y agrupar las noticias
        print("Iniciando agrupación de noticias...")
        updated_count = group_news()
        print(f"Se actualizaron grupos para {updated_count} noticias")
        
        return https_fn.Response(
            json.dumps({
                "status": "success",
                "news_fetched": len(all_news),
                "news_stored": stored_count if 'stored_count' in locals() else 0,
                "groups_updated": updated_count
            }, ensure_ascii=False),
            content_type="application/json"
        )
    except Exception as e:
        error_message = f"Error: {str(e)}"
        print(f"Error en fetch_rss_manually: {error_message}")
        traceback.print_exc()
        return https_fn.Response(
            json.dumps({"error": error_message}, ensure_ascii=False),
            status=500,
            content_type="application/json"
        )

# Endpoint HTTP para pruebas manuales de agrupación
@https_fn.on_request()
def group_news_manually(req: https_fn.Request) -> https_fn.Response:
    try:
        print("Iniciando agrupación manual de noticias...")
        updated_count = group_news()
        
        return https_fn.Response(
            json.dumps({
                "status": "success",
                "groups_updated": updated_count
            }, ensure_ascii=False),
            content_type="application/json"
        )
    except Exception as e:
        error_message = f"Error: {str(e)}"
        print(f"Error en group_news_manually: {error_message}")
        traceback.print_exc()
        return https_fn.Response(
            json.dumps({"error": error_message}, ensure_ascii=False),
            status=500,
            content_type="application/json"
        )
