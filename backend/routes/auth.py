"""
Authentication routes: signup, login, logout, get current user.
"""
from flask import Blueprint, request, jsonify, session
from models.db import users_col, now_utc
from bson import ObjectId
import bcrypt
import re
import jwt
from datetime import datetime, timedelta, timezone
from flask import current_app

auth_bp = Blueprint("auth", __name__)

# ─── Helpers ──────────────────────────────────────────────────────────────────
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

def _serialize_user(u, include_private=False):
    out = {
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
    return out

def _hash_pw(plain):
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

def _check_pw(plain, hashed):
    return bcrypt.checkpw(plain.encode(), hashed.encode())

def _err(msg, code=400):
    return jsonify({"error": msg}), code

def _ok(data, code=200):
    return jsonify(data), code

# ─── JWT Helpers ─────────────────────────────────────────────────────────────
def create_token(user_id):
    payload = {
        "sub": user_id,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(days=7)
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")

def decode_token(token):
    try:
        payload = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
        return payload["sub"]
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None

# ─── Routes ───────────────────────────────────────────────────────────────────

@auth_bp.route("/signup", methods=["POST"])
def signup():
    data = request.get_json(silent=True) or {}
    name     = (data.get("name") or "").strip()
    email    = (data.get("email") or "").strip().lower()
    password = data.get("password", "")
    age      = data.get("age")
    gender   = data.get("gender", "")
    height   = data.get("height")
    weight   = data.get("weight")

    if not name or not email or not password:
        return _err("Name, email, and password are required.")
    if not EMAIL_RE.match(email):
        return _err("Invalid email address.")
    if len(password) < 6:
        return _err("Password must be at least 6 characters.")

    col = users_col()
    if col.find_one({"email": email}):
        return _err("An account with this email already exists.")

    user_doc = {
        "name": name,
        "email": email,
        "password": _hash_pw(password),
        "plan": "free",
        "age": int(age) if age else None,
        "gender": gender or None,
        "height": float(height) if height else None,
        "weight": float(weight) if weight else None,
        "createdAt": now_utc(),
    }
    result = col.insert_one(user_doc)
    user_doc["_id"] = result.inserted_id

    session.permanent = True
    session["user_id"] = str(result.inserted_id)
    token = create_token(str(result.inserted_id))

    return _ok({
        "message": "Account created successfully.", 
        "user": _serialize_user(user_doc),
        "token": token
    }, 201)


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email    = (data.get("email") or "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return _err("Email and password are required.")

    user = users_col().find_one({"email": email})
    if not user or not _check_pw(password, user["password"]):
        return _err("Invalid email or password.", 401)

    session.permanent = True
    session["user_id"] = str(user["_id"])
    token = create_token(str(user["_id"]))
    print(f"[Auth] Login success for {email}, token generated.")

    return _ok({
        "message": "Login successful.", 
        "user": _serialize_user(user),
        "token": token
    })


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return _ok({"message": "Logged out successfully."})


@auth_bp.route("/user", methods=["GET"])
def get_user():
    # Try token first
    auth_header = request.headers.get("Authorization")
    uid = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        uid = decode_token(token)
    
    # Fallback to session (optional)
    if not uid:
        uid = session.get("user_id")

    print(f"[Auth] GET /user - Decoded uid: {uid}")
    if not uid:
        return _err("Not authenticated.", 401)
    
    user = users_col().find_one({"_id": ObjectId(uid)})
    if not user:
        return _err("User not found.", 404)
    return _ok({"user": _serialize_user(user)})
