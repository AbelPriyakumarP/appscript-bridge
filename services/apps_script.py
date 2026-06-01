import re
import time
import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request


class AppsScriptService:
    SCRIPT_API = "https://script.googleapis.com/v1/projects"
    DRIVE_API = "https://www.googleapis.com/drive/v3/files"

    def __init__(self, storage):
        self.storage = storage

    def _get_credentials(self):
        tokens = self.storage.get_google_tokens()
        if not tokens or "access_token" not in tokens:
            return None
        creds = Credentials(
            token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=tokens.get("client_id"),
            client_secret=tokens.get("client_secret"),
        )
        # if creds.expired and creds.refresh_token:
        #     creds.refresh(Request())
        #     tokens["access_token"] = creds.token
        #     self.storage.save_google_tokens(tokens)
        # return creds
        if creds.expired:
            if creds.refresh_token:
                try:
                    creds.refresh(Request())
                    tokens["access_token"] = creds.token
                    self.storage.save_google_tokens(tokens)
                except Exception:
                    return None # Refresh failed, token is dead
            else:
                return None # No refresh token exists, token is dead
                
        return creds


    def _headers(self, creds):
        return {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}

    # ── List all Apps Script projects via Drive API ──
    def list_scripts(self):
        creds = self._get_credentials()
        if not creds:
            return {"success": False, "error": "Google account not connected"}

        try:
            scripts = []
            page_token = None
            while True:
                params = {
                    "q": "mimeType='application/vnd.google-apps.script' and trashed=false",
                    "fields": "nextPageToken,files(id,name,modifiedTime,owners)",
                    "pageSize": 100,
                    "orderBy": "modifiedTime desc",
                }
                if page_token:
                    params["pageToken"] = page_token

                resp = requests.get(
                    self.DRIVE_API,
                    headers=self._headers(creds),
                    params=params,
                    timeout=15,
                )
                if resp.status_code != 200:
                    return {"success": False, "error": f"Drive API error: {resp.status_code} {resp.text}"}

                data = resp.json()
                for f in data.get("files", []):
                    scripts.append({
                        "scriptId": f["id"],
                        "name": f["name"],
                        "modifiedTime": f.get("modifiedTime", ""),
                    })

                page_token = data.get("nextPageToken")
                if not page_token:
                    break

            return {"success": True, "scripts": scripts}
        except requests.RequestException as e:
            return {"success": False, "error": str(e)}

    # ── Get functions from a specific Apps Script project ──
    def get_script_functions(self, script_id):
        creds = self._get_credentials()
        if not creds:
            return {"success": False, "error": "Google account not connected"}

        url = f"{self.SCRIPT_API}/{script_id}/content"
        try:
            resp = requests.get(url, headers=self._headers(creds), timeout=15)
            if resp.status_code != 200:
                return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text}"}

            data = resp.json()
            functions = []
            func_pattern = re.compile(r'function\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(')

            for file_entry in data.get("files", []):
                if file_entry.get("type") == "SERVER_JS":
                    source = file_entry.get("source", "")
                    filename = file_entry.get("name", "unknown")
                    for match in func_pattern.finditer(source):
                        fn_name = match.group(1)
                        functions.append({
                            "name": fn_name,
                            "file": filename,
                        })

            return {"success": True, "functions": functions, "scriptId": script_id}
        except requests.RequestException as e:
            return {"success": False, "error": str(e)}

    # ── Get project metadata ──
    def get_script_metadata(self, script_id):
        creds = self._get_credentials()
        if not creds:
            return {"success": False, "error": "Google account not connected"}

        url = f"{self.SCRIPT_API}/{script_id}"
        try:
            resp = requests.get(url, headers=self._headers(creds), timeout=15)
            if resp.status_code != 200:
                return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text}"}
            return {"success": True, "metadata": resp.json()}
        except requests.RequestException as e:
            return {"success": False, "error": str(e)}

# # ── Execute a function via Apps Script REST API ──
#     def run_script(self, script_id, function_name, parameters=None):
#         creds = self._get_credentials()
#         if not creds:
#             return {"success": False, "error": "Google account not connected"}

#         # CHANGE THIS LINE:
#         # url = f"{self.SCRIPT_API}/{script_id}:run" 
        
#         # TO THIS:
#         dep_id = 'AKfycbwdaySzLNj4iw8r5s1azTYpfBLfEBe2j-a4b7DOgMwPlDR9mKTRJA6z9As0p3pcRojg-Q'
#         url = f"https://script.googleapis.com/v1/scripts/{dep_id}:run"
        
#         body = {"function": function_name, "devMode": False}
#         if parameters:
#             body["parameters"] = parameters if isinstance(parameters, list) else [parameters]

#         start = time.time()

# ── Execute a function via Apps Script REST API ──
    def run_script(self, script_id, function_name, parameters=None):
        creds = self._get_credentials()
        
        # If _get_credentials returns None (because of the fix above), 
        # it gracefully stops here instead of throwing a 401!
        if not creds:
            return {"success": False, "error": "Google account not connected or token expired. Please log in again."}

        # USE THE SCRIPT ID (Project ID), NOT THE DEPLOYMENT ID
        url = f"https://script.googleapis.com/v1/scripts/{script_id}:run"
        
        body = {"function": function_name, "devMode": True}  # devMode=True to run latest code without redeploying
        if parameters:
            body["parameters"] = parameters if isinstance(parameters, list) else [parameters]

        start = time.time()
        # ... (rest of your code remains exactly the same)

        try:
            resp = requests.post(url, json=body, headers=self._headers(creds), timeout=30)
            elapsed_ms = int((time.time() - start) * 1000)

            if resp.status_code == 200:
                data = resp.json()
                if "error" in data:
                    err = data["error"]
                    return {
                        "success": False,
                        "error": err.get("message", str(err)),
                        "details": err.get("details", []),
                        "processing_time_ms": elapsed_ms,
                    }
                return {
                    "success": True,
                    "response": data.get("response", {}),
                    "processing_time_ms": elapsed_ms,
                }
            return {
                "success": False,
                "error": f"HTTP {resp.status_code}: {resp.text}",
                "processing_time_ms": elapsed_ms,
            }
        except requests.Timeout:
            return {"success": False, "error": "Request timed out", "processing_time_ms": 30000}
        except requests.RequestException as e:
            elapsed_ms = int((time.time() - start) * 1000)
            return {"success": False, "error": str(e), "processing_time_ms": elapsed_ms}

    # ── Fallback: call a deployed web app URL ──
    def call_web_app(self, web_app_url, payload=None):
        start = time.time()
        try:
            resp = requests.post(web_app_url, json=payload or {}, timeout=30)
            elapsed_ms = int((time.time() - start) * 1000)
            return {
                "success": resp.status_code == 200,
                "response": resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"text": resp.text},
                "status_code": resp.status_code,
                "processing_time_ms": elapsed_ms,
            }
        except requests.Timeout:
            return {"success": False, "error": "Request timed out", "processing_time_ms": 30000}
        except requests.RequestException as e:
            elapsed_ms = int((time.time() - start) * 1000)
            return {"success": False, "error": str(e), "processing_time_ms": elapsed_ms}
