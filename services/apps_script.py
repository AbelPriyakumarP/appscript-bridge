import re
import time
import requests
from datetime import datetime
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request


class AppsScriptService:
    # Apps Script REST API base (project management)
    SCRIPT_API = "https://script.googleapis.com/v1/projects"
    # Apps Script Execution API
    EXECUTION_API = "https://script.googleapis.com/v1/scripts"
    DRIVE_API = "https://www.googleapis.com/drive/v3/files"

    def __init__(self, storage):
        self.storage = storage

    def _get_credentials(self):
        """
        Load stored OAuth tokens, refresh if expired, return a valid Credentials
        object — or None if the user needs to re-authenticate.
        """
        tokens = self.storage.get_google_tokens()
        if not tokens or not tokens.get("access_token"):
            return None

        # Parse stored expiry (saved by auth.py since the fix).
        # google-auth Credentials.expiry must be a naive UTC datetime — do NOT
        # attach tzinfo or the expired property will raise TypeError.
        expiry = None
        if tokens.get("expiry"):
            try:
                expiry = datetime.fromisoformat(tokens["expiry"])
                if expiry.tzinfo is not None:
                    expiry = expiry.replace(tzinfo=None)  # strip tz if somehow present
            except (ValueError, TypeError):
                pass

        # If no expiry was ever stored (tokens from before the fix), force a
        # refresh so we get a fresh token with a known expiry going forward.
        if expiry is None and tokens.get("refresh_token"):
            expiry = datetime(2000, 1, 1)  # naive, definitely expired

        creds = Credentials(
            token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token"),
            token_uri=tokens.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=tokens.get("client_id"),
            client_secret=tokens.get("client_secret"),
            scopes=tokens.get("scopes", []),
            expiry=expiry,
        )

        if creds.expired:
            if not creds.refresh_token:
                return None  # No way to refresh — user must re-auth
            try:
                creds.refresh(Request())
                # Persist the new token and its expiry
                tokens["access_token"] = creds.token
                if creds.expiry:
                    tokens["expiry"] = creds.expiry.isoformat()
                self.storage.save_google_tokens(tokens)
            except Exception:
                return None  # Refresh failed — user must re-auth

        return creds

    def _headers(self, creds):
        return {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}

    # ── List all Apps Script projects via Drive API ──────────────────────────
    def list_scripts(self):
        creds = self._get_credentials()
        if not creds:
            return {"success": False, "error": "Google account not connected. Please reconnect in Settings."}

        try:
            scripts, page_token = [], None
            while True:
                params = {
                    "q": "mimeType='application/vnd.google-apps.script' and trashed=false",
                    "fields": "nextPageToken,files(id,name,modifiedTime)",
                    "pageSize": 100,
                    "orderBy": "modifiedTime desc",
                }
                if page_token:
                    params["pageToken"] = page_token

                resp = requests.get(self.DRIVE_API, headers=self._headers(creds),
                                    params=params, timeout=15)
                if resp.status_code == 401:
                    return {"success": False, "error": "Google token expired. Please reconnect in Settings."}
                if resp.status_code != 200:
                    return {"success": False, "error": f"Drive API error {resp.status_code}: {resp.text[:200]}"}

                data = resp.json()
                for f in data.get("files", []):
                    scripts.append({
                        "scriptId":     f["id"],
                        "name":         f["name"],
                        "modifiedTime": f.get("modifiedTime", ""),
                    })

                page_token = data.get("nextPageToken")
                if not page_token:
                    break

            return {"success": True, "scripts": scripts}
        except requests.RequestException as e:
            return {"success": False, "error": str(e)}

    # ── Extract functions from script source ─────────────────────────────────
    def get_script_functions(self, script_id):
        creds = self._get_credentials()
        if not creds:
            return {"success": False, "error": "Google account not connected."}

        url = f"{self.SCRIPT_API}/{script_id}/content"
        try:
            resp = requests.get(url, headers=self._headers(creds), timeout=15)
            if resp.status_code == 401:
                return {"success": False, "error": "Google token expired. Reconnect in Settings."}
            if resp.status_code != 200:
                return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}

            func_pattern = re.compile(r'^function\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(', re.MULTILINE)
            functions = []
            for f in resp.json().get("files", []):
                if f.get("type") == "SERVER_JS":
                    for m in func_pattern.finditer(f.get("source", "")):
                        functions.append({"name": m.group(1), "file": f.get("name", "unknown")})

            return {"success": True, "functions": functions, "scriptId": script_id}
        except requests.RequestException as e:
            return {"success": False, "error": str(e)}

    # ── Get project metadata ─────────────────────────────────────────────────
    def get_script_metadata(self, script_id):
        creds = self._get_credentials()
        if not creds:
            return {"success": False, "error": "Google account not connected."}
        url = f"{self.SCRIPT_API}/{script_id}"
        try:
            resp = requests.get(url, headers=self._headers(creds), timeout=15)
            if resp.status_code != 200:
                return {"success": False, "error": f"HTTP {resp.status_code}"}
            return {"success": True, "metadata": resp.json()}
        except requests.RequestException as e:
            return {"success": False, "error": str(e)}

    # ── Execute a function via Apps Script Execution API ─────────────────────
    def run_script(self, script_id, function_name, parameters=None):
        """
        Call a Google Apps Script function using the Execution API.

        Requirements on the script side:
          1. Script must be linked to a GCP project that has the Apps Script API enabled.
          2. The calling Google account must have at least Viewer access to the script.
          3. devMode=True runs the latest saved code without needing a new deployment.

        Parameters passed to the Apps Script function:
          - First (and only) argument is the full event payload as a JSON object.

        In your .gs file, receive it like:
            function handleEvent(payload) {
              Logger.log(payload.event_type);
            }
        """
        if not script_id:
            return {"success": False, "error": "No Apps Script project selected in workflow action."}
        if not function_name:
            return {"success": False, "error": "No function name selected in workflow action."}

        creds = self._get_credentials()
        if not creds:
            return {"success": False, "error": "Google account not connected or token expired. Reconnect in Settings."}

        # Execution API endpoint  — uses scriptId (Project ID), NOT a deployment ID.
        url = f"{self.EXECUTION_API}/{script_id}:run"

        body = {
            "function": function_name,
            "devMode":  True,   # run latest saved code; no new deployment needed
        }
        if parameters is not None:
            body["parameters"] = parameters if isinstance(parameters, list) else [parameters]

        start = time.time()
        try:
            resp = requests.post(url, json=body, headers=self._headers(creds), timeout=30)
            elapsed_ms = int((time.time() - start) * 1000)

            if resp.status_code == 401:
                return {"success": False, "error": "Google token expired mid-request. Reconnect in Settings.",
                        "processing_time_ms": elapsed_ms}

            if resp.status_code == 403:
                return {
                    "success": False,
                    "error": (
                        "Permission denied (403). Ensure: "
                        "1) Apps Script API is enabled in your GCP project, "
                        "2) the script is linked to that GCP project, "
                        "3) you have at least Viewer access to the script."
                    ),
                    "processing_time_ms": elapsed_ms,
                }

            if resp.status_code != 200:
                return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:300]}",
                        "processing_time_ms": elapsed_ms}

            data = resp.json()
            if "error" in data:
                err = data["error"]
                msg = err.get("message", str(err))
                details = err.get("details", [])
                # Surface the actual script error if present
                for d in details:
                    if d.get("@type", "").endswith("ExecutionError"):
                        msg = d.get("errorMessage", msg)
                        break
                return {"success": False, "error": msg, "details": details,
                        "processing_time_ms": elapsed_ms}

            return {
                "success": True,
                "response": data.get("response", {}),
                "processing_time_ms": elapsed_ms,
            }

        except requests.Timeout:
            return {"success": False, "error": "Apps Script execution timed out (30s). "
                    "Check if your function runs too long or has an infinite loop.",
                    "processing_time_ms": 30000}
        except requests.RequestException as e:
            return {"success": False, "error": str(e),
                    "processing_time_ms": int((time.time() - start) * 1000)}

    # ── Fallback: POST to a deployed Web App URL ─────────────────────────────
    def call_web_app(self, web_app_url, payload=None):
        """
        POST the event payload to a Google Apps Script Web App deployment URL.
        The doPost(e) function in the script receives the payload in e.postData.contents.
        """
        if not web_app_url:
            return {"success": False, "error": "No Web App URL configured in workflow action."}

        start = time.time()
        try:
            resp = requests.post(web_app_url, json=payload or {}, timeout=30,
                                 allow_redirects=True)
            elapsed_ms = int((time.time() - start) * 1000)
            try:
                body = resp.json()
            except Exception:
                body = {"text": resp.text[:500]}
            return {
                "success": resp.status_code == 200,
                "response": body,
                "status_code": resp.status_code,
                "processing_time_ms": elapsed_ms,
            }
        except requests.Timeout:
            return {"success": False, "error": "Web App request timed out (30s).",
                    "processing_time_ms": 30000}
        except requests.RequestException as e:
            return {"success": False, "error": str(e),
                    "processing_time_ms": int((time.time() - start) * 1000)}
