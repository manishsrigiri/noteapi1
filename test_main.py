# test_main.py
import os

os.environ["AUTH_DISABLED"] = "true"

from fastapi.testclient import TestClient
from app.main import app
from app.database.mongodb import get_collection, get_client
import mongomock

# -------------------------------
# Setup a mock MongoDB collection
# -------------------------------
mock_client = mongomock.MongoClient()
mock_collection = mock_client["notesdb"]["notes"]

# Override the FastAPI dependency to use the mock collection
app.dependency_overrides[get_collection] = lambda: mock_collection
app.dependency_overrides[get_client] = lambda: mock_client

client = TestClient(app)

# -------------------------------
# Test Cases
# -------------------------------
def test_create_note():
    response = client.post("/notes", json={
        "id": "test1",
        "title": "Test Note",
        "content": "This is a test"
    })
    assert response.status_code == 200
    assert response.json() == {"message": "Note created successfully"}

def test_get_all_notes():
    response = client.get("/notes")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "test1"
    assert data[0]["category"] == "General"
    assert data[0]["tags"] == []
    assert data[0]["created_at"] is not None
    assert data[0]["updated_at"] is not None

def test_get_single_note():
    response = client.get("/notes/test1")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Note"
    assert data["pinned"] is False
    assert data["is_private"] is False

def test_update_note():
    before_update = client.get("/notes/test1").json()
    response = client.put("/notes/test1", json={
        "id": "test1",
        "title": "Updated Note",
        "content": "Updated content",
        "pinned": False,
        "is_private": True,
        "category": "Work",
        "tags": ["urgent", "demo"]
    })
    assert response.status_code == 200
    assert response.json() == {"message": "Note updated successfully"}

    after_update = client.get("/notes/test1").json()
    assert after_update["category"] == "Work"
    assert after_update["tags"] == ["urgent", "demo"]
    assert after_update["created_at"] == before_update["created_at"]
    assert after_update["updated_at"] >= before_update["updated_at"]

def test_pin_note():
    response = client.put("/notes/test1/pin", json={"pinned": True})
    assert response.status_code == 200
    assert response.json() == {"message": "Note pinned successfully"}

    get_response = client.get("/notes/test1")
    assert get_response.status_code == 200
    assert get_response.json()["pinned"] is True

def test_note_stats():
    response = client.get("/notes/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_ids"] == 1
    assert data["pinned_ids"] == 1
    assert data["private_ids"] == 1
    assert data["public_ids"] == 0
    assert data["categories"]["Work"] == 1

def test_delete_note():
    response = client.delete("/notes/test1")
    assert response.status_code == 200
    assert response.json() == {"message": "Note deleted successfully"}

def test_get_deleted_note():
    # Should return 404 because note was deleted
    response = client.get("/notes/test1")
    assert response.status_code == 404
    assert response.json() == {"detail": "Note not found"}
