import firebase_admin
from firebase_admin import credentials, firestore

import re

# Ruta al archivo JSON de tu cuenta de servicio
SERVICE_ACCOUNT_PATH = r'C:\Dev\github\projecte-2-dam-24-25-neutral-news\neutralnews-ca548-firebase-adminsdk-fbsvc-b2a2b9fa03.json'

# Patrones de texto que indican contenido genérico o vacío
GENERIC_PATTERNS = [
    r'No hay información disponible',
    r'No se proporcionaron titulares',
    r'No se proporcionaron.*descripciones',
    r'Se requiere información específica',
    r'Imagen extraída de',
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

        if is_generic_and_short(description):
            print(f"🗑️ Deleting: {doc.id} -> {description[:60]}...")
            doc.reference.delete()
            count += 1

    print(f"\n✅ Finished. Deleted {count} generic/short documents.")

if __name__ == '__main__':
    main()
