"""
Database connection and collection helpers.
All MongoDB interaction goes through this module.
"""
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure
from datetime import datetime, timezone
import os
import certifi

_client = None
_db = None

def get_db():
    global _client, _db
    if _db is None:
        uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/healthflow")
        db_name = os.environ.get("DB_NAME", "healthflow")
        print(f"[DB] Connecting to MongoDB: {uri[:30]}... (DB: {db_name})")
        _client = MongoClient(
            uri,
            serverSelectionTimeoutMS=5000,
            tls=True,
            tlsAllowInvalidCertificates=True,
        )
        _db = _client[db_name]
        try:
            _client.admin.command('ping')
            print("[DB] MongoDB connected successfully!")
        except Exception as e:
            print(f"[DB] MongoDB connection failed: {str(e)}")
        _ensure_indexes(_db)
    return _db

def _ensure_indexes(db):
    """Create indexes for performance."""
    try:
        db.users.create_index("email", unique=True)
        db.health_logs.create_index([("user_id", ASCENDING), ("date", DESCENDING)])
        db.health_logs.create_index("createdAt")
    except Exception:
        pass  # Indexes may already exist

def now_utc():
    return datetime.now(timezone.utc)

def users_col():
    return get_db().users

def logs_col():
    return get_db().health_logs
