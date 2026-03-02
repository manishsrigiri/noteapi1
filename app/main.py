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
        notes.append(Note(id=note["_id"], title=note["title"], content=note["content"]))
    return notes

@app.get("/notes/{id}", response_model=Note)
def get_note(id: str, collection=Depends(get_collection)):
    note = collection.find_one({"_id": id})
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return Note(id=note["_id"], title=note["title"], content=note["content"])

@app.put("/notes/{id}")
def update_note(id: str, note: Note, collection=Depends(get_collection)):
    result = collection.update_one({"_id": id}, {"$set": note.model_dump()})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"message": "Note updated successfully"}

@app.delete("/notes/{id}")
def delete_note(id: str, collection=Depends(get_collection)):
    result = collection.delete_one({"_id": id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"message": "Note deleted successfully"}