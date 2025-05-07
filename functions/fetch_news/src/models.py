import uuid
from datetime import datetime

class PressMedia:
    def __init__(self, name, link):
        self.name = name
        self.link = link

class Media:
    ABC = "abc"
    ANTENA_3 = "antena3"
    COPE = "cope"
    DIARIO_RED = "diarioRed"
    EL_DIARIO = "elDiario"
    EL_ECONOMISTA = "elEconomista"
    EL_MUNDO = "elMundo"
    EL_PAIS = "elPais"
    EL_PERIODICO = "elPeriodico"
    EL_SALTO = "elSalto"
    ES_DIARIO = "esDiario"
    EXPANSION = "expansion"
    LA_SEXTA = "laSexta"
    LA_VANGUARDIA = "laVanguardia"
    LIBERTAD_DIGITAL = "libertadDigital"
    RTVE = "rtve"
    
    @staticmethod
    def get_all():
        return [Media.ABC, Media.ANTENA_3, Media.COPE, Media.DIARIO_RED, Media.EL_DIARIO, Media.EL_ECONOMISTA, Media.EL_MUNDO, Media.EL_PAIS, Media.EL_PERIODICO, Media.EL_SALTO, Media.ES_DIARIO, Media.EXPANSION, Media.LA_SEXTA, Media.LA_VANGUARDIA, Media.LIBERTAD_DIGITAL, Media.RTVE]
    
    @staticmethod
    def get_press_media(medium):
        media_map = {
            Media.ABC: PressMedia("ABC", "https://www.abc.es/rss/2.0/portada/"),
            Media.ANTENA_3: PressMedia("Antena 3", "https://www.antena3.com/noticias/rss/4013050.xml"),
            Media.COPE: PressMedia("COPE", "https://www.cope.es/api/es/news/rss.xml"),
            Media.DIARIO_RED: PressMedia("Diario Red", "https://www.diario-red.com/rss/"),
            Media.EL_DIARIO: PressMedia("El Diario", "https://www.eldiario.es/rss/"),
            Media.EL_ECONOMISTA: PressMedia("El Economista", "https://www.eleconomista.es/rss/rss-seleccion-ee.php"),
            Media.EL_MUNDO: PressMedia("El Mundo", "https://e00-elmundo.uecdn.es/elmundo/rss/portada.xml"),
            Media.EL_PAIS: PressMedia("El País", "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada"),
            Media.EL_PERIODICO: PressMedia("El Periódico", "https://www.elperiodico.com/es/cds/rss/?id=board.xml"),
            Media.EL_SALTO: PressMedia("El Salto", "https://www.elsaltodiario.com/general/feed"),
            Media.ES_DIARIO: PressMedia("ES Diario", "https://www.esdiario.com/rss/home.xml"),
            Media.EXPANSION: PressMedia("Expansión", "https://e00-expansion.uecdn.es/rss/portada.xml"),
            Media.LA_SEXTA: PressMedia("La Sexta", "https://www.lasexta.com/rss/351410.xml"),
            Media.LA_VANGUARDIA: PressMedia("La Vanguardia", "https://www.lavanguardia.com/rss/home.xml"),
            Media.LIBERTAD_DIGITAL: PressMedia("Libertad Digital", "https://feeds2.feedburner.com/libertaddigital/portada"),
            Media.RTVE: PressMedia("RTVE", "https://api2.rtve.es/rss/temas_noticias.xml")
        }
        return media_map.get(medium)

class News:
    def __init__(self, title, description, scraped_description, category, image_url, link, pub_date, source_medium):
        self.id = str(uuid.uuid4())
        self.title = title
        self.description = description
        self.scraped_description = scraped_description
        self.category = category
        self.image_url = image_url
        self.link = link
        self.pub_date = pub_date
        self.source_medium = source_medium
        self.group = None
        self.created_at = datetime.now()
        self.embedding = None

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "scraped_description": self.scraped_description,
            "category": self.category,
            "image_url": self.image_url,
            "link": self.link,
            "pub_date": self.pub_date,
            "source_medium": self.source_medium,
            "group": self.group,
            "created_at": self.created_at,
            "embedding": self.embedding
        }