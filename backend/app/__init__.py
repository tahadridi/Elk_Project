import logging

from flask import Flask, jsonify
from werkzeug.exceptions import RequestEntityTooLarge

from .config import Config
from .extensions import init_extensions, jwt
from .services.geoip_service import GeoIPService
from .services.mongo import ensure_indexes, seed_default_settings

logger = logging.getLogger(__name__)


def create_app(config_object=None, mongo_client=None, redis_client=None, es_client=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config_object:
        app.config.update(config_object)

    init_extensions(app, mongo_client, redis_client, es_client)
    app.extensions["geoip"] = GeoIPService(db_path=app.config["GEOIP_DB_PATH"])
    jwt.init_app(app)

    from .api.admin import bp as admin_bp
    from .api.auth import bp as auth_bp
    from .api.docs import bp as docs_bp
    from .api.files import bp as files_bp
    from .api.health import bp as health_bp
    from .api.logs import bp as logs_bp
    from .api.stats import bp as stats_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(logs_bp)
    app.register_blueprint(stats_bp)
    app.register_blueprint(docs_bp)

    register_jwt_handlers()
    register_error_handlers(app)

    if app.config.get("SEED_DEFAULTS", True):
        with app.app_context():
            try:
                ensure_indexes()
                seed_default_settings()
            except Exception:
                logger.warning("MongoDB initialization deferred until first request", exc_info=True)

    return app


def register_jwt_handlers():
    @jwt.unauthorized_loader
    def missing_token(reason):
        return jsonify({"error": {"code": "UNAUTHORIZED", "message": reason}}), 401

    @jwt.invalid_token_loader
    def invalid_token(reason):
        return jsonify({"error": {"code": "INVALID_TOKEN", "message": reason}}), 401

    @jwt.expired_token_loader
    def expired_token(_header, _payload):
        return jsonify({"error": {"code": "TOKEN_EXPIRED", "message": "Token has expired"}}), 401

    @jwt.revoked_token_loader
    def revoked_token(_header, _payload):
        return jsonify({"error": {"code": "TOKEN_REVOKED", "message": "Token has been revoked"}}), 401


def register_error_handlers(app):
    @app.errorhandler(RequestEntityTooLarge)
    def too_large(_error):
        return jsonify(
            {
                "error": {
                    "code": "FILE_TOO_LARGE",
                    "message": f"File exceeds the {app.config['MAX_UPLOAD_MB']} MB limit",
                }
            }
        ), 413

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"error": {"code": "NOT_FOUND", "message": "Resource not found"}}), 404

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return jsonify({"error": {"code": "METHOD_NOT_ALLOWED", "message": "Method not allowed"}}), 405

    @app.errorhandler(Exception)
    def unhandled(error):
        logger.exception("Unhandled application error", exc_info=error)
        return jsonify({"error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}}), 500
