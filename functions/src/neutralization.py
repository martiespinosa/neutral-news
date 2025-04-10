import re
import traceback
from src.config import get_text_bison_model

def call_vertex_ai(prompt, max_length=512, temperature=0.4):
    text_bison_model = get_text_bison_model()

    try:
        response = text_bison_model.predict(
            prompt,
            max_output_tokens=max_length,
            temperature=temperature,
            top_k=40,
            top_p=0.9,
        )
        generated_text = response.text
        # Limpieza del texto
        result_markers = ["Título neutral:", "Descripción neutral:", "Hechos objetivos:", "Versión corregida:", "Versión corregida neutral:"]
        for marker in result_markers:
            if marker in generated_text:
                parts = generated_text.split(marker, 1)
                if len(parts) > 1:
                    generated_text = parts[1].strip()
        generated_text = re.sub(r"Tu tarea es.*?:", "", generated_text)
        generated_text = re.sub(r"Como redactor periodístico.*?:", "", generated_text)
        return generated_text.strip()
    except Exception as e:
        print(f"Error calling Vertex AI: {str(e)}")
        traceback.print_exc()
        raise

def neutralize_texts(texts, text_type):
    if not texts or len(texts) == 0:
        return "No se proporcionaron textos para procesar."
    
    texts = texts[:5]  # Limitar a 5 textos por grupo
    cleaned_texts = [re.sub(r'<[^>]+>', '', text) for text in texts]
    combined_texts = "\n\n".join([f"Texto {i+1}: {text[:500]}" for i, text in enumerate(cleaned_texts)])
    
    if text_type == "título":
        prompt = f"""
        Los siguientes son títulos periodísticos sobre el mismo tema:
        
        {combined_texts}
        
        Crea un nuevo título neutral y objetivo basado en estos textos. El título debe:
        - Contener solo hechos verificables
        - No incluir lenguaje valorativo
        - Ser conciso (máximo 15 palabras)
        - No usar adjetivos subjetivos
        
        Título neutral:
        """
        max_len = 128
    else:  # descripción
        prompt = f"""
        Las siguientes son descripciones periodísticas sobre el mismo tema:
        
        {combined_texts}
        
        Crea una nueva descripción neutral y objetiva basada en estos textos. La descripción debe:
        - Contener solo hechos verificables
        - No incluir lenguaje valorativo o sesgado
        - No usar adjetivos subjetivos
        - Ser clara y concisa
        
        Descripción neutral:
        """
        max_len = 200
    
    try:
        neutral_text = call_vertex_ai(prompt, max_length=max_len, temperature=0.3)
        if len(neutral_text) >= 10 and not any(word in neutral_text.lower() for word in ["sesgada", "tu tarea", "revisar"]):
            return neutral_text
        return "No se pudo generar una versión neutral válida."
    except Exception as e:
        print(f"Error neutralizing {text_type}: {str(e)}")
        return "Error al neutralizar el texto"

def neutralize_news_groups(grouped_news, news_docs):
    from datetime import datetime
    from src.config import initialize_firebase
    
    db = initialize_firebase()
    batch = db.batch()
    neutralized_count = 0
    current_batch = 0
    
    groups = {}
    for item in grouped_news:
        group_num = item["group_number"]
        if group_num is not None:
            if group_num not in groups:
                groups[group_num] = []
            groups[group_num].append(item["id"])
    
    for group_num, news_ids in groups.items():
        if len(news_ids) < 2:
            continue
        
        titles = []
        descriptions = []
        for news_id in news_ids:
            if news_id in news_docs:
                doc_data = news_docs[news_id].to_dict()
                titles.append(doc_data["title"])
                descriptions.append(doc_data["description"])
        
        neutral_title = neutralize_texts(titles, "título")
        neutral_desc = neutralize_texts(descriptions, "descripción")
        
        group_ref = db.collection('neutralized_groups').document(str(group_num))
        group_data = {
            "group_number": int(group_num),
            "news_ids": news_ids,
            "neutral_title": neutral_title,
            "neutral_description": neutral_desc,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        batch.set(group_ref, group_data, merge=True)
        neutralized_count += 1
        current_batch += 1
        
        if current_batch >= 450:
            batch.commit()
            batch = db.batch()
            current_batch = 0
    
    if current_batch > 0:
        batch.commit()
    
    print(f"Neutralized and stored {neutralized_count} groups in Firestore")
    return neutralized_count