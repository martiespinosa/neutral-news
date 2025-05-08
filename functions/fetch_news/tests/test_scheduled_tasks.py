import pytest
from unittest.mock import patch, MagicMock
from functions.fetch_news.src.functions.scheduled_tasks import fetch_news_task

@patch("functions.fetch_news.src.functions.scheduled_tasks.fetch_all_rss")
@patch("functions.fetch_news.src.functions.scheduled_tasks.store_news_in_firestore")
@patch("functions.fetch_news.src.functions.scheduled_tasks.process_news_groups")
def test_fetch_news_task_success(mock_process_news_groups, mock_store_news_in_firestore, mock_fetch_all_rss):
    # Mock the return values of the dependencies
    mock_fetch_all_rss.return_value = [
        {"id": "1", "title": "News 1", "link": "https://example.com/news1"},
        {"id": "2", "title": "News 2", "link": "https://example.com/news2"}
    ]
    mock_store_news_in_firestore.return_value = 2
    mock_process_news_groups.return_value = 2

    # Call the function
    fetch_news_task()

    # Assertions
    mock_fetch_all_rss.assert_called_once()
    mock_store_news_in_firestore.assert_called_once_with(mock_fetch_all_rss.return_value)
    mock_process_news_groups.assert_called_once()

@patch("functions.fetch_news.src.functions.scheduled_tasks.fetch_all_rss")
@patch("functions.fetch_news.src.functions.scheduled_tasks.store_news_in_firestore")
@patch("functions.fetch_news.src.functions.scheduled_tasks.process_news_groups")
def test_fetch_news_task_no_news(mock_process_news_groups, mock_store_news_in_firestore, mock_fetch_all_rss):
    # Mock the return values of the dependencies
    mock_fetch_all_rss.return_value = []
    mock_store_news_in_firestore.return_value = 0
    mock_process_news_groups.return_value = 0

    # Call the function
    fetch_news_task()

    # Assertions
    mock_fetch_all_rss.assert_called_once()
    mock_store_news_in_firestore.assert_not_called()  # No news to store
    mock_process_news_groups.assert_called_once()

@patch("functions.fetch_news.src.functions.scheduled_tasks.fetch_all_rss")
@patch("functions.fetch_news.src.functions.scheduled_tasks.store_news_in_firestore")
@patch("functions.fetch_news.src.functions.scheduled_tasks.process_news_groups")
def test_fetch_news_task_exception(mock_process_news_groups, mock_store_news_in_firestore, mock_fetch_all_rss, capsys):
    # Mock an exception in one of the dependencies
    mock_fetch_all_rss.side_effect = Exception("RSS fetch failed")

    # Call the function
    fetch_news_task()

    # Capture the output
    captured = capsys.readouterr()

    # Assertions
    mock_fetch_all_rss.assert_called_once()
    mock_store_news_in_firestore.assert_not_called()
    mock_process_news_groups.assert_not_called()

    # Verify the exception was logged
    assert "Error in fetch_news_task: RSS fetch failed" in captured.out
    assert "Traceback" in captured.err