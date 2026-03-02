# test_main.py
from fastapi.testclient import TestClient
from app.main import app, get_collection
import mongomock

# -------------------------------
# Setup a mock MongoDB collection
# -------------------------------
mock_client = mongomock.MongoClient()
mock_collection = mock_client["notesdb"]["notes"]

# Override the FastAPI dependency to use the mock collection
app.dependency_overrides[get_collection] = lambda: mock_collection

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

def test_get_single_note():
    response = client.get("/notes/test1")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Note"

def test_update_note():
    response = client.put("/notes/test1", json={
        "id": "test1",
        "title": "Updated Note",
        "content": "Updated content"
    })
    assert response.status_code == 200
    assert response.json() == {"message": "Note updated successfully"}

def test_delete_note():
    response = client.delete("/notes/test1")
    assert response.status_code == 200
    assert response.json() == {"message": "Note deleted successfully"}

def test_get_deleted_note():
    # Should return 404 because note was deleted
    response = client.get("/notes/test1")
    assert response.status_code == 404
    assert response.json() == {"detail": "Note not found"}