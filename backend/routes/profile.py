"""
Profile routes: view and update user profile.
"""
from flask import Blueprint, request, jsonify, session
from models.db import users_col, now_utc
from bson import ObjectId
import bcrypt

profile_bp = Blueprint("profile", __name__)

def _err(msg, code=400):
    return jsonify({"error": msg}), code

def _ok(data, code=200):
    return jsonify(data), code

def _serialize_user(u):
    return {
        "_id": str(u["_id"]),
        "name": u.get("name", ""),
        "email": u.get("email", ""),
        "plan": u.get("plan", "free"),
        "age": u.get("age"),
        "gender": u.get("gender"),
        "height": u.get("height"),
        "weight": u.get("weight"),
        "createdAt": u.get("createdAt").isoformat() if u.get("createdAt") else None,
    }

def _require_auth():
    from routes.auth import decode_token
    auth_header = request.headers.get("Authorization")
    uid = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        uid = decode_token(token)
    
    if not uid:
        uid = session.get("user_id")
    
    if not uid:
        return None, _err("Not authenticated.", 401)
    return uid, None


@profile_bp.route("/profile", methods=["GET"])
def get_profile():
    uid, err = _require_auth()
    if err: return err
    user = users_col().find_one({"_id": ObjectId(uid)})
    if not user:
        return _err("User not found.", 404)
    return _ok({"user": _serialize_user(user)})


@profile_bp.route("/update-profile", methods=["POST"])
def update_profile():
    uid, err = _require_auth()
    if err: return err

    data = request.get_json(silent=True) or {}
    update = {"updatedAt": now_utc()}

    if "name" in data and data["name"].strip():
        update["name"] = data["name"].strip()
    if "age" in data and data["age"]:
        update["age"] = int(data["age"])
    if "gender" in data:
        update["gender"] = data["gender"]
    if "height" in data and data["height"]:
        update["height"] = float(data["height"])
    if "weight" in data and data["weight"]:
        update["weight"] = float(data["weight"])

    # Password change
    if "password" in data and data["password"]:
        pw = data["password"]
        if len(pw) < 6:
            return _err("Password must be at least 6 characters.")
        update["password"] = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

    if len(update) <= 1:
        return _err("No fields to update.")

    users_col().update_one({"_id": ObjectId(uid)}, {"$set": update})
    user = users_col().find_one({"_id": ObjectId(uid)})
    return _ok({"message": "Profile updated successfully.", "user": _serialize_user(user)})
