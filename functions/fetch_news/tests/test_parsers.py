import pytest
from unittest.mock import patch, MagicMock
from src.parsers import (
    RobotsChecker,
    SafeSession,
    NewsScraper,
    fetch_all_rss,
    parse_xml,
    process_feed_items_parallel
)
from functions.fetch_news.src.models import Media, News
from xml.etree.ElementTree import Element

USER_AGENT = "NeutralNews/1.0 (+https://ezequielgaribotto.com)"

@patch("functions.fetch_news.src.parsers.RobotFileParser")
def test_robots_checker_can_fetch(mock_robot_file_parser):
    # Mock the RobotFileParser behavior
    mock_parser = MagicMock()
    mock_robot_file_parser.return_value = mock_parser
    mock_parser.can_fetch.return_value = True

    # Create an instance of RobotsChecker
    checker = RobotsChecker(user_agent=USER_AGENT)

    # Call the can_fetch method
    result = checker.can_fetch("https://example.com/some-page")

    # Assertions
    assert result is True
    mock_robot_file_parser.assert_called_once()  # Ensure RobotFileParser was instantiated
    mock_parser.set_url.assert_called_once_with("https://example.com/robots.txt")
    mock_parser.read.assert_called_once()
    mock_parser.can_fetch.assert_called_once_with(USER_AGENT, "https://example.com/some-page")

@patch("functions.fetch_news.src.parsers.requests.Session.get")
def test_safe_session_get(mock_get):
    # Mock the RobotsChecker
    mock_checker = MagicMock()
    mock_checker.can_fetch.return_value = True

    # Mock the requests.Session.get method
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_get.return_value = mock_response

    session = SafeSession(robots_checker=mock_checker)
    response = session.get("https://example.com/some-page")

    assert response.status_code == 200
    mock_checker.can_fetch.assert_called_once_with("https://example.com/some-page")
    mock_get.assert_called_once_with("https://example.com/some-page")

@patch("functions.fetch_news.src.parsers.NewsScraper.extract_with_newspaper")
def test_news_scraper_scrape_content(mock_extract_with_newspaper):
    # Mock the extract_with_newspaper method
    mock_extract_with_newspaper.return_value = "Sample article content"

    scraper = NewsScraper(min_word_threshold=10, min_scraped_words=5)
    content = scraper.scrape_content("https://example.com/article")

    assert content == "Sample article content"
    mock_extract_with_newspaper.assert_called_once_with("https://example.com/article")

@patch("functions.fetch_news.src.parsers.NewsScraper.scrape_content")
@patch("functions.fetch_news.src.parsers.load_all_news_links_from_medium")
def test_process_feed_items_parallel(mock_load_all_news_links, mock_scrape_content):
    # Mock the loaded news links
    mock_load_all_news_links.return_value = ["https://example.com/old-article"]

    # Mock the scrape_content method
    mock_scrape_content.return_value = "Scraped content"

    # Create a mock RSS item
    item = Element("item")
    link = Element("link")
    link.text = "https://example.com/new-article"
    item.append(link)
    title = Element("title")
    title.text = "Sample Title"
    item.append(title)
    description = Element("description")
    description.text = "Sample Description"
    item.append(description)

    scraper = NewsScraper()
    robots_checker = RobotsChecker()
    result = process_feed_items_parallel([item], "TestMedium", scraper, robots_checker)

    assert len(result) == 1
    assert isinstance(result[0], News)
    assert result[0].title == "Sample Title"
    assert result[0].link == "https://example.com/new-article"

@patch("functions.fetch_news.src.parsers.NewsScraper.get_session")
@patch("functions.fetch_news.src.parsers.parse_xml")
@patch("functions.fetch_news.src.parsers.Media.get_all")
def test_fetch_all_rss(mock_get_all, mock_parse_xml, mock_get_session):
    # Mock the Media.get_all method
    mock_get_all.return_value = ["TestMedium"]

    # Mock the parse_xml function
    mock_parse_xml.return_value = [News(
        title="Test Title",
        description="Test Description",
        scraped_description="Scraped Description",
        category="Test Category",
        image_url="https://example.com/image.jpg",
        link="https://example.com/article",
        pub_date="2025-05-08",
        source_medium="TestMedium"
    )]

    # Mock the session
    mock_session = MagicMock()
    mock_get_session.return_value = mock_session

    # Call the function
    result = fetch_all_rss(max_workers=1)

    assert len(result) == 1
    assert isinstance(result[0], News)
    assert result[0].title == "Test Title"