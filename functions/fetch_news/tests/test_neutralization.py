import pytest
from unittest.mock import patch, MagicMock
import os
from functions.fetch_news.src.neutralization import (
    neutralize_and_more,
    generate_neutral_analysis_batch,
    generate_neutral_analysis,
    validate_batch_for_processing
)

@patch("functions.fetch_news.src.neutralization.initialize_firebase")
@patch("functions.fetch_news.src.neutralization.store_neutral_news")
@patch("functions.fetch_news.src.neutralization.update_news_with_neutral_scores")
@patch("functions.fetch_news.src.neutralization.update_existing_neutral_news")
@patch.dict(os.environ, {"OPENAI_API_KEY": "mock-api-key"})
def test_neutralize_and_more(
    mock_update_existing_neutral_news,
    mock_update_news_with_neutral_scores,
    mock_store_neutral_news,
    mock_initialize_firebase
):
    # Mock Firestore initialization
    mock_db = MagicMock()
    mock_initialize_firebase.return_value = mock_db

    # Mock Firestore document retrieval
    mock_doc = MagicMock()
    mock_doc.exists = False
    mock_db.collection.return_value.document.return_value.get.return_value = mock_doc

    # Input data
    news_groups = [
        {
            "group": 1,
            "sources": [
                {"id": "1", "title": "Title 1", "scraped_description": "Description 1", "source_medium": "Medium 1"},
                {"id": "2", "title": "Title 2", "scraped_description": "Description 2", "source_medium": "Medium 2"}
            ]
        }
    ]

    # Call the function
    result = neutralize_and_more(news_groups)

    # Assertions
    assert result == 1  # One group processed
    mock_store_neutral_news.assert_called_once()
    mock_update_news_with_neutral_scores.assert_called_once()

@patch("functions.fetch_news.src.neutralization.OpenAI")
def test_generate_neutral_analysis_batch(mock_openai):
    # Mock OpenAI client
    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content='{"neutral_title": "Test Title"}'))]
    mock_client.chat.completions.create.return_value = mock_response

    # Input data
    group_batch = [
        {
            "group": 1,
            "sources": [
                {"id": "1", "title": "Title 1", "scraped_description": "Description 1", "source_medium": "Medium 1"},
                {"id": "2", "title": "Title 2", "scraped_description": "Description 2", "source_medium": "Medium 2"}
            ]
        }
    ]

    # Call the function
    results = generate_neutral_analysis_batch(group_batch)

    # Assertions
    assert len(results) == 1
    assert results[0]["neutral_title"] == "Test Title"

@patch("functions.fetch_news.src.neutralization.OpenAI")
def test_generate_neutral_analysis(mock_openai):
    # Mock OpenAI client
    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content='{"neutral_title": "Test Title"}'))]
    mock_client.chat.completions.create.return_value = mock_response

    # Input data
    sources = [
        {"id": "1", "title": "Title 1", "scraped_description": "Description 1", "source_medium": "Medium 1"},
        {"id": "2", "title": "Title 2", "scraped_description": "Description 2", "source_medium": "Medium 2"}
    ]

    # Call the function
    result = generate_neutral_analysis(sources)

    # Assertions
    assert result["neutral_title"] == "Test Title"

def test_validate_batch_for_processing():
    # Input data
    batch_to_validate = [
        {
            "group": 1,
            "sources": [
                {"title": "Title 1", "scraped_description": "Description 1"},
                {"title": "Title 2", "scraped_description": "Description 2"}
            ]
        },
        {
            "group": 2,
            "sources": [
                {"title": "Title 3", "scraped_description": ""},
                {"title": "", "scraped_description": "Description 4"}
            ]
        }
    ]

    # Call the function
    valid_groups, discarded_count = validate_batch_for_processing(batch_to_validate)

    # Assertions
    assert len(valid_groups) == 1  # Only one group is valid
    assert discarded_count == 1  # One group discarded
    assert valid_groups[0]["group"] == 1