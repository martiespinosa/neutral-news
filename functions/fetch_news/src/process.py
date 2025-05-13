import traceback
from collections import defaultdict
from src.grouping import group_news
from src.storage import get_news_for_grouping
from src.storage import update_groups_in_firestore
from src.neutralization import neutralize_and_more

def process_news_groups(fetch_all_news=False):
    try:
        # Get news for grouping with the option to fetch all news documents
        news_for_grouping, news_docs = get_news_for_grouping(fetch_all_news=fetch_all_news)
        
        if not news_for_grouping:
            print("No news to group")
            return 0
                
        # Perform grouping process directly
        grouped_news: list = group_news(news_for_grouping)
        groups_prepared = prepare_groups_for_neutralization(grouped_news)
        print(f"ℹ️ Prepared {len(groups_prepared)} news groups for neutralization")

        # Update groups in Firestore - pass the prepared groups instead of raw grouped news
        updated_count, created_count, updated_groups, created_groups = update_groups_in_firestore(groups_prepared, news_docs)
        print(f"Updated {updated_count} news items in {len(updated_groups)} groups")
        print(f"Created {created_count} new news group assignments")
        print(f"Updated groups: {updated_groups}")
        print(f"Created groups: {created_groups}")
        
        # Neutralizar los grupos recién creados y guardarlos
        neutralized_count = neutralize_and_more(groups_prepared)

        print(f"Neutralized {neutralized_count} groups")
    except Exception as e:
        print(f"Error in process_news_groups: {str(e)}")
        traceback.print_exc()
        return 0

def prepare_groups_for_neutralization(grouped_news) -> list:
    grupos = defaultdict(list)
    
    # Track valid sources per group without and with fallback
    valid_sources_no_fallback = defaultdict(int)
    valid_sources_with_fallback = defaultdict(int)
    groups_using_fallback = set()
    
    # Track which groups are existing vs new
    existing_groups = set()
    
    # Process each news item
    for noticia in grouped_news:
        grupo = noticia.get("group")
        if grupo is not None:
            grupo = int(float(grupo))
            
            # Check if this is an existing group
            if noticia.get("existing_group") is not None:
                existing_groups.add(grupo)
                
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
            # Mark whether this is an existing or new group
            is_existing = grupo in existing_groups
            valid_groups.append({
                "group": grupo, 
                "sources": sources,
                "is_existing_group": is_existing
            })
    
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
    
    # Log number of existing vs new groups
    new_groups_count = sum(1 for g in valid_groups if not g["is_existing_group"])
    existing_groups_count = sum(1 for g in valid_groups if g["is_existing_group"])
    print(f"🆕 Prepared {new_groups_count} new groups and {existing_groups_count} existing groups")
    
    return valid_groups