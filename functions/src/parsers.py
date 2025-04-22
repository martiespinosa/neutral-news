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

USER_AGENT = "NeutralNews/1.0 (+https://ezequielgaribotto.com/neutralnews)"

thread_local = threading.local()

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
        if base_url in self.parsers:
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

robots_checker = RobotsChecker(user_agent=USER_AGENT)

class NewsScraper:
    ERROR_PATTERNS = [
        r"404", r"página no encontrada", r"not found", r"no existe",
        r"error 404", r"no se ha encontrado", r"no disponible", 
        r"Esta funcionalidad es sólo para registrados",
    ]

    GENERIC_PATTERNS = [
        r"bienvenido", r"acerca de", r"quiénes somos", r"contacto", 
        r"home", r"inicio", r"política de privacidad", r"aviso legal"
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
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    def get_session(self):
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
            self.logger.debug("Duplicate content detected.")
            self.error_counts["duplicate_content"] += 1
            return True
        self.processed_articles.add(h)
        return False

    def contains_error_message(self, text):
        if not text:
            return True
        t = text.lower()
        return any(re.search(p, t) for p in self.ERROR_PATTERNS)

    def clean_content(self, content):
        if not content:
            return ""
        sents = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)?(?<=\.|\?)\s', content)
        cleaned = [s for s in sents if not any(term in s.lower() for term in ["cookie", "regist", "suscri", "privacidad"])]
        text = re.sub(r'\s+', ' ', ' '.join(cleaned)).strip()
        words = text.split()
        return ' '.join(words[:self.max_scraped_words]) if len(words) > self.max_scraped_words else text

    def extract_with_newspaper(self, url):
        if not robots_checker.can_fetch(url):
            self.logger.info(f"Article from newspaper Scrap Method: Blocked by robots.txt: {url}")
            self.error_counts["blocked_by_robots"] += 1
            return ""
        try:
            art = Article(url, language='es')
            art.download()
            art.parse()
            t = self.clean_content(art.text)
            if len(t.split()) >= self.min_scraped_words:
                self.logger.info(f"Article successfully extracted via Newspaper3k: {url}")
                return t
        except Exception as e:
            self.logger.warning(f"Newspaper3k failed for {url}: {e}")
        return ""

    def extract_fallback(self, soup):
        for sel in ['article', '.article-body', '.content', '.entry-content', 'main', '#main-content']:
            c = soup.select_one(sel)
            if c:
                ps = [p.get_text().strip() for p in c.find_all('p') if len(p.get_text().strip()) > 30]
                if ps:
                    self.logger.debug(f"Extracted content using fallback selector {sel}.")
                    return self.clean_content(' '.join(ps))
        ps = [p.get_text().strip() for p in soup.find_all('p') if len(p.get_text().strip()) > 30]
        return self.clean_content(' '.join(ps)) if ps else ""

    def needs_scraping(self, text):
        return not text or len(text.split()) < self.min_word_threshold

    def scrape_content(self, url):
        if not url:
            self.logger.warning("Empty URL provided.")
            self.error_counts["empty_url"] += 1
            return ""
        if not robots_checker.can_fetch(url):
            self.logger.info(f"Blocked by robots.txt: {url}")
            self.error_counts["blocked_by_robots_ua"] += 1
            return ""
        try:
            domain = self.get_domain(url)
            self.rate_limiter.wait(domain)
            self.logger.debug(f"Fetching content from {url}")
            self.stats["requests_made"] += 1
            content = self.extract_with_newspaper(url)
            if not content:
                sess = self.get_session()
                r = sess.get(url, timeout=self.request_timeout)
                if r.status_code != 200:
                    self.logger.warning(f"Non-200 HTTP status code {r.status_code} for {url}")
                    self.error_counts[f"http_{r.status_code}"] += 1
                    return ""
                txt = r.text
                if self.contains_error_message(txt):
                    self.logger.warning(f"Error pattern detected in page content: {url}")
                    self.error_counts["error_page"] += 1
                    return ""
                soup = BeautifulSoup(txt, 'html.parser')
                content = self.extract_fallback(soup)
            if len(content.split()) < self.min_scraped_words or self.is_duplicate(content):
                self.logger.info(f"Content too short or duplicate for {url}")
                return ""
            self.stats["successful_scrapes"] += 1
            self.logger.info(f"Successfully scraped content from {url}")
            return content
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request error for {url}: {e}")
            self.error_counts["request_error"] += 1
        except Exception as e:
            self.logger.exception(f"Unexpected error scraping {url}: {e}")
            self.error_counts["scraping_error"] += 1
        return ""

def normalize_string(s):
    return s.lower().strip()

def clean_html(html_content):
    if not html_content:
        return ""
    try:
        return BeautifulSoup(html_content, 'html.parser').get_text(separator=' ', strip=True)
    except:
        return html_content

def parse_xml(data, medium, scraper=None):
    if scraper is None:
        scraper = NewsScraper()
    news_list = []
    try:
        root = ET.fromstring(data)
        ns = {'media': 'http://search.yahoo.com/mrss/'}
        for item in root.findall('.//item'):
            t = item.find('title')
            title = clean_html(t.text) if t is not None and t.text else ""
            d = item.find('description')
            desc = clean_html(d.text) if d is not None and d.text else ""
            l = item.find('link')
            link = l.text.strip() if l is not None and l.text else ""
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
            scr_desc = desc
            if scraper.needs_scraping(desc) and link:
                scr = scraper.scrape_content(link)
                if scr:
                    scr_desc = scr
            item_obj = News(
                title=title,
                description=desc,
                scraped_description=scr_desc,
                category=cat,
                image_url=img,
                link=link,
                pub_date=pub,
                source_medium=medium
            )
            if not any(n.link==item_obj.link for n in news_list):
                news_list.append(item_obj)
    except Exception as e:
        logging.exception(f"Error parsing XML feed for medium {medium}: {e}")
    return news_list

def fetch_all_rss():
    all_news = []
    scraper = NewsScraper(min_word_threshold=25, min_scraped_words=100, max_scraped_words=800, request_timeout=5, domain_delay=1.5)
    session = scraper.get_session()  # ✅ Get it once
    for medium in Media.get_all():
        pm = Media.get_press_media(medium)
        if not pm:
            continue
        try:
            r = session.get(pm.link, timeout=5)            
            r.raise_for_status()
            news = parse_xml(r.text, medium, scraper)
            all_news.extend(news)
        except Exception as e:
            logging.warning(f"Failed to fetch or parse feed from {pm.link}: {e}")
    return all_news
