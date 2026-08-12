"""app/__init__.py — Flask application factory."""
import logging
from flask import Flask, jsonify, send_from_directory
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
import os

from app.config import config

logging.basicConfig(
    level=logging.DEBUG if config.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# urllib3 logs every connection at DEBUG, which buries the WAAS/API
# lines that actually matter. Warnings and errors still come through.
logging.getLogger("urllib3").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

jwt     = JWTManager()
limiter = Limiter(key_func=get_remote_address)


def create_app() -> Flask:
    # templates folder sits one level up from app/
    template_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
    app = Flask(__name__, template_folder=os.path.abspath(template_dir))

    app.config["SECRET_KEY"]                = config.SECRET_KEY
    app.config["JWT_SECRET_KEY"]            = config.JWT_SECRET_KEY
    app.config["JWT_ACCESS_TOKEN_EXPIRES"]  = config.JWT_ACCESS_TOKEN_EXPIRES
    app.config["JWT_REFRESH_TOKEN_EXPIRES"] = config.JWT_REFRESH_TOKEN_EXPIRES
    app.config["RATELIMIT_DEFAULT"]         = config.RATELIMIT_DEFAULT
    app.config["RATELIMIT_STORAGE_URI"]     = config.RATELIMIT_STORAGE_URL

    jwt.init_app(app)
    limiter.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": config.ALLOWED_ORIGINS}})

    with app.app_context():
        from app.database import init_db
        try:
            init_db()
            logger.info("Database initialised.")
        except Exception as exc:
            logger.warning("DB init skipped: %s", exc)

    # ── Blueprints ────────────────────────────────────────────
    from app.routes.user_routes  import user_bp
    from app.routes.auth_routes  import auth_bp
    from app.routes.admin_routes import admin_bp
    from app.routes.kyc_routes   import kyc_bp

    limiter.limit(config.RATELIMIT_OTP_SEND)(user_bp)
    limiter.limit(config.RATELIMIT_LOGIN)(user_bp)

    app.register_blueprint(user_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(kyc_bp)

    # ── Swagger ───────────────────────────────────────────────
    try:
        from flasgger import Swagger
        Swagger(app, template={
            "info": {"title": "NBAWORLD.IN Partner API", "version": "1.0.0"},
            "securityDefinitions": {
                "BearerAuth": {"type": "apiKey", "name": "Authorization", "in": "header"}
            },
        })
    except Exception:
        pass

    # ── Error handlers ────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(_):
        return jsonify({"success": False, "message": "Endpoint not found."}), 404

    @app.errorhandler(405)
    def method_not_allowed(_):
        return jsonify({"success": False, "message": "Method not allowed."}), 405

    @app.errorhandler(429)
    def rate_limited(_):
        return jsonify({"success": False, "message": "Too many requests. Please slow down."}), 429

    @app.errorhandler(500)
    def internal_error(exc):
        logger.exception("Unhandled: %s", exc)
        from app.utils.error_logging import record_error
        record_error("user", exc)
        return jsonify({"success": False, "message": "Internal server error."}), 500

    # ── Health ────────────────────────────────────────────────
    @app.get("/health")
    def health():
        from app.database import check_db_connection
        ok = check_db_connection()
        return jsonify({"status": "ok" if ok else "degraded",
                        "database": "connected" if ok else "unavailable"}), 200 if ok else 503

    # ── Serve the frontend HTML (index) ───────────────────────
    @app.route("/")
    def index():
        return send_from_directory(
            os.path.join(app.root_path, "..", "templates"), "index.html"
        )

    logger.info("NBAWORLD.IN API started (debug=%s)", config.DEBUG)
    return app
