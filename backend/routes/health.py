"""
Health tracking routes: save, get today, get weekly, get all, insights, delete, export.
"""
from flask import Blueprint, request, jsonify, session, Response
from models.db import logs_col, users_col, now_utc
from bson import ObjectId
from datetime import datetime, timezone, timedelta
import io, csv

health_bp = Blueprint("health", __name__)

def _err(msg, code=400):
    return jsonify({"error": msg}), code

def _ok(data, code=200):
    return jsonify(data), code

def _require_auth():
    from routes.auth import decode_token
    
    auth_header = request.headers.get("Authorization")
    print(f"[Health] Auth Check - Header: {auth_header[:20] if auth_header else 'None'}...")
    
    uid = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        uid = decode_token(token)
    
    if not uid:
        uid = session.get("user_id")
        if uid: print(f"[Health] Auth Check - Found uid in session: {uid}")

    if not uid:
        print(f"[Health] Auth failed. Request Host: {request.host}, Origin: {request.origin}")
        return None, (_err("Not authenticated.", 401))
    
    return uid, None

def _serialize_log(log):
    return {
        "_id": str(log["_id"]),
        "user_id": str(log.get("user_id", "")),
        "water": log.get("water"),
        "steps": log.get("steps"),
        "mood": log.get("mood"),
        "weight": log.get("weight"),
        "sleep": log.get("sleep"),
        "bmi": log.get("bmi"),
        "date": log.get("date").isoformat() if log.get("date") else None,
        "createdAt": log.get("createdAt").isoformat() if log.get("createdAt") else None,
    }

def _today_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def _parse_date(date_str):
    """Parse YYYY-MM-DD date string into timezone-aware datetime at midnight UTC."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


@health_bp.route("/save-health", methods=["POST"])
def save_health():
    uid, err = _require_auth()
    if err: 
        print(f"[SaveHealth] Auth failed: {err}")
        return err

    data = request.get_json(silent=True) or {}
    date_str = data.get("date") or _today_str()
    date_dt = _parse_date(date_str)
    
    print(f"[SaveHealth] Saving data for user {uid} on date {date_str}")

    # Upsert: one log per user per day
    update_fields = {"updatedAt": now_utc()}
    for field in ["water", "steps", "mood", "weight", "sleep", "bmi"]:
        val = data.get(field)
        if val is not None:
            try:
                update_fields[field] = float(val) if field in ["weight", "sleep", "bmi"] else val
            except (ValueError, TypeError):
                print(f"[SaveHealth] Invalid value for {field}: {val}")

    try:
        result = logs_col().find_one_and_update(
            {"user_id": ObjectId(uid), "date": date_dt},
            {
                "$set": update_fields,
                "$setOnInsert": {"user_id": ObjectId(uid), "date": date_dt, "createdAt": now_utc()},
            },
            upsert=True,
            return_document=True,
        )
        print(f"[SaveHealth] Successfully saved log: {result.get('_id')}")
        return _ok({"message": "Health log saved.", "log": _serialize_log(result)}, 200)
    except Exception as e:
        print(f"[SaveHealth] Database error: {str(e)}")
        return _err(f"Database error: {str(e)}", 500)


@health_bp.route("/get-today-health", methods=["GET"])
def get_today_health():
    uid, err = _require_auth()
    if err: return err

    today = _parse_date(_today_str())
    log = logs_col().find_one({"user_id": ObjectId(uid), "date": today})
    return _ok({"log": _serialize_log(log) if log else None})


@health_bp.route("/get-weekly-health", methods=["GET"])
def get_weekly_health():
    uid, err = _require_auth()
    if err: return err

    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    logs = list(
        logs_col()
        .find({"user_id": ObjectId(uid), "date": {"$gte": seven_days_ago}})
        .sort("date", 1)
    )
    return _ok({"logs": [_serialize_log(l) for l in logs]})


@health_bp.route("/get-health", methods=["GET"])
def get_all_health():
    uid, err = _require_auth()
    if err: return err

    limit = min(int(request.args.get("limit", 30)), 90)
    logs = list(
        logs_col()
        .find({"user_id": ObjectId(uid)})
        .sort("date", -1)
        .limit(limit)
    )
    return _ok({"logs": [_serialize_log(l) for l in logs]})


@health_bp.route("/save-bmi", methods=["POST"])
def save_bmi():
    uid, err = _require_auth()
    if err: return err

    data = request.get_json(silent=True) or {}
    bmi    = data.get("bmi")
    height = data.get("height")
    weight = data.get("weight")

    if not bmi:
        return _err("BMI value is required.")

    today = _parse_date(_today_str())
    result = logs_col().find_one_and_update(
        {"user_id": ObjectId(uid), "date": today},
        {
            "$set": {"bmi": float(bmi), "height": height, "weight": weight, "updatedAt": now_utc()},
            "$setOnInsert": {"user_id": ObjectId(uid), "date": today, "createdAt": now_utc()},
        },
        upsert=True,
        return_document=True,
    )
    return _ok({"message": "BMI saved.", "log": _serialize_log(result)})


@health_bp.route("/get-insights", methods=["GET"])
def get_insights():
    uid, err = _require_auth()
    if err: return err

    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    logs = list(
        logs_col()
        .find({"user_id": ObjectId(uid), "date": {"$gte": thirty_days_ago}})
        .sort("date", 1)
    )

    total = len(logs)
    if total == 0:
        return _ok({
            "total_logs": 0, "averages": {}, "streak": 0,
            "personal_bests": {}, "trends": [], "tips": ["Start logging your health data to get personalized insights!"]
        })

    # Averages
    def avg(field):
        vals = [l[field] for l in logs if l.get(field) is not None]
        return round(sum(vals) / len(vals), 1) if vals else None

    averages = {
        "water": avg("water"), "steps": avg("steps"),
        "mood": avg("mood"), "weight": avg("weight"), "sleep": avg("sleep"),
    }

    # Personal bests
    def best(field, mode="max"):
        vals = [l[field] for l in logs if l.get(field) is not None]
        if not vals: return None
        return max(vals) if mode == "max" else min(vals)

    personal_bests = {
        "max_steps": best("steps"), "best_sleep": best("sleep"),
        "max_water": best("water"), "best_mood": best("mood"),
    }

    # Streak — consecutive days with at least one metric logged
    streak = 0
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    log_dates = set()
    for l in logs:
        d = l.get("date")
        if d:
            log_dates.add(d.strftime("%Y-%m-%d"))
    check = today
    while check >= thirty_days_ago:
        if check.strftime("%Y-%m-%d") in log_dates:
            streak += 1
            check -= timedelta(days=1)
        else:
            break

    # Trends — daily data points for charting
    trends = []
    for l in logs:
        trends.append({
            "date": l["date"].strftime("%Y-%m-%d") if l.get("date") else None,
            "water": l.get("water"), "steps": l.get("steps"),
            "mood": l.get("mood"), "weight": l.get("weight"), "sleep": l.get("sleep"),
        })

    # Smart tips based on actual data
    tips = []
    if averages["sleep"] and averages["sleep"] < 7:
        tips.append(f"💤 Your average sleep is {averages['sleep']}h. Aim for 7–9 hours for optimal health.")
    if averages["water"] and averages["water"] < 6:
        tips.append(f"💧 You're averaging {averages['water']} glasses of water. Try to reach 8 glasses daily.")
    if averages["steps"] and averages["steps"] < 5000:
        tips.append(f"👟 Your avg steps ({int(averages['steps'])}) are below recommended. Try adding a 20-min walk.")
    if averages["steps"] and averages["steps"] >= 8000:
        tips.append(f"🏃 Great activity level! You're averaging {int(averages['steps'])} steps/day.")
    if averages["mood"] and averages["mood"] >= 4:
        tips.append("😊 Your mood has been consistently positive — keep doing what works!")
    if averages["mood"] and averages["mood"] < 3:
        tips.append("🧘 Your mood has been low lately. Consider mindfulness exercises or talking to someone.")
    if streak >= 7:
        tips.append(f"🔥 Amazing {streak}-day logging streak! Consistency is key to better health.")
    if streak == 0:
        tips.append("📝 Log today's health to start building your streak!")

    # correlations
    correlations = []
    # Steps vs Mood
    high_step_moods = [l["mood"] for l in logs if l.get("steps") and l["steps"] >= 8000 and l.get("mood")]
    low_step_moods = [l["mood"] for l in logs if l.get("steps") and l["steps"] < 5000 and l.get("mood")]
    if high_step_moods and low_step_moods:
        h_avg = sum(high_step_moods) / len(high_step_moods)
        l_avg = sum(low_step_moods) / len(low_step_moods)
        if h_avg - l_avg >= 0.5:
            correlations.append("📊 You tend to feel happier on days you walk 8,000+ steps!")
            tips.append("💡 Activity Boost: You feel significantly better on active days. Keep moving!")

    # Sleep vs Mood
    good_sleep_moods = [l["mood"] for l in logs if l.get("sleep") and l["sleep"] >= 7.5 and l.get("mood")]
    bad_sleep_moods = [l["mood"] for l in logs if l.get("sleep") and l["sleep"] < 6 and l.get("mood")]
    if good_sleep_moods and bad_sleep_moods:
        gs_avg = sum(good_sleep_moods) / len(good_sleep_moods)
        bs_avg = sum(bad_sleep_moods) / len(bad_sleep_moods)
        if gs_avg - bs_avg >= 0.5:
            correlations.append("😴 Better sleep is clearly linked to your positive mood.")
    
    if not tips:
        tips.append("Keep tracking — more data means smarter insights!")

    return _ok({
        "total_logs": total, "averages": averages, "streak": streak,
        "personal_bests": personal_bests, "trends": trends, "tips": tips,
        "correlations": correlations
    })


@health_bp.route("/delete-health/<log_id>", methods=["DELETE"])
def delete_health(log_id):
    uid, err = _require_auth()
    if err: return err

    try:
        result = logs_col().delete_one({"_id": ObjectId(log_id), "user_id": ObjectId(uid)})
    except Exception:
        return _err("Invalid log ID.", 400)

    if result.deleted_count == 0:
        return _err("Log not found or not yours.", 404)
    return _ok({"message": "Health log deleted."})


@health_bp.route("/export-health", methods=["GET"])
def export_health():
    uid, err = _require_auth()
    if err: return err

    logs = list(
        logs_col()
        .find({"user_id": ObjectId(uid)})
        .sort("date", -1)
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Water (glasses)", "Steps", "Mood (1-5)", "Weight (kg)", "Sleep (hrs)", "BMI"])
    for l in logs:
        writer.writerow([
            l.get("date").strftime("%Y-%m-%d") if l.get("date") else "",
            l.get("water", ""), l.get("steps", ""), l.get("mood", ""),
            l.get("weight", ""), l.get("sleep", ""), l.get("bmi", ""),
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=healthflow-export.csv"}
    )
