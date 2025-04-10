import uuid
from datetime import datetime

class PressMedia:
    def __init__(self, name, link):
        self.name = name
        self.link = link

class Media:
    ABC = "abc"
    EL_PAIS = "elPais"
    EL_MUNDO = "elMundo"
    LA_VANGUARDIA = "laVanguardia"
    EL_PERIODICO = "elPeriodico"
    
    @staticmethod
    def get_all():
        return [Media.ABC, Media.EL_PAIS, Media.EL_MUNDO, Media.LA_VANGUARDIA, Media.EL_PERIODICO]
    
    @staticmethod
    def get_press_media(medium):
        media_map = {
            Media.ABC: PressMedia("ABC", "https://www.abc.es/rss/2.0/portada/"),
            Media.EL_PAIS: PressMedia("El País", "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada"),
            Media.EL_MUNDO: PressMedia("El Mundo", "https://e00-elmundo.uecdn.es/elmundo/rss/portada.xml"),
            Media.LA_VANGUARDIA: PressMedia("La Vanguardia", "https://www.lavanguardia.com/rss/home.xml"),
            Media.EL_PERIODICO: PressMedia("El Periódico", "https://www.elperiodico.com/es/cds/rss/?id=board.xml")
        }
        return media_map.get(medium)

class News:
    def __init__(self, title, description, category, image_url, link, pub_date, source_medium):
        self.id = str(uuid.uuid4())
        self.title = title
        self.description = description
        self.category = category
        self.image_url = image_url
        self.link = link
        self.pub_date = pub_date
        self.source_medium = source_medium
        self.group = None
        self.created_at = datetime.now()

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "imageUrl": self.image_url,
            "link": self.link,
            "pubDate": self.pub_date,
            "sourceMedium": self.source_medium,
            "group": self.group,
            "created_at": self.created_at
        }