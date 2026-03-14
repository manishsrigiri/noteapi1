import os

from fastapi import Depends
from pymongo import MongoClient


def _load_local_env(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                os.environ.setdefault(key, value)
    except OSError:
        return


_load_local_env()


def get_client():
    mongo_uri = os.getenv("MONGO_URI", "mongodb://mongo:27017").strip()
    if not mongo_uri:
        mongo_uri = "mongodb://mongo:27017"
    return MongoClient(mongo_uri)


def get_collection(client: MongoClient = Depends(get_client)):
    db = client["notesdb"]
    return db["notes"]


def get_session_collection(client: MongoClient = Depends(get_client)):
    db = client["notesdb"]
    return db["sessions"]


def get_user_collection(client: MongoClient = Depends(get_client)):
    db = client["notesdb"]
    return db["users"]


def get_request_collection(client: MongoClient = Depends(get_client)):
    db = client["notesdb"]
    return db["note_requests"]
