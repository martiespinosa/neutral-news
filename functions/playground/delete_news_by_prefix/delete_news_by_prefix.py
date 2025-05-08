import firebase_admin
from firebase_admin import credentials, firestore
import re
import os

# Ruta al archivo JSON de tu cuenta de servicio
SERVICE_ACCOUNT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../neutralnews-ca548-firebase-adminsdk-fbsvc-b2a2b9fa03.json'))
# Patrones de texto que indican contenido genérico o vacío
GENERIC_PATTERNS = [
    r'No hay información disponible',
    r'No hay información disponible para análisis',
    r'No se proporcionaron titulares',
    r'No se proporcionaron.*descripciones',
    r'Se requiere información específica',
    r'No se han proporcionado titulares',
]

# Longitud máxima permitida para considerar que el texto es corto (seguro de borrar)
MAX_LENGTH = 300

def is_generic_and_short(text):
    if not isinstance(text, str):
        return False
    if len(text) > MAX_LENGTH:
        return False
    for pattern in GENERIC_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False

def main():
    cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
    firebase_admin.initialize_app(cred)
    db = firestore.client()

    docs = db.collection('neutral_news').stream()

    count = 0
    for doc in docs:
        data = doc.to_dict()
        description = data.get('neutral_description', '')
        title = data.get('neutral_title', '')
        
        # Check both title and description for generic content
        generic_description = is_generic_and_short(description)
        generic_title = is_generic_and_short(title)
        
        if generic_description or generic_title:
            reason = []
            if generic_title:
                reason.append("generic title")
            if generic_description:
                reason.append("generic description")
            
            print(f"🗑️ Deleting: {doc.id} -> {reason} -> {title[:30]}... / {description[:30]}...")
            doc.reference.delete()
            count += 1

    print(f"\n✅ Finished. Deleted {count} generic/short documents.")

if __name__ == '__main__':
    main()