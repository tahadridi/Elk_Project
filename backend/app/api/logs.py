import csv
import io

from flask import Blueprint, Response, current_app, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from ..services.policy_service import get_search_policy
from ..services.search_service import (
    clear_search_history,
    export_logs,
    get_log,
    list_search_history,
    save_search_history,
    search_logs,
)
from ..utils.responses import (
    error_response,
    paginated,
    parse_pagination,
    success_response,
)

bp = Blueprint("logs", __name__, url_prefix="/api/v1")


def _search_args():
    return {
        "q": request.args.get("q"),
        "level": request.args.get("level"),
        "service": request.args.get("service"),
        "date_from": request.args.get("date_from"),
        "date_to": request.args.get("date_to"),
        "sort": request.args.get("sort", "date"),
        "order": request.args.get("order", "desc"),
    }


@bp.get("/logs/export")
@jwt_required()
def export():
    args = _search_args()
    try:
        rows = export_logs(**args)
    except ValueError as exc:
        return error_response("INVALID_QUERY", str(exc), 400)
    except Exception:
        current_app.logger.exception("Elasticsearch export failed")
        return error_response("ELASTICSEARCH_UNAVAILABLE", "Search service unavailable", 503)

    def generate():
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            ["timestamp", "level", "service", "source_ip", "user", "message"]
        )
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)
        for row in rows:
            writer.writerow(
                [
                    row.get("timestamp"),
                    row.get("level"),
                    row.get("service"),
                    row.get("source_ip"),
                    row.get("user"),
                    row.get("message"),
                ]
            )
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    return Response(
        generate(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=security-logs.csv"},
    )


@bp.get("/logs")
@jwt_required()
def search():
    args = _search_args()
    default_per_page = int(get_search_policy().get("page_size", 50))
    page, per_page = parse_pagination(default_per_page=default_per_page)
    try:
        items, total = search_logs(
            **args,
            page=page,
            per_page=per_page,
        )
    except ValueError as exc:
        return error_response("INVALID_QUERY", str(exc), 400)
    except Exception:
        current_app.logger.exception("Elasticsearch search failed")
        return error_response("ELASTICSEARCH_UNAVAILABLE", "Search service unavailable", 503)

    if page == 1:
        save_search_history(
            get_jwt_identity(),
            get_jwt().get("username"),
            args["q"],
            args["level"],
            args["service"],
            args["date_from"],
            args["date_to"],
        )

    return jsonify(paginated(items, total, page, per_page)), 200


@bp.get("/logs/<log_id>")
@jwt_required()
def detail(log_id):
    try:
        item = get_log(log_id)
    except Exception:
        current_app.logger.exception("Elasticsearch get failed")
        return error_response("ELASTICSEARCH_UNAVAILABLE", "Search service unavailable", 503)
    if item is None:
        return error_response("LOG_NOT_FOUND", "Log not found", 404)
    return success_response(item)


@bp.get("/search/history")
@jwt_required()
def search_history():
    page, per_page = parse_pagination(default_per_page=20)
    items, total = list_search_history(get_jwt_identity(), page, per_page)
    return jsonify(paginated(items, total, page, per_page)), 200


@bp.delete("/search/history")
@jwt_required()
def delete_search_history():
    deleted = clear_search_history(get_jwt_identity())
    return jsonify({"deleted": deleted}), 200
