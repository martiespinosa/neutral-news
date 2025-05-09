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
    
    # Track valid sources per group without and with fallback
    valid_sources_no_fallback = defaultdict(int)
    valid_sources_with_fallback = defaultdict(int)
    groups_using_fallback = set()
    
    # Process each news item
    for noticia in grouped_news:
        grupo = noticia.get("group")
        if grupo is not None:
            grupo = int(float(grupo))
            
            # Get title and primary description
            title = noticia.get("title", "")
            description = noticia.get("scraped_description", "")
            
            # Count valid sources without fallback
            if title and title.strip() and description and description.strip():
                valid_sources_no_fallback[grupo] += 1
                valid_sources_with_fallback[grupo] += 1
                
                grupos[grupo].append({
                    "id": noticia.get("id"),
                    "title": title,
                    "scraped_description": description,
                    "source_medium": noticia.get("source_medium"),
                })
            else:
                # Try fallback
                fallback_description = noticia.get("description", "")
                if title and title.strip() and fallback_description and fallback_description.strip():
                    groups_using_fallback.add(grupo)
                    valid_sources_with_fallback[grupo] += 1
                    
                    grupos[grupo].append({
                        "id": noticia.get("id"),
                        "title": title,
                        "scraped_description": fallback_description,
                        "source_medium": noticia.get("source_medium"),
                    })
    
    # Identify which groups were saved by fallback
    groups_saved_by_fallback = []
    groups_not_saved_by_fallback = []
    
    for grupo in groups_using_fallback:
        if valid_sources_no_fallback[grupo] < 2 and valid_sources_with_fallback[grupo] >= 2:
            groups_saved_by_fallback.append(grupo)
        elif valid_sources_with_fallback[grupo] < 2:
            groups_not_saved_by_fallback.append(grupo)
    
    # Create final list of valid groups
    valid_groups = []
    for grupo, sources in grupos.items():
        if len(sources) >= 2:
            valid_groups.append({"group": grupo, "sources": sources})
    
    # Log statistics
    insufficient_groups = [g for g, s in grupos.items() if len(s) < 2]
    if insufficient_groups:
        print(f"⚠️ {len(insufficient_groups)} groups had fewer than 2 valid sources: {sorted(insufficient_groups)}")
    
    if groups_saved_by_fallback:
        print(f"✅ {len(groups_saved_by_fallback)} groups were saved by fallback descriptions: {sorted(groups_saved_by_fallback)}")
    
    if groups_not_saved_by_fallback:
        print(f"❌ {len(groups_not_saved_by_fallback)} groups used fallback but still failed validation: {sorted(groups_not_saved_by_fallback)}")
    
    total_groups_with_fallback = len(groups_using_fallback)
    if total_groups_with_fallback > 0:
        print(f"📊 {total_groups_with_fallback} groups used fallback descriptions, {len(groups_saved_by_fallback)} were saved")
    
    return valid_groups