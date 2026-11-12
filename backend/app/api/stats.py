from flask import Blueprint, current_app, jsonify
from flask_jwt_extended import jwt_required

from ..services.search_service import get_stats
from ..utils.responses import error_response

bp = Blueprint("stats", __name__, url_prefix="/api/v1")


@bp.get("/stats")
@jwt_required()
def stats():
    try:
        return jsonify({"stats": get_stats()}), 200
    except Exception:
        current_app.logger.exception("Unable to compute stats")
        return error_response("STATS_UNAVAILABLE", "Unable to compute statistics", 503)
