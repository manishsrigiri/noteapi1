# app/main.py
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from pymongo import MongoClient
from typing import List

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

# -------------------------
# CRUD Endpoints
# -------------------------
@app.post("/notes")
def create_note(note: Note, collection=Depends(get_collection)):
    if collection.find_one({"_id": note.id}):
        raise HTTPException(status_code=400, detail="Note already exists")
    collection.insert_one(note.model_dump() | {"_id": note.id})
    return {"message": "Note created successfully"}

@app.get("/notes", response_model=List[Note])
def get_notes(collection=Depends(get_collection)):
    notes = []
    for note in collection.find():
        notes.append(
            Note(
                id=note["_id"],
                title=note["title"],
                content=note["content"],
                pinned=note.get("pinned", False),
                is_private=note.get("is_private", False),
            )
        )
    return notes


@app.get("/notes/stats")
def get_note_stats(collection=Depends(get_collection)):
    total_ids = collection.count_documents({})
    pinned_count = collection.count_documents({"pinned": True})
    private_count = collection.count_documents({"is_private": True})
    return {
        "total_ids": total_ids,
        "pinned_ids": pinned_count,
        "private_ids": private_count,
    }


@app.get("/notes/{id}", response_model=Note)
def get_note(id: str, collection=Depends(get_collection)):
    note = collection.find_one({"_id": id})
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return Note(
        id=note["_id"],
        title=note["title"],
        content=note["content"],
        pinned=note.get("pinned", False),
        is_private=note.get("is_private", False),
    )

@app.put("/notes/{id}")
def update_note(id: str, note: Note, collection=Depends(get_collection)):
    payload = note.model_dump()
    payload["id"] = id
    result = collection.update_one({"_id": id}, {"$set": payload})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"message": "Note updated successfully"}


@app.put("/notes/{id}/pin")
def pin_note(id: str, pin_request: PinRequest, collection=Depends(get_collection)):
    result = collection.update_one({"_id": id}, {"$set": {"pinned": pin_request.pinned}})
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
