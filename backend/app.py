import os
from flask import Flask, jsonify
from dotenv import load_dotenv
from flask_cors import CORS

from routes.auth       import auth_bp
from routes.jobs       import jobs_bp
from routes.candidates import candidates_bp
from routes.pipeline   import pipeline_bp

load_dotenv()

def create_app():
    app = Flask(__name__)

    # ── CORS — allow React dev server ────────────────────────────────────────
    # ── CORS — allow local dev + deployed frontend ───────────────────────────
    allowed_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    frontend_url = os.getenv("FRONTEND_URL")
    if frontend_url:
        allowed_origins.append(frontend_url)

    CORS(app, resources={r"/api/*": {"origins": allowed_origins}}, supports_credentials=True)

    # ── Register Blueprints ──────────────────────────────────────────────────
    app.register_blueprint(auth_bp,       url_prefix="/api/auth")
    app.register_blueprint(jobs_bp,       url_prefix="/api/jobs")
    app.register_blueprint(candidates_bp, url_prefix="/api/candidates")
    app.register_blueprint(pipeline_bp,   url_prefix="/api/pipeline")
    # ── Create DB indexes on startup ─────────────────────────────────────────
    from utils.db import create_indexes
    create_indexes()

    # ── Health Check ─────────────────────────────────────────────────────────
    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({
            "status" : "ok",
            "message": "RecruitMate AI backend is running"
        }), 200

    # ── Global Error Handler ─────────────────────────────────────────────────
    @app.errorhandler(Exception)
    def handle_exception(e):
        return jsonify({"success": False, "error": str(e)}), 500

    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)