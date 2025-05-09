import pytest
from functions.fetch_news.src.models import PressMedia, Media, News
from datetime import datetime
from unittest.mock import patch

def test_press_media_initialization():
    # Test initialization of PressMedia
    media = PressMedia(name="Test Media", link="https://test.com/rss")
    assert media.name == "Test Media"
    assert media.link == "https://test.com/rss"

def test_media_get_all():
    # Test Media.get_all() returns all media constants
    all_media = Media.get_all()
    assert isinstance(all_media, list)
    assert len(all_media) > 0
    assert Media.ABC in all_media
    assert Media.RTVE in all_media

def test_media_get_press_media():
    # Test Media.get_press_media() returns correct PressMedia object
    press_media = Media.get_press_media(Media.ABC)
    assert isinstance(press_media, PressMedia)
    assert press_media.name == "ABC"
    assert press_media.link == "https://www.abc.es/rss/2.0/portada/"

    # Test for a non-existent media
    press_media = Media.get_press_media("non_existent_media")
    assert press_media is None

@patch("functions.fetch_news.src.models.uuid.uuid4")
def test_news_initialization(mock_uuid):
    # Mock UUID generation
    mock_uuid.return_value = "test-uuid"

    # Test initialization of News
    news = News(
        title="Test Title",
        description="Test Description",
        scraped_description="Test Scraped Description",
        category="Test Category",
        image_url="https://test.com/image.jpg",
        link="https://test.com/article",
        pub_date="2025-05-08",
        source_medium=Media.ABC
    )

    assert news.id == "test-uuid"
    assert news.title == "Test Title"
    assert news.description == "Test Description"
    assert news.scraped_description == "Test Scraped Description"
    assert news.category == "Test Category"
    assert news.image_url == "https://test.com/image.jpg"
    assert news.link == "https://test.com/article"
    assert news.pub_date == "2025-05-08"
    assert news.source_medium == Media.ABC
    assert news.group is None
    assert isinstance(news.created_at, datetime)
    assert news.embedding is None

def test_news_to_dict():
    # Test the to_dict method of News
    news = News(
        title="Test Title",
        description="Test Description",
        scraped_description="Test Scraped Description",
        category="Test Category",
        image_url="https://test.com/image.jpg",
        link="https://test.com/article",
        pub_date="2025-05-08",
        source_medium=Media.ABC
    )

    news_dict = news.to_dict()
    assert news_dict["id"] == news.id
    assert news_dict["title"] == "Test Title"
    assert news_dict["description"] == "Test Description"
    assert news_dict["scraped_description"] == "Test Scraped Description"
    assert news_dict["category"] == "Test Category"
    assert news_dict["image_url"] == "https://test.com/image.jpg"
    assert news_dict["link"] == "https://test.com/article"
    assert news_dict["pub_date"] == "2025-05-08"
    assert news_dict["source_medium"] == Media.ABC
    assert news_dict["group"] is None
    assert news_dict["created_at"] == news.created_at
    assert news_dict["embedding"] is None