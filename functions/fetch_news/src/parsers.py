import xml.etree.ElementTree as ET
import re
import requests
import threading
import time
import logging
from urllib.parse import urlparse
from collections import defaultdict  
from bs4 import BeautifulSoup
from newspaper import Article, Config
from urllib.robotparser import RobotFileParser
from .models import News, Media
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
        self.logger.setLevel(logging.INFO)
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

class RobotsChecker:
    def __init__(self, user_agent=USER_AGENT, timeout=10):
        self.user_agent = user_agent
        self.parsers = {}
        self.timeout = timeout
        self.logger = Logger("RobotsChecker")
    
    def _get_parser(self, base_url):
        if (base_url in self.parsers) and (self.parsers[base_url] is not None):
            return self.parsers[base_url]
        rp = RobotFileParser()
        rp.set_url(base_url.rstrip('/') + '/robots.txt')
        try:
            rp.read()
        except Exception as e:
            self.logger.debug(f"Could not read robots.txt at {base_url}: {e}")
            rp = None
        self.parsers[base_url] = rp
        return rp

    def can_fetch(self, url):
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        path = parsed.path or "/"
        
        rp = self._get_parser(base)
        if not rp:
            return True
            
        if rp.can_fetch(self.user_agent, url):
            return True
        
        reason = self._determine_blocking_rule(rp, path)
        return False, reason
        
    def _determine_blocking_rule(self, parser, path):
        try:
            if hasattr(parser, '_rules') and parser._rules:
                for rule in parser._rules:
                    if hasattr(rule, 'disallows') and path in str(rule.disallows):
                        return f"Path '{path}' matches disallow rule: {rule.disallows}"
                
                return f"Unknown rule in robots.txt is blocking access to {path}"
            return "Access denied by robots.txt (no specific rule information available)"
        except Exception:
            return "Access denied by robots.txt"

class SafeSession(requests.Session):
    def __init__(self, robots_checker, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.robots_checker = robots_checker
        self.logger = Logger("SafeSession")

    def get(self, url, *args, **kwargs):
        is_rss_feed = kwargs.pop('is_rss_feed', False)
        check_result = self.robots_checker.can_fetch(url)
        
        if check_result is not True:
            _, reason = check_result
            if is_rss_feed:
                # For RSS feeds, just warn but continue
                self.logger.warning(f"RSS feed possibly blocked by robots.txt: {url} - {reason}")
            else:
                # For content scraping, block access
                error_msg = f"Blocked by robots.txt: {url} - {reason}"
                self.logger.warning(error_msg)
                raise PermissionError(error_msg)
            
        return super().get(url, *args, **kwargs)

class DomainRateLimiter:
    def __init__(self, delay=1.0, max_domains=50):
        self.delay = delay
        self.last_calls = {}
        self.lock = threading.Lock()
        self.max_domains = max_domains

    def wait(self, domain):
        if not domain:
            return
        with self.lock:
            now = time.time()
            if len(self.last_calls) > self.max_domains:
                oldest_domains = sorted(self.last_calls.items(), key=lambda x: x[1])[:self.max_domains//2]
                for old_domain, _ in oldest_domains:
                    del self.last_calls[old_domain]
                    
            if domain in self.last_calls:
                elapsed = now - self.last_calls[domain]
                if elapsed < self.delay:
                    time.sleep(self.delay - elapsed)
            self.last_calls[domain] = time.time()

class NewsScraper:
    ERROR_PATTERNS = [
        r"404", r"página no encontrada", r"not found", r"no existe",
        r"error 404", r"no se ha encontrado", r"no disponible", 
        r"Esta funcionalidad es sólo para registrados",
    ]
    
    NEWSPAPER_CONFIG = Config()
    NEWSPAPER_CONFIG.browser_user_agent = USER_AGENT
    NEWSPAPER_CONFIG.request_timeout = 10
    NEWSPAPER_CONFIG.fetch_images = False
    NEWSPAPER_CONFIG.memoize_articles = False
    NEWSPAPER_CONFIG.thread_number = 1

    def __init__(self, min_word_threshold=30, min_scraped_words=200, request_timeout=10, domain_delay=1.0):
        self.min_word_threshold = min_word_threshold
        self.min_scraped_words = min_scraped_words
        self.request_timeout = request_timeout
        self.rate_limiter = DomainRateLimiter(domain_delay)
        self.error_counts = defaultdict(int)
        self.stats = defaultdict(int)
        self.processed_articles = set()
        self.logger = Logger("NewsScraper")

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
            art = Article(url, language='es', config=self.NEWSPAPER_CONFIG)
            art.download()
            art.parse()
            return art.text
        except Exception as e:
            self.error_counts["newspaper_fail"] += 1
        return ""

    def needs_scraping(self, desc_len):
        return desc_len < self.min_word_threshold

    def scrape_content(self, url):
        try:
            if not url:
                self.error_counts["empty_url"] += 1
                return ""
            
            domain = self.get_domain(url)
            self.rate_limiter.wait(domain)
            self.stats["requests_made"] += 1
            content = self.extract_with_newspaper(url)

            if not content:
                self.error_counts["empty_content"] += 1
                return ""

            if self.is_duplicate(content):
                self.error_counts["duplicate_content"] += 1
                return ""
            
            word_count = len(content.split())
            if word_count < self.min_scraped_words:
                self.error_counts["short_content"] += 1
                return ""
            
            self.stats["successful_scrapes"] += 1
            return content
        except requests.exceptions.RequestException as e:
            self.error_counts["request_error"] += 1
        except Exception as e:
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

def process_feed_items_parallel(items, medium, scraper, robots_checker, max_workers=20):
    all_news_links = load_all_news_links_from_medium(medium)
    all_news_links_normalized = set()
    for link in all_news_links:
        if link:
            normalized = link.lower().replace("http://", "").replace("https://", "").rstrip("/")
            all_news_links_normalized.add(normalized)
    
    ns = {'media': 'http://search.yahoo.com/mrss/'}
    valid_items = []
    skipped_count = 0
    
    for item in items:
        l = item.find('link')
        link = l.text.strip() if l is not None and l.text else ""
        if not link:
            continue
        
        normalized_link = link.lower().replace("http://", "").replace("https://", "").rstrip("/")
        if normalized_link in all_news_links_normalized:
            skipped_count += 1
            continue
        valid_items.append(item)
    
    scraper.logger.info(f"Medium {medium}: {len(valid_items)} new articles, {skipped_count} duplicates")
    
    current_count = 0
    news_list = []
    counter_lock = threading.Lock()
    
    def process_item(item):
        nonlocal current_count
        try:
            l = item.find('link')
            link = l.text.strip() if l is not None and l.text else ""
            
            with counter_lock:
                current_count += 1
            
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
                try:
                    can_fetch_result = robots_checker.can_fetch(link)
                    if can_fetch_result is True: 
                        scr_desc = scraper.scrape_content(link)
                    else:
                        # When robots.txt blocks content scraping, use the basic description
                        # and log but continue processing
                        scraper.error_counts["blocked_by_robots"] += 1
                        if isinstance(can_fetch_result, tuple) and len(can_fetch_result) == 2:
                            scraper.logger.warning(f"Blocked by robots.txt: {link} - Reason: {can_fetch_result[1]}")
                        # Use the description we already have instead of scraping
                        scr_desc = desc if desc else ""
                except Exception as r_exc:
                    scraper.logger.error(f"Exception during robots_checker.can_fetch for link {link}: {r_exc}", exc_info=True)
                    # Use the existing description if there's any issue
                    scr_desc = desc if desc else ""
            
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
            # Enhanced logging for diagnosis
            error_link_info = "Unknown link"
            error_title_info = "Unknown title"
            try:
                l_tag = item.find('link')
                if l_tag is not None and l_tag.text:
                    error_link_info = l_tag.text.strip()
                t_tag = item.find('title')
                if t_tag is not None and t_tag.text:
                    error_title_info = t_tag.text.strip()
            except:
                pass # Ignore errors trying to get details for logging

            scraper.logger.error(f"Error processing item for medium {medium} (Link: '{error_link_info}', Title: '{error_title_info}'): {e}", exc_info=True)
            return None
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_item, item) for item in valid_items]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                news_list.append(result)
    
    return news_list

def parse_xml(data, medium, scraper, robots_checker):
    try:
        root = ET.fromstring(data)
        items = list(root.findall('.//item'))
        return process_feed_items_parallel(items, medium, scraper, robots_checker)
    except Exception as e:
        scraper.logger.error(f"Error parsing XML feed for medium {medium}: {e}")
    return []

def fetch_all_rss(max_workers=10):
    scraper = NewsScraper(
        min_word_threshold=100, 
        min_scraped_words=100, 
        request_timeout=8, 
        domain_delay=0.5
    )
    robots_checker = RobotsChecker(user_agent=USER_AGENT)
    all_media = list(Media.get_all())
    total_media = len(all_media)
    
    scraper.logger.info(f"Processing {total_media} media sources in parallel (max workers: {max_workers})")
    
    progress = {"current": 0, "total": total_media}
    progress_lock = threading.Lock()
    
    def process_medium(medium):
        session = scraper.get_session(robots_checker)
        
        with progress_lock:
            progress["current"] += 1
            current = progress["current"]
        
        scraper.logger.info(f"[{current}/{total_media}] Processing: {medium}")
        
        pm = Media.get_press_media(medium)
        if not pm:
            return []
            
        try:
            # Mark this request as an RSS feed
            r = session.get(pm.link, timeout=8, is_rss_feed=True)
            r.raise_for_status()
            news = parse_xml(r.text, medium, scraper, robots_checker)
            scraper.logger.info(f"[{current}/{total_media}] Completed: {medium} - {len(news)} articles")
            return news
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                scraper.logger.error(f"Failed to fetch feed from {medium}: 403 Forbidden - The server understood the request but refused authorization. This could be due to anti-scraping measures despite robots.txt access.")
                # Log the headers we're using
                scraper.logger.info(f"Request headers used: {session.headers}")
                return []
            else:
                scraper.logger.error(f"HTTP error fetching feed from {medium}: {e}")
                return []
        except Exception as e:
            scraper.logger.error(f"Failed to fetch feed from {medium}: {e}")
            return []
    
    all_news = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_medium = {executor.submit(process_medium, medium): medium for medium in all_media}
        for future in concurrent.futures.as_completed(future_to_medium):
            medium = future_to_medium[future]
            try:
                news_list = future.result()
                all_news.extend(news_list)
            except Exception as e:
                scraper.logger.error(f"Unhandled exception processing {medium}: {e}")
    
    scraper.logger.info(f"Processing complete. Total articles collected: {len(all_news)}")
    if scraper.error_counts:
        scraper.logger.info(f"Error counts: {dict(scraper.error_counts)}")
        
    return all_news