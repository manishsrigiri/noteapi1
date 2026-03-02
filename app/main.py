from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient

app = FastAPI()

client = MongoClient("mongodb://mongo:27017")
db = client["notesdb"]
collection = db["notes"]


class Note(BaseModel):
    id: str
    title: str
    content: str


# ✅ Create Note with Custom ID
@app.post("/notes")
def create_note(note: Note):

    # Check if ID already exists
    if collection.find_one({"_id": note.id}):
        raise HTTPException(status_code=400, detail="ID already exists")

    note_dict = note.dict()
    note_dict["_id"] = note_dict.pop("id")

    collection.insert_one(note_dict)

    return {"message": "Note created successfully", "id": note_dict["_id"]}


# ✅ Get All Notes
@app.get("/notes")
def get_notes():
    notes = []
    for note in collection.find():
        # Convert _id to string for JSON serialization
        note["id"] = str(note.pop("_id"))
        notes.append(note)
    return notesS


# ✅ Get Single Note
@app.get("/notes/{id}")
def get_note(id: str):
    note = collection.find_one({"_id": id})

    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    note["id"] = note.pop("_id")
    return note


# ✅ Update Note
@app.put("/notes/{id}")
def update_note(id: str, note: Note):
    result = collection.update_one(
        {"_id": id},
        {"$set": {"title": note.title, "content": note.content}}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Note not found")

    return {"message": "Note updated successfully"}


# ✅ Delete 
@app.delete("/notes/{id}")
def delete_note(id: str):
    result = collection.delete_one({"_id": id})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Note not found")

    return {"message": "Note deleted successfully"}