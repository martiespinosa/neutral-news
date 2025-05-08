import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from functions.fetch_news.src.storage import (
    store_news_in_firestore,
    get_news_for_grouping,
    update_groups_in_firestore,
    update_news_with_neutral_scores,
    load_all_news_links_from_medium,
    store_neutral_news,
    update_existing_neutral_news,
    get_most_neutral_image,
    delete_old_news
)

@patch("functions.fetch_news.src.storage.initialize_firebase")
def test_store_news_in_firestore(mock_initialize_firebase):
    # Mock Firestore
    mock_db = MagicMock()
    mock_batch = MagicMock()
    mock_initialize_firebase.return_value = mock_db
    mock_db.batch.return_value = mock_batch

    # Mock news list
    news_list = [
        MagicMock(id="1", link="https://example.com/news1", to_dict=lambda: {"id": "1", "link": "https://example.com/news1"}),
        MagicMock(id="2", link="https://example.com/news2", to_dict=lambda: {"id": "2", "link": "https://example.com/news2"})
    ]

    # Call the function
    result = store_news_in_firestore(news_list)

    # Assertions
    assert result == 2
    mock_batch.set.assert_called()
    mock_batch.commit.assert_called()

@patch("functions.fetch_news.src.storage.initialize_firebase")
def test_get_news_for_grouping(mock_initialize_firebase):
    # Mock Firestore
    mock_db = MagicMock()
    mock_initialize_firebase.return_value = mock_db

    # Mock Firestore query results
    mock_ungrouped_news = [MagicMock(id="1", to_dict=lambda: {"id": "1", "title": "News 1", "group": None})]
    mock_recent_grouped_news = [MagicMock(id="2", to_dict=lambda: {"id": "2", "title": "News 2", "group": 1})]
    mock_db.collection.return_value.where.return_value.stream.side_effect = [mock_ungrouped_news, mock_recent_grouped_news]

    # Call the function
    result, all_docs = get_news_for_grouping()

    # Assertions
    assert len(result) == 2
    assert len(all_docs) == 2

@patch("functions.fetch_news.src.storage.initialize_firebase")
def test_update_groups_in_firestore(mock_initialize_firebase):
    # Mock Firestore
    mock_db = MagicMock()
    mock_batch = MagicMock()
    mock_initialize_firebase.return_value = mock_db
    mock_db.batch.return_value = mock_batch

    # Mock grouped news and documents
    grouped_news = [{"id": "1", "group": 1}]
    news_docs = {"1": MagicMock(to_dict=lambda: {"id": "1", "group": None}, reference=MagicMock())}

    # Call the function
    result = update_groups_in_firestore(grouped_news, news_docs)

    # Assertions
    assert result == 1
    mock_batch.update.assert_called_once()
    mock_batch.commit.assert_called_once()

@patch("functions.fetch_news.src.storage.initialize_firebase")
def test_update_news_with_neutral_scores(mock_initialize_firebase):
    # Mock Firestore
    mock_db = MagicMock()
    mock_batch = MagicMock()
    mock_initialize_firebase.return_value = mock_db
    mock_db.batch.return_value = mock_batch

    # Mock sources and neutralization result
    sources = [{"id": "1", "source_medium": "Medium 1"}]
    neutralization_result = {"source_ratings": [{"source_medium": "Medium 1", "rating": 0.8}]}

    # Call the function
    result = update_news_with_neutral_scores(sources, neutralization_result)

    # Assertions
    assert result == 1
    mock_batch.update.assert_called_once()
    mock_batch.commit.assert_called_once()

@patch("functions.fetch_news.src.storage.initialize_firebase")
def test_delete_old_news(mock_initialize_firebase):
    # Mock Firestore
    mock_db = MagicMock()
    mock_batch = MagicMock()
    mock_initialize_firebase.return_value = mock_db
    mock_db.batch.return_value = mock_batch

    # Mock old news documents
    mock_old_news_docs = [MagicMock(reference=MagicMock()) for _ in range(10)]
    mock_db.collection.return_value.where.return_value.stream.return_value = mock_old_news_docs

    # Call the function
    result = delete_old_news(hours=72)

    # Assertions
    assert result == 10
    mock_batch.delete.assert_called()
    mock_batch.commit.assert_called()