import traceback

from src.grouping import agrupar_noticias
from src.storage import get_news_for_grouping
from src.storage import update_groups_in_firestore
from src.neutralization import neutralize_news_groups

def process_news_groups():
    try:
        # Get news for grouping with la función modificada
        news_for_grouping, news_docs = get_news_for_grouping()
       
        if not news_for_grouping:
            print("No news to group")
            return 0
                
        # Perform grouping process directly
        grouped_news = agrupar_noticias(news_for_grouping)
                
        # Update groups in Firestore
        updated_count = update_groups_in_firestore(grouped_news, news_docs)

        # Neutralizar los grupos recién creados y guardarlos
        neutralized_count = neutralize_news_groups(grouped_news, news_docs)

        print(f"Groups updated for {updated_count} news, neutralized {neutralized_count} groups")
        return updated_count
    except Exception as e:
        print(f"Error in process_news_groups: {str(e)}")
        traceback.print_exc()
        return 0