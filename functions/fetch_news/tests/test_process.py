import pytest
from unittest.mock import patch, MagicMock
from functions.fetch_news.src.process import process_news_groups, prepare_groups_for_neutralization

@patch("functions.fetch_news.src.process.get_news_for_grouping")
@patch("functions.fetch_news.src.process.group_news")
@patch("functions.fetch_news.src.process.update_groups_in_firestore")
@patch("functions.fetch_news.src.process.neutralize_and_more")
def test_process_news_groups(
    mock_neutralize_and_more,
    mock_update_groups_in_firestore,
    mock_group_news,
    mock_get_news_for_grouping
):
    # Mock the return values of the dependencies
    mock_get_news_for_grouping.return_value = (
        [{"id": "1", "title": "Title 1", "group": None}],
        ["doc1"]
    )
    mock_group_news.return_value = [
        {"id": "1", "title": "Title 1", "group": 1}
    ]
    mock_update_groups_in_firestore.return_value = 1
    mock_neutralize_and_more.return_value = 1

    # Call the function
    result = process_news_groups()

    # Assertions
    assert result == 1
    mock_get_news_for_grouping.assert_called_once()
    mock_group_news.assert_called_once_with([{"id": "1", "title": "Title 1", "group": None}])
    mock_update_groups_in_firestore.assert_called_once_with(
        [{"id": "1", "title": "Title 1", "group": 1}], ["doc1"]
    )
    mock_neutralize_and_more.assert_called_once_with(
        [{"group": 1, "sources": [{"id": "1", "title": "Title 1", "scraped_description": None, "source_medium": None}]}]
    )

@patch("functions.fetch_news.src.process.prepare_groups_for_neutralization")
def test_process_news_groups_no_news(mock_prepare_groups_for_neutralization):
    # Mock get_news_for_grouping to return no news
    with patch("functions.fetch_news.src.process.get_news_for_grouping", return_value=([], [])):
        result = process_news_groups()

    # Assertions
    assert result == 0
    mock_prepare_groups_for_neutralization.assert_not_called()

def test_prepare_groups_for_neutralization():
    # Input data
    grouped_news = [
        {"id": "1", "title": "Title 1", "group": 1, "scraped_description": "Description 1", "source_medium": "Medium 1"},
        {"id": "2", "title": "Title 2", "group": 1, "scraped_description": "Description 2", "source_medium": "Medium 2"},
        {"id": "3", "title": "Title 3", "group": 2, "scraped_description": "Description 3", "source_medium": "Medium 3"},
    ]

    # Call the function
    result = prepare_groups_for_neutralization(grouped_news)

    # Assertions
    assert len(result) == 2
    assert result[0]["group"] == 1
    assert len(result[0]["sources"]) == 2
    assert result[1]["group"] == 2
    assert len(result[1]["sources"]) == 1
    assert result[0]["sources"][0]["id"] == "1"
    assert result[1]["sources"][0]["id"] == "3"