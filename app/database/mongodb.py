import os

from fastapi import Depends
from pymongo import MongoClient


def get_client():
    mongo_uri = os.getenv("MONGO_URI", "mongodb://mongo:27017")
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
