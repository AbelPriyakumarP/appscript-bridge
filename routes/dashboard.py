from flask import Blueprint, render_template, current_app, session
from services.storage import APP_CREDENTIAL_SCHEMAS

dashboard_bp = Blueprint("dashboard", __name__)


def _ctx(**extra):
    storage = current_app.config["STORAGE"]
    tokens = storage.get_google_tokens()
    base = {
        "google_connected": bool(tokens and tokens.get("access_token")),
        "user_email": session.get("user_email", ""),
        "user_name": session.get("user_name", ""),
        "user_picture": session.get("user_picture", ""),
        "base_url": current_app.config["BASE_URL"],
        "app_schemas": APP_CREDENTIAL_SCHEMAS,
    }
    base.update(extra)
    return base


@dashboard_bp.route("/")
def index():
    return render_template("dashboard.html", **_ctx(page="dashboard"))


@dashboard_bp.route("/workspaces")
def workspaces():
    return render_template("workspaces.html", **_ctx(page="workspaces"))


@dashboard_bp.route("/workspaces/<workspace_id>")
def workspace_detail(workspace_id):
    storage = current_app.config["STORAGE"]
    ws = storage.get_workspace(workspace_id)
    return render_template("workspace_detail.html", **_ctx(page="workspaces", workspace=ws))


@dashboard_bp.route("/workspaces/<workspace_id>/projects/<project_id>")
def project_detail(workspace_id, project_id):
    storage = current_app.config["STORAGE"]
    ws = storage.get_workspace(workspace_id)
    proj = storage.get_project(project_id)
    return render_template("project_detail.html", **_ctx(page="workspaces", workspace=ws, project=proj))


@dashboard_bp.route("/workspaces/<workspace_id>/projects/<project_id>/workflows/new")
def workflow_create(workspace_id, project_id):
    storage = current_app.config["STORAGE"]
    ws = storage.get_workspace(workspace_id)
    proj = storage.get_project(project_id)
    creds = storage.get_credentials(workspace_id)
    return render_template("workflow_create.html", **_ctx(
        page="workspaces", workspace=ws, project=proj, credentials=creds,
    ))


@dashboard_bp.route("/workflows/<workflow_id>/edit")
def workflow_edit(workflow_id):
    storage = current_app.config["STORAGE"]
    wf = storage.get_workflow(workflow_id)
    if not wf:
        return render_template("dashboard.html", **_ctx(page="dashboard"))
    proj = storage.get_project(wf["project_id"])
    ws = storage.get_workspace(wf["workspace_id"])
    creds = storage.get_credentials(wf["workspace_id"])

    import json
    source = wf.get("trigger", {}).get("source_app", "custom")
    test_payloads = {
        "servicenow": json.dumps({
            "event_type": wf.get("trigger", {}).get("event_type", "incident.created"),
            "number": "INC0010001",
            "short_description": "Test incident from AppScript Bridge",
            "priority": "3",
            "state": "1",
            "sys_id": "abc123def456"
        }, indent=2),
        "telegram": json.dumps({
            "message": {
                "message_id": 1,
                "from": {"id": 123456, "first_name": "Test", "username": "testuser"},
                "chat": {"id": 123456, "type": "private"},
                "date": 1234567890,
                "text": "/start Hello from AppScript Bridge"
            }
        }, indent=2),
        "custom": json.dumps({"test": True, "message": "Hello from AppScript Bridge"}, indent=2),
    }
    test_payload = test_payloads.get(source, test_payloads["custom"])

    return render_template("workflow_edit.html", **_ctx(
        page="workspaces", workflow=wf, project=proj, workspace=ws,
        credentials=creds, test_payload=test_payload,
    ))


@dashboard_bp.route("/credentials")
def credentials():
    return render_template("credentials.html", **_ctx(page="credentials"))


@dashboard_bp.route("/credentials/new/<app_type>")
def credential_create(app_type):
    schema = APP_CREDENTIAL_SCHEMAS.get(app_type)
    if not schema:
        return render_template("credentials.html", **_ctx(page="credentials"))
    return render_template("credential_create.html", **_ctx(
        page="credentials", app_type=app_type, schema=schema,
    ))


@dashboard_bp.route("/credentials/<credential_id>/manage")
def credential_manage(credential_id):
    storage = current_app.config["STORAGE"]
    cred = storage.get_credential(credential_id)
    if not cred:
        return render_template("credentials.html", **_ctx(page="credentials"))
    schema = APP_CREDENTIAL_SCHEMAS.get(cred.get("app_type", "custom"), APP_CREDENTIAL_SCHEMAS["custom"])
    return render_template("credential_manage.html", **_ctx(
        page="credentials", credential=cred, schema=schema,
    ))


@dashboard_bp.route("/events")
def events():
    return render_template("events.html", **_ctx(page="events"))


@dashboard_bp.route("/settings")
def settings():
    return render_template("settings.html", **_ctx(page="settings"))


@dashboard_bp.route("/guide")
def guide():
    return render_template("guide.html", **_ctx(page="guide"))
