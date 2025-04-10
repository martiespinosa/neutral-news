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

def get_text_bison_model():
    """
    Función para obtener el modelo text-bison desde Vertex AI (modelo gestionado)
    """
    try:
        print("Loading text-bison model from Vertex AI Model Garden...")
        from vertexai.language_models import TextGenerationModel
        from vertexai import init

        init(project="neutralnews-ca548", location="us-central1")
        model = TextGenerationModel.from_pretrained("text-bison")
        print("text-bison model loaded successfully")
        return model
    except Exception as e:
        print(f"Failed to load text-bison model: {str(e)}")
        traceback.print_exc()
        raise