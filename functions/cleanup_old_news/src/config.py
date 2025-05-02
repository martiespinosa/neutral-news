import traceback

def initialize_firebase():
    """
    Función para inicializar Firebase solo cuando sea necesario
    """
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
        try:
            app = firebase_admin.get_app()
        except ValueError:
            cred = credentials.ApplicationDefault()
            app = firebase_admin.initialize_app(cred)
        return firestore.client()
    except Exception as e:
        print(f"Error initializing Firebase: {str(e)}")
        traceback.print_exc()
        raise