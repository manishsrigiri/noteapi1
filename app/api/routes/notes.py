from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.database.mongodb import get_collection
from app.models.models import Note, PinRequest, User
from app.services.auth_service import get_current_user
from app.utils.helpers import normalize_note, now_iso

router = APIRouter(tags=["notes"])


@router.post("/notes")
def create_note(
    note: Note,
    collection=Depends(get_collection),
    user: User = Depends(get_current_user),
):
    if collection.find_one({"_id": note.id}):
        raise HTTPException(status_code=400, detail="Note already exists")
    payload = note.model_dump()
    payload["created_at"] = now_iso()
    payload["updated_at"] = payload["created_at"]
    collection.insert_one(payload | {"_id": note.id})
    return {"message": "Note created successfully"}


@router.get("/notes", response_model=List[Note])
def get_notes(collection=Depends(get_collection), user: User = Depends(get_current_user)):
    return [normalize_note(note) for note in collection.find()]


@router.get("/notes/stats")
def get_note_stats(collection=Depends(get_collection), user: User = Depends(get_current_user)):
    total_ids = collection.count_documents({})
    pinned_count = collection.count_documents({"pinned": True})
    private_count = collection.count_documents({"is_private": True})
    category_pipeline = [
        {"$group": {"_id": {"$ifNull": ["$category", "General"]}, "count": {"$sum": 1}}},
        {"$sort": {"count": -1, "_id": 1}},
    ]
    categories = {doc["_id"]: doc["count"] for doc in collection.aggregate(category_pipeline)}
    return {
        "total_ids": total_ids,
        "pinned_ids": pinned_count,
        "private_ids": private_count,
        "public_ids": total_ids - private_count,
        "categories": categories,
    }


@router.get("/notes/{id}", response_model=Note)
def get_note(id: str, collection=Depends(get_collection), user: User = Depends(get_current_user)):
    note = collection.find_one({"_id": id})
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return normalize_note(note)


@router.put("/notes/{id}")
def update_note(
    id: str,
    note: Note,
    collection=Depends(get_collection),
    user: User = Depends(get_current_user),
):
    existing = collection.find_one({"_id": id})
    if not existing:
        raise HTTPException(status_code=404, detail="Note not found")
    payload = note.model_dump()
    payload["id"] = id
    payload["created_at"] = existing.get("created_at", now_iso())
    payload["updated_at"] = now_iso()
    collection.update_one({"_id": id}, {"$set": payload})
    return {"message": "Note updated successfully"}


@router.put("/notes/{id}/pin")
def pin_note(
    id: str,
    pin_request: PinRequest,
    collection=Depends(get_collection),
    user: User = Depends(get_current_user),
):
    result = collection.update_one(
        {"_id": id},
        {"$set": {"pinned": pin_request.pinned, "updated_at": now_iso()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Note not found")
    action = "pinned" if pin_request.pinned else "unpinned"
    return {"message": f"Note {action} successfully"}


@router.delete("/notes/{id}")
def delete_note(
    id: str,
    collection=Depends(get_collection),
    user: User = Depends(get_current_user),
):
    result = collection.delete_one({"_id": id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"message": "Note deleted successfully"}
