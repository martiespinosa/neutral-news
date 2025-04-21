import xml.etree.ElementTree as ET
import re
import requests
import threading
import time
from urllib.parse import urlparse
from collections import defaultdict
from bs4 import BeautifulSoup
from .models import News, Media

# Thread local storage for session management
thread_local = threading.local()

class DomainRateLimiter:
    """Controls request frequency to specific domains"""
    def __init__(self, delay=1.0):
        self.delay = delay
        self.last_calls = {}
        self.lock = threading.Lock()

    def wait(self, domain):
        """Wait appropriate time before making a request to the domain"""
        if not domain:
            return
            
        with self.lock:
            now = time.time()
            if domain in self.last_calls:
                elapsed = now - self.last_calls[domain]
                if elapsed < self.delay:
                    time.sleep(self.delay - elapsed)
            self.last_calls[domain] = time.time()

class NewsScraper:
    """Advanced news content scraper with customizable parameters"""
    
    # Error patterns to detect in page content
    ERROR_PATTERNS = [
        r"404", r"página no encontrada", r"not found", r"no existe",
        r"error 404", r"no se ha encontrado", r"no disponible", 
        r"Esta funcionalidad es sólo para registrados",
    ]
    
    # Patterns for generic pages that aren't articles
    GENERIC_PATTERNS = [
        r"bienvenido", r"acerca de", r"quiénes somos", r"contacto", 
        r"home", r"inicio", r"política de privacidad", r"aviso legal"
    ]
    
    def __init__(self, 
                 min_word_threshold=30,      # Min words for RSS content to be acceptable
                 min_scraped_words=200,      # Min words for scraped content to be acceptable
                 max_scraped_words=2000,     # Max words for scraped content (truncate if longer)
                 request_timeout=10,         # Request timeout in seconds
                 domain_delay=1.0):          # Seconds to wait between requests to same domain
        
        self.min_word_threshold = min_word_threshold
        self.min_scraped_words = min_scraped_words
        self.max_scraped_words = max_scraped_words
        self.request_timeout = request_timeout
        self.rate_limiter = DomainRateLimiter(domain_delay)
        
        # Statistics tracking
        self.error_counts = defaultdict(int)
        self.stats = defaultdict(int)
        self.processed_articles = set()
    
    def get_session(self):
        """Returns a persistent session for making requests"""
        if not hasattr(thread_local, "session"):
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
                'Accept-Language': 'es-ES,es;q=0.9,en;q=0.5'
            })
            thread_local.session = session
        return thread_local.session
    
    def get_domain(self, url):
        """Extracts the domain from the URL"""
        try:
            parsed = urlparse(url)
            return parsed.netloc if parsed.netloc else None
        except:
            return None
    
    def is_duplicate(self, content):
        """Checks if content has been processed before"""
        if not content:
            return True
            
        content_hash = hash(content)
        if content_hash in self.processed_articles:
            self.error_counts["duplicate_content"] += 1
            return True
        self.processed_articles.add(content_hash)
        return False
    
    def contains_error_message(self, text):
        """Checks if text contains error messages"""
        if not text:
            return True
            
        text = text.lower()
        return any(re.search(pattern, text) for pattern in self.ERROR_PATTERNS)
    
    def is_generic_page(self, title, content):
        """Checks if the page is a generic page rather than an article"""
        if not title or not content:
            return True
            
        text = f"{title} {content}".lower()
        return any(re.search(pattern, text) for pattern in self.GENERIC_PATTERNS)
    
    def clean_content(self, content):
        """Cleans the content by removing cookie notices and other non-article text"""
        if not content:
            return ""
            
        # Remove cookie/registration notices by sentence
        sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', content)
        cleaned_sentences = []
        
        for sentence in sentences:
            # Skip sentences with unwanted content
            if any(term in sentence.lower() for term in ["cookie", "regist", "suscri", "privacidad"]):
                continue
            cleaned_sentences.append(sentence)
        
        # Rejoin and normalize whitespace
        cleaned_content = " ".join(cleaned_sentences).strip()
        cleaned_content = re.sub(r'\s+', ' ', cleaned_content)
        
        # Truncate if too long
        words = cleaned_content.split()
        if len(words) > self.max_scraped_words:
            cleaned_content = " ".join(words[:self.max_scraped_words])
            
        return cleaned_content
    
    def extract_text_from_article(self, soup):
        """Extracts the main content from an article page"""
        # Try to find content in typical containers
        for selector in ['article', '.article-body', '.content', '.entry-content', 'main', '#main-content']:
            container = soup.select_one(selector)
            if container:
                paragraphs = container.find_all('p')
                if paragraphs:
                    # Get paragraphs that aren't too short (to avoid captions, ads, etc.)
                    valid_texts = [p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 30]
                    if valid_texts:
                        content = " ".join(valid_texts)
                        return self.clean_content(content)
        
        # Fallback: get all paragraphs in the document
        paragraphs = soup.find_all('p')
        valid_texts = [p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 30]
        
        if valid_texts:
            content = " ".join(valid_texts)
            return self.clean_content(content)
        
        return ""
    
    def needs_scraping(self, description_text):
        """Determines if a description needs additional content"""
        if not description_text:
            return True
            
        word_count = len(description_text.split())
        return word_count < self.min_word_threshold
    
    def scrape_content(self, url):
        """Scrapes content from the given URL with quality checks and rate limiting"""
        if not url:
            self.error_counts["empty_url"] += 1
            return ""
            
        try:
            # Get domain and apply rate limiting
            domain = self.get_domain(url)
            self.rate_limiter.wait(domain)
            
            # Make the request
            session = self.get_session()
            self.stats["requests_made"] += 1
            response = session.get(url, timeout=self.request_timeout)
            
            # Check response status
            if response.status_code != 200:
                self.error_counts[f"http_{response.status_code}"] += 1
                return ""
                
            # Parse the page content
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Check for error pages
            page_text = soup.get_text(separator=" ", strip=True)
            if self.contains_error_message(page_text):
                self.error_counts["error_page_detected"] += 1
                return ""
                
            # Extract the article content
            content = self.extract_text_from_article(soup)
            
            # Validate the content quality
            word_count = len(content.split())
            if word_count < self.min_scraped_words:
                self.error_counts["insufficient_content"] += 1
                return ""
                
            if self.is_duplicate(content):
                return ""
                
            # Successfully scraped content
            self.stats["successful_scrapes"] += 1
            return content
            
        except requests.exceptions.RequestException as e:
            self.error_counts["request_error"] += 1
            print(f"Request error when scraping {url}: {str(e)}")
            return ""
        except Exception as e:
            self.error_counts["scraping_error"] += 1
            print(f"Error when scraping {url}: {str(e)}")
            return ""

def normalize_string(s):
    """Helper function to normalize strings"""
    return s.lower().strip()

def clean_html(html_content):
    """Remove HTML tags and clean content using BeautifulSoup"""
    if not html_content:
        return ""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        return soup.get_text(separator=' ', strip=True)
    except Exception as e:
        print(f"Error cleaning HTML: {str(e)}")
        return html_content  # Return original content if cleaning fails

def parse_xml(data, medium, scraper=None):
    """
    Parse XML content from RSS feed and extract news items
    
    Args:
        data: XML content from RSS feed
        medium: Source media identifier
        scraper: Optional NewsScraper instance (will create one if None)
    """
    # Initialize scraper if not provided
    if scraper is None:
        scraper = NewsScraper()
        
    news_list = []
    try:
        root = ET.fromstring(data)
        
        # Look for namespace for media content (some RSS use it)
        namespaces = {'media': 'http://search.yahoo.com/mrss/'}
        
        # Find all 'item' elements in the RSS
        for item in root.findall('.//item'):
            # Extract title
            title = item.find('title')
            title_raw = title.text.strip() if title is not None and title.text else ""
            title_text = clean_html(title_raw)
            
            # Extract description
            description = item.find('description')
            description_raw = description.text.strip() if description is not None and description.text else ""
            description_text = clean_html(description_raw)
            
            # Extract link
            link = item.find('link')
            link_text = link.text.strip() if link is not None and link.text else ""
            
            # Extract publication date
            pub_date = item.find('pubDate')
            pub_date_text = pub_date.text.strip() if pub_date is not None and pub_date.text else ""
            
            # Find categories
            categories = []
            for category in item.findall('category'):
                if category.text:
                    categories.append(clean_html(category.text.strip()))
            
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
            
            # Method 3: look in HTML content with BeautifulSoup
            if not image_url and description_raw:
                try:
                    soup = BeautifulSoup(description_raw, 'html.parser')
                    img_tag = soup.find('img')
                    if img_tag and 'src' in img_tag.attrs:
                        image_url = img_tag['src']
                except Exception as e:
                    print(f"Error extracting image from description: {str(e)}")
            
            # Determine category
            final_category = "sinCategoria"  # Default category
            if categories:
                # You could implement more complex logic to map categories
                final_category = categories[0]
            
            # Check if the description needs additional content using the scraper's criteria
            if scraper.needs_scraping(description_text) and link_text:
                print(f"Description too short ({len(description_text.split())} words), scraping content from: {link_text}")
                scraped_content = scraper.scrape_content(link_text)
                if scraped_content:
                    description_text = scraped_content
            
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
    
    except Exception as e:
        print(f"Error parsing XML: {str(e)}")
        import traceback
        traceback.print_exc()
    
    return news_list

def fetch_all_rss():
    """
    Fetch RSS feeds from all configured media sources
    """
    all_news = []
    
    # Create a shared scraper instance with custom parameters
    scraper = NewsScraper(
        min_word_threshold=30,      # RSS content shorter than this will trigger scraping
        min_scraped_words=200,      # Minimum words for scraped content to be accepted
        max_scraped_words=1500,     # Maximum words to keep from scraped content
        request_timeout=15,         # Timeout for HTTP requests
        domain_delay=1.5            # Seconds between requests to the same domain
    )
    
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
            
            # Parse XML and get news using the shared scraper
            medium_news = parse_xml(response.text, medium, scraper)
            all_news.extend(medium_news)
            print(f"Parsed {len(medium_news)} news for {press_media.name}")
        except Exception as e:
            print(f"Error loading RSS for {press_media.name}: {str(e)}")
            import traceback
            traceback.print_exc()
    
    # Print scraper statistics
    print(f"Scraping statistics: {dict(scraper.stats)}")
    print(f"Error counts: {dict(scraper.error_counts)}")
    
    return all_news