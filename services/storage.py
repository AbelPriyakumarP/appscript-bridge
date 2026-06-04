import json
import os
import threading
from datetime import datetime, timezone

APP_CREDENTIAL_SCHEMAS = {
    "servicenow": {
        "label": "ServiceNow",
        "icon": "bi-gear-wide-connected",
        "color": "#81b5a1",
        "fields": [
            {"key": "instance_url", "label": "Instance URL", "type": "text", "placeholder": "https://dev12345.service-now.com", "required": True},
            {"key": "client_id", "label": "Client ID", "type": "text", "placeholder": "OAuth Client ID", "required": True},
            {"key": "client_secret", "label": "Client Secret", "type": "password", "placeholder": "OAuth Client Secret", "required": True},
            {"key": "username", "label": "Username", "type": "text", "placeholder": "admin", "required": False},
            {"key": "password", "label": "Password", "type": "password", "placeholder": "Password", "required": False},
        ],
        "webhook_events": [
            "incident.created", "incident.updated", "incident.resolved",
            "change_request.created", "change_request.approved",
            "problem.created", "custom",
        ],
    },
    "telegram": {
        "label": "Telegram",
        "icon": "bi-telegram",
        "color": "#0088cc",
        "fields": [
            {"key": "bot_token", "label": "Bot Token", "type": "password", "placeholder": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11", "required": True},
        ],
        "webhook_events": [
            "message", "edited_message", "callback_query",
            "inline_query", "command", "custom",
        ],
    },
    "datadog": {
        "label": "Datadog",
        "icon": "bi-activity",
        "color": "#632ca6",
        "fields": [
            {"key": "webhook_secret", "label": "Webhook Secret", "type": "password",
             "placeholder": "Secret set in Datadog Webhooks Integration", "required": False},
            {"key": "dd_site", "label": "Datadog Site", "type": "text",
             "placeholder": "datadoghq.com", "required": False},
        ],
        "webhook_events": [
            "metric_alert_triggered", "metric_alert_recovered",
            "monitor_alert", "monitor_recovered",
            "service_check.critical", "service_check.warning",
            "event.created", "custom",
        ],
    },
    "jira": {
        "label": "Jira",
        "icon": "bi-kanban-fill",
        "color": "#0052CC",
        "fields": [
            {"key": "jira_url", "label": "Jira Base URL", "type": "text",
             "placeholder": "https://yourorg.atlassian.net", "required": True},
            {"key": "webhook_secret", "label": "Webhook Secret Token", "type": "password",
             "placeholder": "Token set in Jira Webhooks settings", "required": False},
        ],
        "webhook_events": [
            "jira:issue_created", "jira:issue_updated", "jira:issue_deleted",
            "jira:worklog_updated", "sprint_started", "sprint_closed",
            "board_created", "comment_created", "custom",
        ],
    },
    "custom": {
        "label": "Custom / Generic",
        "icon": "bi-plug",
        "color": "#6366f1",
        "fields": [
            {"key": "base_url", "label": "Base URL", "type": "text", "placeholder": "https://api.example.com", "required": False},
            {"key": "auth_header", "label": "Auth Header Name", "type": "text", "placeholder": "Authorization", "required": False},
            {"key": "auth_value", "label": "Auth Header Value", "type": "password", "placeholder": "Bearer xxx", "required": False},
        ],
        "webhook_events": ["custom"],
    },
}


class JSONStorage:
    _lock = threading.Lock()

    def __init__(self, data_dir):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self._ensure_files()

    def _ensure_files(self):
        defaults = {
            "workspaces": [],
            "projects": [],
            "workflows": [],
            "credentials": [],
            "event_logs": [],
            "google_tokens": {},
        }
        for name, default in defaults.items():
            path = os.path.join(self.data_dir, f"{name}.json")
            if not os.path.exists(path):
                self._write_file(path, default)

    def _read_file(self, filename):
        path = os.path.join(self.data_dir, f"{filename}.json")
        with self._lock:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)

    def _write_file(self, path_or_name, data):
        if not path_or_name.endswith(".json"):
            path_or_name = os.path.join(self.data_dir, f"{path_or_name}.json")
        with self._lock:
            with open(path_or_name, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)

    def _now(self):
        return datetime.now(timezone.utc).isoformat()

    # --- Workspaces ---
    def get_workspaces(self):
        return self._read_file("workspaces")

    def get_workspace(self, workspace_id):
        return next((w for w in self.get_workspaces() if w["id"] == workspace_id), None)

    def create_workspace(self, data):
        workspaces = self.get_workspaces()
        workspace = {
            "id": f"ws_{os.urandom(8).hex()}",
            "name": data["name"],
            "description": data.get("description", ""),
            "created_at": self._now(),
            "updated_at": self._now(),
        }
        workspaces.append(workspace)
        self._write_file("workspaces", workspaces)
        return workspace

    def update_workspace(self, workspace_id, data):
        workspaces = self.get_workspaces()
        for w in workspaces:
            if w["id"] == workspace_id:
                w.update({k: v for k, v in data.items() if k not in ("id", "created_at")})
                w["updated_at"] = self._now()
                self._write_file("workspaces", workspaces)
                return w
        return None

    def delete_workspace(self, workspace_id):
        workspaces = [w for w in self.get_workspaces() if w["id"] != workspace_id]
        self._write_file("workspaces", workspaces)
        projects = [p for p in self.get_projects() if p["workspace_id"] != workspace_id]
        self._write_file("projects", projects)
        workflows = [wf for wf in self.get_workflows() if wf["workspace_id"] != workspace_id]
        self._write_file("workflows", workflows)
        creds = [c for c in self.get_credentials() if c["workspace_id"] != workspace_id]
        self._write_file("credentials", creds)

    # --- Projects ---
    def get_projects(self, workspace_id=None):
        projects = self._read_file("projects")
        if workspace_id:
            return [p for p in projects if p["workspace_id"] == workspace_id]
        return projects

    def get_project(self, project_id):
        return next((p for p in self.get_projects() if p["id"] == project_id), None)

    def create_project(self, data):
        projects = self.get_projects()
        project = {
            "id": f"proj_{os.urandom(8).hex()}",
            "workspace_id": data["workspace_id"],
            "name": data["name"],
            "description": data.get("description", ""),
            "created_at": self._now(),
            "updated_at": self._now(),
        }
        projects.append(project)
        self._write_file("projects", projects)
        return project

    def update_project(self, project_id, data):
        projects = self.get_projects()
        for p in projects:
            if p["id"] == project_id:
                p.update({k: v for k, v in data.items() if k not in ("id", "created_at", "workspace_id")})
                p["updated_at"] = self._now()
                self._write_file("projects", projects)
                return p
        return None

    def delete_project(self, project_id):
        projects = [p for p in self.get_projects() if p["id"] != project_id]
        self._write_file("projects", projects)
        workflows = [wf for wf in self.get_workflows() if wf["project_id"] != project_id]
        self._write_file("workflows", workflows)

    # --- Workflows ---
    def get_workflows(self, project_id=None, workspace_id=None):
        workflows = self._read_file("workflows")
        if project_id:
            return [wf for wf in workflows if wf["project_id"] == project_id]
        if workspace_id:
            return [wf for wf in workflows if wf["workspace_id"] == workspace_id]
        return workflows

    def get_workflow(self, workflow_id):
        return next((wf for wf in self.get_workflows() if wf["id"] == workflow_id), None)

    def create_workflow(self, data):
        workflows = self.get_workflows()
        workflow = {
            "id": f"wf_{os.urandom(8).hex()}",
            "project_id": data["project_id"],
            "workspace_id": data["workspace_id"],
            "name": data["name"],
            "description": data.get("description", ""),
            "status": "inactive",
            "trigger": {
                "type": "webhook",
                "source_app": data.get("source_app", ""),
                "credential_id": data.get("credential_id", ""),
                "event_type": data.get("event_type", ""),
            },
            "action": {
                "type": data.get("action_type", "apps_script_api"),
                "script_id": data.get("script_id", ""),
                "script_name": data.get("script_name", ""),
                "function_name": data.get("function_name", ""),
                "web_app_url": data.get("web_app_url", ""),
            },
            "created_at": self._now(),
            "updated_at": self._now(),
            "last_triggered": None,
            "trigger_count": 0,
        }
        workflows.append(workflow)
        self._write_file("workflows", workflows)
        return workflow

    def update_workflow(self, workflow_id, data):
        workflows = self.get_workflows()
        for wf in workflows:
            if wf["id"] == workflow_id:
                for key in ("name", "description", "status", "last_triggered", "trigger_count"):
                    if key in data:
                        wf[key] = data[key]
                if "trigger" in data:
                    wf["trigger"].update(data["trigger"])
                if "action" in data:
                    wf["action"].update(data["action"])
                wf["updated_at"] = self._now()
                self._write_file("workflows", workflows)
                return wf
        return None

    def delete_workflow(self, workflow_id):
        workflows = [wf for wf in self.get_workflows() if wf["id"] != workflow_id]
        self._write_file("workflows", workflows)

    # --- Credentials (app-specific) ---
    def get_credentials(self, workspace_id=None):
        creds = self._read_file("credentials")
        if workspace_id:
            return [c for c in creds if c["workspace_id"] == workspace_id]
        return creds

    def get_credential(self, credential_id):
        return next((c for c in self.get_credentials() if c["id"] == credential_id), None)

    def get_credential_by_api_key(self, api_key):
        return next((c for c in self.get_credentials() if c.get("api_key") == api_key), None)

    def create_credential(self, data):
        creds = self.get_credentials()
        credential = {
            "id": f"cred_{os.urandom(8).hex()}",
            "workspace_id": data["workspace_id"],
            "name": data["name"],
            "app_type": data.get("app_type", "custom"),
            "config": data.get("config", {}),
            "api_key": f"asb_{os.urandom(16).hex()}",
            "api_secret": os.urandom(24).hex(),
            "is_active": True,
            "webhook_registered": False,
            "created_at": self._now(),
            "updated_at": self._now(),
        }
        creds.append(credential)
        self._write_file("credentials", creds)
        return credential

    def update_credential(self, credential_id, data):
        creds = self.get_credentials()
        for c in creds:
            if c["id"] == credential_id:
                for key in ("name", "is_active", "config", "webhook_registered"):
                    if key in data:
                        c[key] = data[key]
                c["updated_at"] = self._now()
                self._write_file("credentials", creds)
                return c
        return None

    def delete_credential(self, credential_id):
        creds = [c for c in self.get_credentials() if c["id"] != credential_id]
        self._write_file("credentials", creds)

    # --- Event Logs ---
    def get_event_logs(self, workflow_id=None, limit=50):
        logs = self._read_file("event_logs")
        if workflow_id:
            logs = [l for l in logs if l["workflow_id"] == workflow_id]
        logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return logs[:limit]

    def create_event_log(self, data):
        logs = self._read_file("event_logs")
        log = {
            "id": f"evt_{os.urandom(8).hex()}",
            "workflow_id": data.get("workflow_id", ""),
            "credential_id": data.get("credential_id", ""),
            "source_app": data.get("source_app", ""),
            "event_type": data.get("event_type", ""),
            "payload": data.get("payload", {}),
            "status": data.get("status", "pending"),
            "response": data.get("response", {}),
            "error": data.get("error", ""),
            "timestamp": self._now(),
            "processing_time_ms": data.get("processing_time_ms", 0),
        }
        logs.append(log)
        if len(logs) > 1000:
            logs = logs[-1000:]
        self._write_file("event_logs", logs)
        return log

    # --- Google Tokens ---
    def get_google_tokens(self):
        return self._read_file("google_tokens")

    def save_google_tokens(self, tokens):
        self._write_file("google_tokens", tokens)
