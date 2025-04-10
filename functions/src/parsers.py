import xml.etree.ElementTree as ET
import re
import requests
from .models import News, Media

def normalize_string(s):
    """Helper function to normalize strings"""
    return s.lower().strip()

def parse_xml(data, medium):
    """
    Parse XML content from RSS feed and extract news items
    """
    news_list = []
    root = ET.fromstring(data)
    
    # Look for namespace for media content (some RSS use it)
    namespaces = {'media': 'http://search.yahoo.com/mrss/'}
    
    # Find all 'item' elements in the RSS
    for item in root.findall('.//item'):
        title = item.find('title')
        title_text = title.text.strip() if title is not None and title.text else ""
        
        description = item.find('description')
        description_text = description.text.strip() if description is not None and description.text else ""
        
        link = item.find('link')
        link_text = link.text.strip() if link is not None and link.text else ""
        
        pub_date = item.find('pubDate')
        pub_date_text = pub_date.text.strip() if pub_date is not None and pub_date.text else ""
        
        # Find categories
        categories = []
        for category in item.findall('category'):
            if category.text:
                categories.append(category.text.strip())
        
        # Find image (different methods depending on RSS format)
        image_url = ""
        # Method 1: using media namespace
        media_content = item.find('.//media:content', namespaces)
        if media_content is not None and 'url' in media_content.attrib:
            image_url = media_content.attrib['url']
        
        # Method 2: look in enclosure
        if not image_url:
            enclosure = item.find('enclosure')
            if enclosure is not None and 'url' in enclosure.attrib and 'type' in enclosure.attrib:
                if enclosure.attrib['type'].startswith('image/'):
                    image_url = enclosure.attrib['url']
        
        # Method 3: look in HTML content
        if not image_url and description_text:
            img_pattern = re.compile(r'<img[^>]+src="([^">]+)"')
            img_match = img_pattern.search(description_text)
            if img_match:
                image_url = img_match.group(1)
        
        # Determine category
        final_category = "sinCategoria"  # Default category
        if categories:
            # You could implement more complex logic to map categories
            final_category = categories[0]
        
        # Create News object
        news_item = News(
            title_text,
            description_text,
            final_category,
            image_url,
            link_text,
            pub_date_text,
            medium
        )
        
        # Check if this news already exists (by URL)
        if not any(news.link == news_item.link for news in news_list):
            news_list.append(news_item)
    
    return news_list

def fetch_all_rss():
    """
    Fetch RSS feeds from all configured media sources
    """
    all_news = []
    
    # Get news for each medium
    for medium in Media.get_all():
        press_media = Media.get_press_media(medium)
        if not press_media:
            print(f"Invalid medium: {medium}")
            continue
        
        try:
            print(f"Loading RSS for {press_media.name}...")
            response = requests.get(press_media.link)
            response.raise_for_status()  # Throw exception if HTTP error
            
            # Parse XML and get news
            medium_news = parse_xml(response.text, medium)
            all_news.extend(medium_news)
            print(f"Parsed {len(medium_news)} news for {press_media.name}")
        except Exception as e:
            print(f"Error loading RSS for {press_media.name}: {str(e)}")
            import traceback
            traceback.print_exc()
    
    return all_news