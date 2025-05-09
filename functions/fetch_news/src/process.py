import traceback
from collections import defaultdict
from src.grouping import group_news
from src.storage import get_news_for_grouping
from src.storage import update_groups_in_firestore
from src.neutralization import neutralize_and_more

def process_news_groups():
    try:
        # Get news for grouping with la función modificada
        news_for_grouping, news_docs = get_news_for_grouping()
       
        if not news_for_grouping:
            print("No news to group")
            return 0
                
        # Perform grouping process directly
        grouped_news = group_news(news_for_grouping)
                
        # Update groups in Firestore
        updated_count = update_groups_in_firestore(grouped_news, news_docs)

        # Neutralizar los grupos recién creados y guardarlos
        groups_prepared = prepare_groups_for_neutralization(grouped_news)
        neutralized_count = neutralize_and_more(groups_prepared)

        print(f"{updated_count} individual news items were updated with neutrality scores, neutralized {neutralized_count} groups")
    except Exception as e:
        print(f"Error in process_news_groups: {str(e)}")
        traceback.print_exc()
        return 0

def prepare_groups_for_neutralization(grouped_news):
    grupos = defaultdict(list)

    for noticia in grouped_news:
        grupo = noticia.get("group")
        if grupo is not None:
            grupo = int(float(grupo))
            
            # Only add sources with non-empty title and description
            title = noticia.get("title", "")
            description = noticia.get("scraped_description", "")
            
            # Validate content before adding to group
            if title and title.strip() and description and description.strip():
                grupos[grupo].append({
                    "id": noticia.get("id"),
                    "title": title,
                    "scraped_description": description,
                    "source_medium": noticia.get("source_medium"),
                })

    # Only return groups with at least 2 valid sources
    valid_groups = [{"group": g, "sources": s} for g, s in grupos.items() if len(s) >= 2]
    
    # Log groups with insufficient valid sources
    insufficient_groups = [g for g, s in grupos.items() if len(s) < 2]
    if insufficient_groups:
        print(f"⚠️ {len(insufficient_groups)} groups had fewer than 2 valid sources: {insufficient_groups}")
        
    return valid_groups
