"""
HealthFlow Flask Backend
========================
Main application entry point.

Run locally:
    cd backend
    python app.py

Or with gunicorn (production):
    gunicorn app:app --bind 0.0.0.0:5000 --workers 2
"""

import os, re
from flask import Flask, jsonify
from flask_cors import CORS

# ─── App Factory ──────────────────────────────────────────────────────────────
def create_app(env: str = None) -> Flask:
    app = Flask(__name__)

    # ── Config ────────────────────────────────────────────────────────────────
    from config import config
    env = env or os.environ.get("FLASK_ENV", "development")
    app.config.from_object(config.get(env, config["default"]))

    # ── CORS ──────────────────────────────────────────────────────────────────
    # Merge env origins with necessary Vercel patterns to prevent overrides
    env_origins = app.config.get("CORS_ORIGINS", [])
    processed_origins = []
    for o in env_origins:
        if o.startswith("re:"):
            processed_origins.append(re.compile(o[3:]))
        else:
            processed_origins.append(o)
    
    # Always allow Vercel subdomains
    processed_origins.append(re.compile(r"https://.*\.vercel\.app"))

    CORS(
        app,
        origins=processed_origins,
        supports_credentials=True,
        allow_headers=["Content-Type", "Authorization"],
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    )

    # Logging Hook for debugging CORS
    from flask import request
    @app.before_request
    def log_request_info():
        origin = request.headers.get("Origin")
        if origin:
            app.logger.info(f"Incoming Request Origin: {origin}")

    # ── Blueprints / Routes ───────────────────────────────────────────────────
    from routes.auth    import auth_bp
    from routes.health  import health_bp
    from routes.profile import profile_bp

    API = "/api"
    app.register_blueprint(auth_bp,    url_prefix=API)
    app.register_blueprint(health_bp,  url_prefix=API)
    app.register_blueprint(profile_bp, url_prefix=API)

    # ── Health Check ──────────────────────────────────────────────────────────
    @app.route("/")
    def root():
        return jsonify({
            "app": "HealthFlow API",
            "version": "1.0.0",
            "status": "running",
            "docs": "See README.md for API documentation",
        })

    @app.route("/api/health")
    def api_health():
        try:
            from models.db import get_db
            get_db().command("ping")
            db_status = "connected"
        except Exception as e:
            db_status = f"error: {str(e)}"
        return jsonify({"status": "ok", "database": db_status})

    # ── Error Handlers ────────────────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Endpoint not found."}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": "Method not allowed."}), 405

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "Internal server error."}), 500

    return app


# ─── Entry Point ──────────────────────────────────────────────────────────────
app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"""
╔══════════════════════════════════════╗
║   🌿 HealthFlow API v1.0.0           ║
║   Running on http://localhost:{port}   ║
║   Press CTRL+C to stop               ║
╚══════════════════════════════════════╝
""")
    app.run(host="0.0.0.0", port=port, debug=app.config.get("DEBUG", False))
