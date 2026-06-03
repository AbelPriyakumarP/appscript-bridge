from flask import Blueprint, request, jsonify, current_app
from services.storage import APP_CREDENTIAL_SCHEMAS

api_bp = Blueprint("api", __name__, url_prefix="/api")


def _storage():
    return current_app.config["STORAGE"]


# ── Workspaces ──

@api_bp.route("/workspaces", methods=["GET"])
def list_workspaces():
    return jsonify(_storage().get_workspaces())

@api_bp.route("/workspaces", methods=["POST"])
def create_workspace():
    data = request.json
    if not data or not data.get("name"):
        return jsonify({"error": "Name is required"}), 400
    return jsonify(_storage().create_workspace(data)), 201

@api_bp.route("/workspaces/<workspace_id>", methods=["GET"])
def get_workspace(workspace_id):
    ws = _storage().get_workspace(workspace_id)
    if not ws:
        return jsonify({"error": "Workspace not found"}), 404
    return jsonify(ws)

@api_bp.route("/workspaces/<workspace_id>", methods=["PUT"])
def update_workspace(workspace_id):
    ws = _storage().update_workspace(workspace_id, request.json)
    if not ws:
        return jsonify({"error": "Workspace not found"}), 404
    return jsonify(ws)

@api_bp.route("/workspaces/<workspace_id>", methods=["DELETE"])
def delete_workspace(workspace_id):
    _storage().delete_workspace(workspace_id)
    return jsonify({"success": True})


# ── Projects ──

@api_bp.route("/workspaces/<workspace_id>/projects", methods=["GET"])
def list_projects(workspace_id):
    return jsonify(_storage().get_projects(workspace_id))

@api_bp.route("/projects", methods=["POST"])
def create_project():
    data = request.json
    if not data or not data.get("name") or not data.get("workspace_id"):
        return jsonify({"error": "Name and workspace_id are required"}), 400
    return jsonify(_storage().create_project(data)), 201

@api_bp.route("/projects/<project_id>", methods=["GET"])
def get_project(project_id):
    proj = _storage().get_project(project_id)
    if not proj:
        return jsonify({"error": "Project not found"}), 404
    return jsonify(proj)

@api_bp.route("/projects/<project_id>", methods=["PUT"])
def update_project(project_id):
    proj = _storage().update_project(project_id, request.json)
    if not proj:
        return jsonify({"error": "Project not found"}), 404
    return jsonify(proj)

@api_bp.route("/projects/<project_id>", methods=["DELETE"])
def delete_project(project_id):
    _storage().delete_project(project_id)
    return jsonify({"success": True})


# ── Workflows ──

@api_bp.route("/projects/<project_id>/workflows", methods=["GET"])
def list_workflows(project_id):
    return jsonify(_storage().get_workflows(project_id=project_id))

@api_bp.route("/workspaces/<workspace_id>/workflows", methods=["GET"])
def list_workspace_workflows(workspace_id):
    return jsonify(_storage().get_workflows(workspace_id=workspace_id))

@api_bp.route("/workflows", methods=["POST"])
def create_workflow():
    data = request.json
    if not data or not data.get("name") or not data.get("project_id"):
        return jsonify({"error": "Name and project_id are required"}), 400
    return jsonify(_storage().create_workflow(data)), 201

@api_bp.route("/workflows/<workflow_id>", methods=["GET"])
def get_workflow(workflow_id):
    wf = _storage().get_workflow(workflow_id)
    if not wf:
        return jsonify({"error": "Workflow not found"}), 404
    return jsonify(wf)

@api_bp.route("/workflows/<workflow_id>", methods=["PUT"])
def update_workflow(workflow_id):
    wf = _storage().update_workflow(workflow_id, request.json)
    if not wf:
        return jsonify({"error": "Workflow not found"}), 404
    return jsonify(wf)

@api_bp.route("/workflows/<workflow_id>", methods=["DELETE"])
def delete_workflow(workflow_id):
    _storage().delete_workflow(workflow_id)
    return jsonify({"success": True})

@api_bp.route("/workflows/<workflow_id>/toggle", methods=["POST"])
def toggle_workflow(workflow_id):
    wf = _storage().get_workflow(workflow_id)
    if not wf:
        return jsonify({"error": "Workflow not found"}), 404
    new_status = "inactive" if wf["status"] == "active" else "active"
    wf = _storage().update_workflow(workflow_id, {"status": new_status})
    return jsonify(wf)


# ── Credentials ──

@api_bp.route("/credential-schemas", methods=["GET"])
def get_credential_schemas():
    return jsonify(APP_CREDENTIAL_SCHEMAS)

@api_bp.route("/workspaces/<workspace_id>/credentials", methods=["GET"])
def list_credentials(workspace_id):
    return jsonify(_storage().get_credentials(workspace_id))

@api_bp.route("/credentials", methods=["GET"])
def list_all_credentials():
    return jsonify(_storage().get_credentials())

@api_bp.route("/credentials", methods=["POST"])
def create_credential():
    data = request.json
    if not data or not data.get("name") or not data.get("workspace_id"):
        return jsonify({"error": "Name and workspace_id are required"}), 400
    return jsonify(_storage().create_credential(data)), 201

@api_bp.route("/credentials/<credential_id>", methods=["GET"])
def get_credential(credential_id):
    cred = _storage().get_credential(credential_id)
    if not cred:
        return jsonify({"error": "Credential not found"}), 404
    return jsonify(cred)

@api_bp.route("/credentials/<credential_id>", methods=["PUT"])
def update_credential(credential_id):
    cred = _storage().update_credential(credential_id, request.json)
    if not cred:
        return jsonify({"error": "Credential not found"}), 404
    return jsonify(cred)

@api_bp.route("/credentials/<credential_id>", methods=["DELETE"])
def delete_credential(credential_id):
    _storage().delete_credential(credential_id)
    return jsonify({"success": True})


# ── Apps Script: List scripts and functions ──

@api_bp.route("/scripts", methods=["GET"])
def list_scripts():
    script_svc = current_app.config["APPS_SCRIPT"]
    result = script_svc.list_scripts()
    if not result["success"]:
        return jsonify(result), 400
    return jsonify(result)

@api_bp.route("/scripts/<script_id>/functions", methods=["GET"])
def get_script_functions(script_id):
    script_svc = current_app.config["APPS_SCRIPT"]
    result = script_svc.get_script_functions(script_id)
    if not result["success"]:
        return jsonify(result), 400
    return jsonify(result)

@api_bp.route("/scripts/<script_id>/metadata", methods=["GET"])
def get_script_metadata(script_id):
    script_svc = current_app.config["APPS_SCRIPT"]
    result = script_svc.get_script_metadata(script_id)
    if not result["success"]:
        return jsonify(result), 400
    return jsonify(result)


# ── Event Logs ──

@api_bp.route("/events", methods=["GET"])
def list_events():
    workflow_id = request.args.get("workflow_id")
    limit       = int(request.args.get("limit", 50))
    events      = _storage().get_event_logs(workflow_id=workflow_id, limit=limit)

    # Enrich each event with the workflow name so the UI can show it directly.
    wf_cache = {}
    for evt in events:
        wid = evt.get("workflow_id")
        if wid and wid not in wf_cache:
            wf = _storage().get_workflow(wid)
            wf_cache[wid] = {"name": wf["name"], "id": wid} if wf else None
        evt["workflow_info"] = wf_cache.get(wid) if wid else None

    return jsonify(events)


# ── Webhook connectivity test ──

@api_bp.route("/test-webhook", methods=["POST"])
def test_webhook_connectivity():
    """Quick echo endpoint used from the Help panel / settings to verify connectivity."""
    return jsonify({
        "success": True,
        "echo":    request.json,
        "message": "AppScript Bridge webhook endpoint is reachable",
    })


# ── Dashboard Stats ──

@api_bp.route("/stats", methods=["GET"])
def get_stats():
    storage = _storage()
    workspaces = storage.get_workspaces()
    projects = storage.get_projects()
    workflows = storage.get_workflows()
    events = storage.get_event_logs(limit=1000)

    active_wf = sum(1 for wf in workflows if wf["status"] == "active")
    success_events = sum(1 for e in events if e["status"] == "success")
    failed_events = sum(1 for e in events if e["status"] == "failed")

    return jsonify({
        "workspaces": len(workspaces),
        "projects": len(projects),
        "workflows": {"total": len(workflows), "active": active_wf, "inactive": len(workflows) - active_wf},
        "events": {"total": len(events), "success": success_events, "failed": failed_events},
    })
