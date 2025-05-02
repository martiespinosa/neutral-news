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

        print(f"Groups updated for {updated_count} news, neutralized {neutralized_count} groups")
        return updated_count
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
            grupos[grupo].append({
                "id": noticia.get("id"),
                "title": noticia.get("title"),
                "scraped_description": noticia.get("scraped_description"),
                "source_medium": noticia.get("source_medium"),
            })

    return [{"group": g, "sources": s} for g, s in grupos.items()]
