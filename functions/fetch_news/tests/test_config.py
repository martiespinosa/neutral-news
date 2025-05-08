import pytest
from unittest.mock import patch, MagicMock
from functions.fetch_news.src.config import initialize_firebase

@patch("functions.fetch_news.src.config.credentials")
def test_initialize_firebase(mock_credentials, mock_firebase_admin):
    # Mock the credentials and Firebase Admin SDK
    mock_app = MagicMock()
    mock_firebase_admin.get_app.side_effect = ValueError("No app initialized")
    mock_firebase_admin.initialize_app.return_value = mock_app
    mock_firebase_admin.firestore.client.return_value = "mock_firestore_client"

    # Call the function
    firestore_client = initialize_firebase()

    # Assertions
    mock_firebase_admin.get_app.assert_called_once()
    mock_firebase_admin.initialize_app.assert_called_once_with(mock_credentials.ApplicationDefault())
    assert firestore_client == "mock_firestore_client"

@patch("functions.fetch_news.src.config.firebase_admin")
def test_initialize_firebase_already_initialized(mock_firebase_admin):
    # Mock the case where Firebase is already initialized
    mock_app = MagicMock()
    mock_firebase_admin.get_app.return_value = mock_app
    mock_firebase_admin.firestore.client.return_value = "mock_firestore_client"

    # Call the function
    firestore_client = initialize_firebase()

    # Assertions
    mock_firebase_admin.get_app.assert_called_once()
    mock_firebase_admin.initialize_app.assert_not_called()  # Ensure no reinitialization
    assert firestore_client == "mock_firestore_client"

def test_initialize_firebase_error_handling():
    # Test error handling when Firebase initialization fails
    with patch("functions.fetch_news.src.config.firebase_admin", side_effect=Exception("Initialization failed")):
        with pytest.raises(Exception, match="Initialization failed"):
            initialize_firebase()