# app/main.py
from datetime import datetime, UTC
from typing import List

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from pymongo import MongoClient

app = FastAPI()

# -------------------------
# Models
# -------------------------
class Note(BaseModel):
    id: str
    title: str
    content: str
    pinned: bool = False
    is_private: bool = False
    category: str = "General"
    tags: List[str] = Field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None


class PinRequest(BaseModel):
    pinned: bool = True

# -------------------------
# MongoDB Dependency
# -------------------------
def get_client():
    """Return a MongoClient instance."""
    return MongoClient("mongodb://mongo:27017")  # Change host if needed

def get_collection(client: MongoClient = Depends(get_client)):
    """Return the MongoDB collection object."""
    db = client["notesdb"]
    return db["notes"]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _normalize_note(note: dict) -> Note:
    return Note(
        id=note["_id"],
        title=note["title"],
        content=note["content"],
        pinned=note.get("pinned", False),
        is_private=note.get("is_private", False),
        category=note.get("category", "General"),
        tags=note.get("tags", []),
        created_at=note.get("created_at"),
        updated_at=note.get("updated_at"),
    )

# -------------------------
# CRUD Endpoints
# -------------------------
@app.post("/notes")
def create_note(note: Note, collection=Depends(get_collection)):
    if collection.find_one({"_id": note.id}):
        raise HTTPException(status_code=400, detail="Note already exists")
    payload = note.model_dump()
    now = _now_iso()
    payload["created_at"] = now
    payload["updated_at"] = now
    collection.insert_one(payload | {"_id": note.id})
    return {"message": "Note created successfully"}

@app.get("/notes", response_model=List[Note])
def get_notes(collection=Depends(get_collection)):
    notes = []
    for note in collection.find():
        notes.append(_normalize_note(note))
    return notes


@app.get("/notes/stats")
def get_note_stats(collection=Depends(get_collection)):
    total_ids = collection.count_documents({})
    pinned_count = collection.count_documents({"pinned": True})
    private_count = collection.count_documents({"is_private": True})
    category_pipeline = [
        {
            "$group": {
                "_id": {"$ifNull": ["$category", "General"]},
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"count": -1, "_id": 1}},
    ]
    categories = {
        doc["_id"]: doc["count"] for doc in collection.aggregate(category_pipeline)
    }
    return {
        "total_ids": total_ids,
        "pinned_ids": pinned_count,
        "private_ids": private_count,
        "public_ids": total_ids - private_count,
        "categories": categories,
    }


@app.get("/notes/{id}", response_model=Note)
def get_note(id: str, collection=Depends(get_collection)):
    note = collection.find_one({"_id": id})
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return _normalize_note(note)

@app.put("/notes/{id}")
def update_note(id: str, note: Note, collection=Depends(get_collection)):
    existing = collection.find_one({"_id": id})
    if not existing:
        raise HTTPException(status_code=404, detail="Note not found")

    payload = note.model_dump()
    payload["id"] = id
    payload["created_at"] = existing.get("created_at", _now_iso())
    payload["updated_at"] = _now_iso()
    result = collection.update_one({"_id": id}, {"$set": payload})
    return {"message": "Note updated successfully"}


@app.put("/notes/{id}/pin")
def pin_note(id: str, pin_request: PinRequest, collection=Depends(get_collection)):
    result = collection.update_one(
        {"_id": id},
        {"$set": {"pinned": pin_request.pinned, "updated_at": _now_iso()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Note not found")
    action = "pinned" if pin_request.pinned else "unpinned"
    return {"message": f"Note {action} successfully"}


@app.delete("/notes/{id}")
def delete_note(id: str, collection=Depends(get_collection)):
    result = collection.delete_one({"_id": id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"message": "Note deleted successfully"}
