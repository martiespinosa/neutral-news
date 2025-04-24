import xml.etree.ElementTree as ET
import re
import requests
import threading
import time
import logging
from urllib.parse import urlparse
from collections import defaultdict  
from bs4 import BeautifulSoup
from newspaper import Article
from urllib.robotparser import RobotFileParser
from .models import News, Media
import logging
from src.storage import load_all_news_links_from_medium
import concurrent.futures

USER_AGENT = "NeutralNews/1.0 (+https://ezequielgaribotto.com)"
thread_local = threading.local()

class PrintHandler(logging.Handler):
    def emit(self, record):
        msg = self.format(record)
        print(msg)

class Logger:
    def __init__(self, name):
        self.logger = logging.getLogger(name)
        self.logger.handlers = []
        self.logger.propagate = False
        
        self.logger.setLevel(logging.DEBUG)
        handler = PrintHandler()
        formatter = logging.Formatter('%(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
    
    def debug(self, msg, *args, **kwargs):
        self.logger.debug(msg, *args, **kwargs)
        
    def info(self, msg, *args, **kwargs):
        self.logger.info(msg, *args, **kwargs)
        
    def warning(self, msg, *args, **kwargs):
        self.logger.warning(msg, *args, **kwargs)
        
    def error(self, msg, *args, **kwargs):
        self.logger.error(msg, *args, **kwargs)
        
    def critical(self, msg, *args, **kwargs):
        self.logger.critical(msg, *args, **kwargs)
        
    def exception(self, msg, *args, **kwargs):
        self.logger.exception(msg, *args, **kwargs)

class SafeSession(requests.Session):
    def __init__(self, robots_checker, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.robots_checker = robots_checker

    def get(self, url, *args, **kwargs):
        if not self.robots_checker.can_fetch(url):
            raise PermissionError(f"Blocked by robots.txt: {url}")
        return super().get(url, *args, **kwargs)


class DomainRateLimiter:
    def __init__(self, delay=1.0):
        self.delay = delay
        self.last_calls = {}
        self.lock = threading.Lock()

    def wait(self, domain):
        if not domain:
            return
        with self.lock:
            now = time.time()
            if domain in self.last_calls:
                elapsed = now - self.last_calls[domain]
                if elapsed < self.delay:
                    time.sleep(self.delay - elapsed)
            self.last_calls[domain] = time.time()

class RobotsChecker:
    def __init__(self, user_agent=USER_AGENT, timeout=10):
        self.user_agent = user_agent
        self.parsers = {}
        self.timeout = timeout

    def _get_parser(self, base_url):
        if (base_url in self.parsers) and (self.parsers[base_url] is not None):
            return self.parsers[base_url]
        rp = RobotFileParser()
        rp.set_url(base_url.rstrip('/') + '/robots.txt')
        try:
            rp.read()
        except Exception:
            rp = None
        self.parsers[base_url] = rp
        return rp

    def can_fetch(self, url):
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        rp = self._get_parser(base)
        if not rp:
            return True
        return rp.can_fetch(self.user_agent, url)

class NewsScraper:
    ERROR_PATTERNS = [
        r"404", r"página no encontrada", r"not found", r"no existe",
        r"error 404", r"no se ha encontrado", r"no disponible", 
        r"Esta funcionalidad es sólo para registrados",
    ]

    def __init__(self, min_word_threshold=30, min_scraped_words=200, max_scraped_words=2000, request_timeout=10, domain_delay=1.0):
        self.min_word_threshold = min_word_threshold
        self.min_scraped_words = min_scraped_words
        self.max_scraped_words = max_scraped_words
        self.request_timeout = request_timeout
        self.rate_limiter = DomainRateLimiter(domain_delay)
        self.error_counts = defaultdict(int)
        self.stats = defaultdict(int)
        self.processed_articles = set()
        self.logger = Logger("PrintLogger")

    def get_session(self, robots_checker):
        if not hasattr(thread_local, "session"):
            session = SafeSession(robots_checker)
            session.headers.update({
                'User-Agent': USER_AGENT,
                'Accept-Language': 'es-ES,es;q=0.9,en;q=0.5'
            })
            thread_local.session = session
        return thread_local.session

    def get_domain(self, url):
        try:
            return urlparse(url).netloc or None
        except Exception as e:
            self.logger.error(f"Error parsing domain from URL {url}: {e}")
            return None

    def is_duplicate(self, content):
        if not content:
            return True
        h = hash(content)
        if h in self.processed_articles:
            self.logger.warning("Duplicate content detected.")
            self.error_counts["duplicate_content"] += 1
            return True
        self.processed_articles.add(h)
        return False

    def contains_error_message(self, text):
        if not text:
            return True
        t = text.lower()
        return any(re.search(p, t) for p in self.ERROR_PATTERNS)

    def extract_with_newspaper(self, url):
        try:
            art = Article(url, language='es')
            art.config.browser_user_agent = USER_AGENT
            art.download()
            art.parse()
            return art.text
        except Exception as e:
            self.logger.warning(f"Newspaper3k failed for {url}: {e}")
        return ""

    def needs_scraping(self, desc_len):
        return desc_len < self.min_word_threshold

    def scrape_content(self, url):
        try:
            if not url:
                self.logger.warning("Empty URL provided.")
                self.error_counts["empty_url"] += 1
                return ""
            
            domain = self.get_domain(url)
            self.rate_limiter.wait(domain)
            self.stats["requests_made"] += 1
            content = self.extract_with_newspaper(url)

            if not content:
                self.logger.warning(f"Failed to extract content from {url}")
                self.error_counts["empty_content"] += 1
                return ""

            if self.is_duplicate(content):
                self.logger.warning(f"Duplicate content detected for {url}")
                self.error_counts["duplicate_content"] += 1
                return ""
            
            if len(content.split()) < self.min_scraped_words:
                self.logger.warning(f"Content too short ({len(content.split())} words) for {url}, minimum required: {self.min_scraped_words}")
                self.error_counts["short_content"] += 1
                return ""
            
            self.stats["successful_scrapes"] += 1
            return content
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request error for {url}: {e}")
            self.error_counts["request_error"] += 1
        except Exception as e:
            self.logger.warning(f"Unexpected error scraping {url}: {e}")
            self.error_counts["scraping_error"] += 1
        return ""


def transform_utf8(text):
    if not text:
        return ""
    try:
        return text.encode('utf-8').decode('utf-8')
    except UnicodeDecodeError:
        return text

def clean_html(html_content):
    if not html_content:
        return ""
    try:
        cleaned = BeautifulSoup(html_content, 'html.parser').get_text(separator=' ', strip=True)
        cleaned = transform_utf8(cleaned)
        return cleaned
    except:
        return html_content

def process_feed_items_parallel(items, medium, scraper, robots_checker, max_workers=5):
    news_list = []
    
    # Get all existing links from the database for this medium
    scraper.logger.info(f"Loading existing links for {medium}...")
    all_news_links = load_all_news_links_from_medium(medium)
    scraper.logger.info(f"Found {len(all_news_links)} existing links for {medium}")
    
    # Normalize all links for better comparison
    all_news_links_normalized = set()
    for link in all_news_links:
        if link:
            # Normalize links to handle http/https differences
            normalized = link.lower().replace("http://", "").replace("https://", "").rstrip("/")
            all_news_links_normalized.add(normalized)
    
    ns = {'media': 'http://search.yahoo.com/mrss/'}
    
    def process_item(item):
        try:
            l = item.find('link')
            link = l.text.strip() if l is not None and l.text else ""
            
            # Skip empty links
            if not link:
                return None
            
            # Normalize the current link for comparison
            normalized_link = link.lower().replace("http://", "").replace("https://", "").rstrip("/")
            
            # Check if link already exists in database using normalized comparison
            if normalized_link in all_news_links_normalized:
                process_item.skipped_count += 1
                return None
                
            # Add article counter for those being processed (not skipped)
            process_item.current_count += 1
            total_items = len(items)
            scraper.logger.info(f"Processing article {process_item.current_count}/{total_items} from {medium}")
            
            # Rest of your processing code...
            t = item.find('title')
            title = clean_html(t.text) if t is not None and t.text else ""
            d = item.find('description')
            desc = clean_html(d.text) if d is not None and d.text else ""
            pd = item.find('pubDate')
            pub = pd.text.strip() if pd is not None and pd.text else ""
            cats = [clean_html(c.text) for c in item.findall('category') if c.text]
            img = ""
            m = item.find('.//media:content', ns)
            if m is not None and 'url' in m.attrib:
                img = m.attrib['url']
            if not img:
                enc = item.find('enclosure')
                if enc is not None and enc.attrib.get('type','').startswith('image/'):
                    img = enc.attrib['url']
            if not img and desc:
                try:
                    soup = BeautifulSoup(desc, 'html.parser')
                    tag = soup.find('img')
                    if tag and 'src' in tag.attrs:
                        img = tag['src']
                except:
                    pass
            cat = cats[0] if cats else "sinCategoria"
            scr_desc = ""

            desc_len = len(desc.split()) if desc else 0

            if scraper.needs_scraping(desc_len) and link:
                if robots_checker.can_fetch(link):
                    scr_desc = scraper.scrape_content(link)
                    scraper.logger.info(f"Scraped description for article {process_item.current_count}/{total_items} from {medium}")
                    scraper.logger.error(f"Scraped content: {scr_desc})")
                else:
                    scraper.logger.warning(f"Blocked by robots.txt: {link}")
                    scraper.error_counts["blocked_by_robots"] += 1

            return News(
                title=title,
                description=desc,
                scraped_description=scr_desc,
                category=cat,
                image_url=img,
                link=link,
                pub_date=pub,
                source_medium=medium
            )
        except Exception as e:
            scraper.logger.warning(f"Error processing item: {e}")
            return None

    # Initialize counters
    process_item.current_count = 0
    process_item.skipped_count = 0
    
    # Process items in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_item, item) for item in items]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                news_list.append(result)
    
    # Log statistics
    scraper.logger.info(f"Processed {process_item.current_count} new articles from {medium}")
    scraper.logger.info(f"Skipped {process_item.skipped_count} duplicate articles from {medium}")
    
    return news_list

def parse_xml(data, medium, scraper, robots_checker):
    news_list = []
    try:
        root = ET.fromstring(data)
        items = list(root.findall('.//item'))
        scraper.logger.info(f"Found {len(items)} items in feed for {medium}")
        
        return process_feed_items_parallel(items, medium, scraper, robots_checker)
    except Exception as e:
        scraper.logger.info(f"Error parsing XML feed for medium {medium}: {e}")
    return news_list

def fetch_all_rss():
    all_news = []
    scraper = NewsScraper(min_word_threshold=100, min_scraped_words=100, max_scraped_words=800, request_timeout=5, domain_delay=1.5)
    robots_checker = RobotsChecker(user_agent=USER_AGENT)
    session = scraper.get_session(robots_checker)
    total_media = len(list(Media.get_all()))

    for medium in Media.get_all():
        pm = Media.get_press_media(medium)
        media_count = list(Media.get_all()).index(medium) + 1
        
        scraper.logger.info(f"Fetching RSS feed for medium {medium} ({media_count}/{total_media})...")
        if not pm:
            continue
        try:
            r = session.get(pm.link, timeout=5)            
            r.raise_for_status()
            news = parse_xml(r.text, medium, scraper, robots_checker)
            all_news.extend(news)
        except Exception as e:
            scraper.logger.warning(f"Failed to fetch or parse feed from {pm.link}: {e}")
    return all_news
