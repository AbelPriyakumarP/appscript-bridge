import re

_EXPR = re.compile(r'\{\{([^}]+)\}\}')


def _get_nested(obj, path):
    """Resolve a dot-path like 'payload.incident.number' against obj.
    Leading 'payload.' prefix is stripped so users can write either form."""
    if path.startswith("payload."):
        path = path[8:]
    val = obj
    for part in path.split("."):
        if isinstance(val, dict):
            val = val.get(part)
        else:
            return None
    return val


class EventProcessor:
    def __init__(self, storage, apps_script_service):
        self.storage = storage
        self.script_service = apps_script_service

    # ── Credential validation ────────────────────────────────────────────────

    def validate_api_key(self, api_key):
        cred = self.storage.get_credential_by_api_key(api_key)
        if not cred:
            return None, "Invalid API key"
        if not cred["is_active"]:
            return None, "Credential is deactivated"
        return cred, None

    def validate_credential(self, credential_id):
        cred = self.storage.get_credential(credential_id)
        if not cred:
            return None, "Credential not found"
        if not cred["is_active"]:
            return None, "Credential is deactivated"
        return cred, None

    # ── Workflow matching ────────────────────────────────────────────────────

    def find_workflows(self, credential_id, event_type=None):
        """Return active workflows whose trigger matches credential + event_type.
        Matching is case-insensitive; 'custom' acts as a wildcard."""
        matching = []
        for wf in self.storage.get_workflows():
            if wf["status"] != "active":
                continue
            trigger = wf.get("trigger", {})
            if trigger.get("credential_id") != credential_id:
                continue
            wf_event = (trigger.get("event_type") or "").lower().strip()
            in_event  = (event_type or "").lower().strip()
            if wf_event and in_event and wf_event not in (in_event, "custom"):
                continue
            matching.append(wf)
        return matching

    # ── Filter evaluation ────────────────────────────────────────────────────

    def _passes_filter(self, filter_cfg, payload):
        """Return (passes: bool, reason: str).
        passes=True means the payload satisfies all filter conditions."""
        if not filter_cfg or not filter_cfg.get("enabled"):
            return True, ""

        conditions = filter_cfg.get("conditions") or []
        if not conditions:
            return True, ""

        logic   = (filter_cfg.get("logic") or "AND").upper()
        results = []

        for cond in conditions:
            field    = (cond.get("field") or "").strip()
            operator = (cond.get("operator") or "eq").strip()
            expected = str(cond.get("value") or "")
            actual   = _get_nested(payload, field) if field else None
            results.append(self._compare(actual, operator, expected))

        passed = any(results) if logic == "OR" else all(results)
        if not passed:
            reason = f"Filter ({logic}) blocked: " + "; ".join(
                f"{c.get('field')} {c.get('operator')} {c.get('value')}"
                for c in conditions
            )
            return False, reason
        return True, ""

    @staticmethod
    def _compare(actual, operator, expected):
        try:
            if operator in ("eq",  "=="):  return str(actual) == str(expected)
            if operator in ("ne",  "!="):  return str(actual) != str(expected)
            if operator in ("gt",  ">"):   return float(actual) > float(expected)
            if operator in ("lt",  "<"):   return float(actual) < float(expected)
            if operator in ("gte", ">="):  return float(actual) >= float(expected)
            if operator in ("lte", "<="):  return float(actual) <= float(expected)
            if operator == "contains":     return str(expected).lower() in str(actual or "").lower()
            if operator == "not_contains": return str(expected).lower() not in str(actual or "").lower()
            if operator == "exists":       return actual is not None
            if operator == "not_exists":   return actual is None
            if operator == "starts_with":  return str(actual or "").lower().startswith(str(expected).lower())
            if operator == "ends_with":    return str(actual or "").lower().endswith(str(expected).lower())
        except (TypeError, ValueError):
            return False
        return False

    # ── Parameter resolution ─────────────────────────────────────────────────

    @staticmethod
    def _resolve_params(mappings, payload):
        """Resolve a [{name, value}] mapping list against payload.
        Expressions like {{payload.field}} are substituted with live values.
        Returns a dict, or None if mappings is empty (→ pass full payload)."""
        if not mappings:
            return None

        def _sub(match):
            val = _get_nested(payload, match.group(1).strip())
            return str(val) if val is not None else ""

        result = {}
        for m in mappings:
            name = (m.get("name") or "").strip()
            if not name:
                continue
            raw_value = str(m.get("value") or "")
            result[name] = _EXPR.sub(_sub, raw_value)
        return result or None

    # ── Event processing ─────────────────────────────────────────────────────

    def process_event(self, credential, event_type, payload):
        workflows = self.find_workflows(credential["id"], event_type)

        if not workflows:
            log = self.storage.create_event_log({
                "credential_id": credential["id"],
                "source_app":    credential.get("app_type", "custom"),
                "event_type":    event_type or "unknown",
                "payload":       payload,
                "status":        "skipped",
                "error":         "No active workflows matched this credential + event type",
            })
            return {"processed": 0, "skipped": 1, "logs": [log]}

        results  = []
        skipped  = 0
        for wf in workflows:
            # ── 1. Evaluate filter ───────────────────────────────────────────
            passes, filter_reason = self._passes_filter(wf.get("filter"), payload)
            if not passes:
                log = self.storage.create_event_log({
                    "workflow_id":   wf["id"],
                    "credential_id": credential["id"],
                    "source_app":    credential.get("app_type", "custom"),
                    "event_type":    event_type or "unknown",
                    "payload":       payload,
                    "status":        "skipped",
                    "error":         filter_reason,
                })
                self.storage.update_workflow(wf["id"], {
                    "last_triggered": self.storage._now(),
                    "trigger_count":  wf.get("trigger_count", 0) + 1,
                })
                results.append(log)
                skipped += 1
                continue

            # ── 2. Resolve parameters ────────────────────────────────────────
            action      = wf.get("action", {})
            action_type = action.get("type", "apps_script_api")
            param_mappings = action.get("parameters") or []
            resolved = self._resolve_params(param_mappings, payload)
            # resolved is None  → pass full payload (backward-compatible)
            # resolved is dict  → pass the mapped object
            call_params = resolved if resolved is not None else payload

            # ── 3. Execute action ────────────────────────────────────────────
            if action_type == "apps_script_api":
                result = self.script_service.run_script(
                    action.get("script_id", ""),
                    action.get("function_name", ""),
                    parameters=call_params,
                )
            elif action_type == "web_app":
                result = self.script_service.call_web_app(
                    action.get("web_app_url", ""),
                    payload=call_params,
                )
            else:
                result = {"success": False, "error": f"Unknown action type: {action_type}"}

            log = self.storage.create_event_log({
                "workflow_id":        wf["id"],
                "credential_id":      credential["id"],
                "source_app":         credential.get("app_type", "custom"),
                "event_type":         event_type or "unknown",
                "payload":            payload,
                "status":             "success" if result.get("success") else "failed",
                "response":           result.get("response", {}),
                "error":              result.get("error", ""),
                "processing_time_ms": result.get("processing_time_ms", 0),
            })

            self.storage.update_workflow(wf["id"], {
                "last_triggered": self.storage._now(),
                "trigger_count":  wf.get("trigger_count", 0) + 1,
            })
            results.append(log)

        succeeded = sum(1 for r in results if r["status"] == "success")
        failed    = sum(1 for r in results if r["status"] == "failed")
        return {"processed": succeeded, "failed": failed, "skipped": skipped, "logs": results}

    # ── Telegram parser ──────────────────────────────────────────────────────

    @staticmethod
    def parse_telegram_event(update):
        """Map a Telegram Update object to (event_type, payload)."""
        if "message" in update:
            text = update["message"].get("text", "")
            return ("command" if text.startswith("/") else "message"), update
        if "edited_message" in update:
            return "edited_message", update
        if "callback_query" in update:
            return "callback_query", update
        if "inline_query" in update:
            return "inline_query", update
        return "message", update

    # ── ServiceNow parser ────────────────────────────────────────────────────

    @staticmethod
    def parse_servicenow_event(payload):
        """Extract a normalised event_type from a ServiceNow webhook payload."""
        raw = (
            payload.get("event_type")
            or payload.get("event")
            or payload.get("type")
        )
        if not raw:
            table  = (payload.get("table") or payload.get("tableName") or "").lower()
            action = (
                payload.get("sys_action")
                or payload.get("action")
                or payload.get("operation")
                or ""
            ).lower()
            action_map = {
                "insert": "created", "inserted": "created",
                "update": "updated", "updated":  "updated",
                "delete": "deleted", "deleted":  "deleted",
            }
            mapped = action_map.get(action, action)
            raw = f"{table}.{mapped}" if table and mapped else (f"{table}.changed" if table else None)

        return (raw or "custom").lower().strip(), payload
