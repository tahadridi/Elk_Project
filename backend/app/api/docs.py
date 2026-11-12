from flask import Blueprint, current_app, render_template_string, send_from_directory

bp = Blueprint("docs", __name__, url_prefix="/api/v1")

SWAGGER_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Security Monitoring API</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    window.ui = SwaggerUIBundle({
      url: "/api/v1/openapi.yaml",
      dom_id: "#swagger-ui",
      deepLinking: true,
      persistAuthorization: true
    });
  </script>
</body>
</html>
"""


@bp.get("/docs")
def docs():
    return render_template_string(SWAGGER_HTML)


@bp.get("/openapi.yaml")
def openapi():
    return send_from_directory(current_app.static_folder, "openapi.yaml", mimetype="application/yaml")
