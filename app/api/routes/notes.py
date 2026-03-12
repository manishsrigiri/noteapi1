import secrets
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.database.mongodb import get_collection, get_request_collection
from app.models.models import ChangeDecisionRequest, Note, NoteChangeRequest, PinRequest, User
from app.services.auth_service import get_current_user
from app.utils.helpers import normalize_note, now_iso

router = APIRouter(tags=["notes"])


def _can_edit(user: User) -> bool:
    return user.is_admin or user.role in {"editor", "admin"}


@router.post("/notes")
def create_note(
    note: Note,
    collection=Depends(get_collection),
    user: User = Depends(get_current_user),
):
    if not _can_edit(user):
        raise HTTPException(status_code=403, detail="Editor access required")
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
    if not _can_edit(user):
        raise HTTPException(status_code=403, detail="Editor access required")
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
    if not _can_edit(user):
        raise HTTPException(status_code=403, detail="Editor access required")
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
    if not _can_edit(user):
        raise HTTPException(status_code=403, detail="Editor access required")
    result = collection.delete_one({"_id": id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"message": "Note deleted successfully"}


@router.post("/notes/requests")
def create_change_request(
    request: NoteChangeRequest,
    request_collection=Depends(get_request_collection),
    user: User = Depends(get_current_user),
):
    action = (request.action or "").strip().lower()
    if action not in {"create", "update", "delete", "pin"}:
        raise HTTPException(status_code=400, detail="Invalid action")
    if action != "create" and not request.note_id:
        raise HTTPException(status_code=400, detail="note_id is required")
    if action in {"create", "update", "pin"} and not request.payload:
        raise HTTPException(status_code=400, detail="payload is required")

    request_id = secrets.token_urlsafe(12)
    doc = {
        "_id": request_id,
        "action": action,
        "note_id": request.note_id,
        "payload": request.payload,
        "reason": request.reason,
        "status": "pending",
        "requested_by": user.username,
        "requested_by_role": user.role,
        "requested_at": now_iso(),
    }
    request_collection.insert_one(doc)
    return {"message": "Request submitted", "request_id": request_id}


@router.get("/notes/requests")
def list_change_requests(
    status: str | None = "pending",
    request_collection=Depends(get_request_collection),
    user: User = Depends(get_current_user),
):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    query = {}
    if status and status != "all":
        query["status"] = status
    requests = list(request_collection.find(query))
    return {"requests": requests}


@router.post("/notes/requests/{request_id}/approve")
def approve_change_request(
    request_id: str,
    request_collection=Depends(get_request_collection),
    collection=Depends(get_collection),
    user: User = Depends(get_current_user),
):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    req = request_collection.find_one({"_id": request_id})
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req.get("status") != "pending":
        raise HTTPException(status_code=400, detail="Request already resolved")

    action = req.get("action")
    note_id = req.get("note_id")
    payload = req.get("payload") or {}

    if action == "create":
        if collection.find_one({"_id": payload.get("id")}):
            raise HTTPException(status_code=400, detail="Note already exists")
        payload["created_at"] = now_iso()
        payload["updated_at"] = payload["created_at"]
        collection.insert_one(payload | {"_id": payload.get("id")})
    elif action == "update":
        existing = collection.find_one({"_id": note_id})
        if not existing:
            raise HTTPException(status_code=404, detail="Note not found")
        payload["id"] = note_id
        payload["created_at"] = existing.get("created_at", now_iso())
        payload["updated_at"] = now_iso()
        collection.update_one({"_id": note_id}, {"$set": payload})
    elif action == "delete":
        result = collection.delete_one({"_id": note_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Note not found")
    elif action == "pin":
        result = collection.update_one(
            {"_id": note_id},
            {"$set": {"pinned": payload.get("pinned", False), "updated_at": now_iso()}},
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Note not found")
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    request_collection.update_one(
        {"_id": request_id},
        {
            "$set": {
                "status": "approved",
                "approved_by": user.username,
                "approved_at": now_iso(),
            }
        },
    )
    return {"message": "Request approved"}


@router.post("/notes/requests/{request_id}/decline")
def decline_change_request(
    request_id: str,
    decision: ChangeDecisionRequest,
    request_collection=Depends(get_request_collection),
    user: User = Depends(get_current_user),
):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    req = request_collection.find_one({"_id": request_id})
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req.get("status") != "pending":
        raise HTTPException(status_code=400, detail="Request already resolved")
    request_collection.update_one(
        {"_id": request_id},
        {
            "$set": {
                "status": "declined",
                "declined_by": user.username,
                "declined_at": now_iso(),
                "decline_reason": decision.reason,
            }
        },
    )
    return {"message": "Request declined"}
