import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np
from functions.fetch_news.src.grouping import group_news, get_news_not_embedded, extract_titles_and_descriptions

@patch("functions.fetch_news.src.grouping.get_sentence_transformer_model")
@patch("functions.fetch_news.src.grouping.update_news_embedding")
@patch("functions.fetch_news.src.grouping.get_all_embeddings")
def test_group_news(mock_get_all_embeddings, mock_update_news_embedding, mock_get_model):
    # Mock the SentenceTransformer model
    mock_model = MagicMock()
    mock_model.encode.return_value = np.random.rand(2, 384)  # Mock embeddings
    mock_get_model.return_value = mock_model

    # Mock Firestore interactions
    mock_get_all_embeddings.return_value = []
    mock_update_news_embedding.return_value = None

    # Input data
    news_list = [
        {"id": "1", "title": "News 1", "scraped_description": "Description 1"},
        {"id": "2", "title": "News 2", "scraped_description": "Description 2"},
    ]

    # Call the function
    result = group_news(news_list)

    # Assertions
    assert isinstance(result, list)
    assert len(result) == len(news_list)
    for item in result:
        assert "id" in item
        assert "group" in item

def test_get_news_not_embedded():
    # Input DataFrame
    input_df = pd.DataFrame([
        {"id": "1", "embedding": None, "scraped_description": "Description 1"},
        {"id": "2", "embedding": [], "scraped_description": "Description 2"},
        {"id": "3", "embedding": [0.1, 0.2], "scraped_description": "Description 3"},
    ])

    # Call the function
    result = get_news_not_embedded(input_df)

    # Assertions
    assert isinstance(result, list)
    assert len(result) == 2  # Only the first two rows need embeddings
    assert result[0]["id"] == "1"
    assert result[1]["id"] == "2"

def test_extract_titles_and_descriptions():
    # Input DataFrame
    input_df = pd.DataFrame([
        {"title": "Title 1", "scraped_description": "Description 1"},
        {"title": "Title 2", "scraped_description": None, "description": "Fallback Description 2"},
        {"title": "Title 3", "scraped_description": None, "description": None},
    ])

    # Call the function
    titles, descriptions = extract_titles_and_descriptions(input_df)

    # Assertions
    assert isinstance(titles, pd.Series)
    assert isinstance(descriptions, pd.Series)
    assert titles.tolist() == ["Title 1", "Title 2", "Title 3"]
    assert descriptions.tolist() == ["Description 1", "Fallback Description 2", ""]
