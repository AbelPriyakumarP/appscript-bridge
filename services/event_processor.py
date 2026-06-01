import hmac
import hashlib


class EventProcessor:
    def __init__(self, storage, apps_script_service):
        self.storage = storage
        self.script_service = apps_script_service

    def validate_api_key(self, api_key):
        credential = self.storage.get_credential_by_api_key(api_key)
        if not credential:
            return None, "Invalid API key"
        if not credential["is_active"]:
            return None, "Credential is deactivated"
        return credential, None

    def validate_credential(self, credential_id):
        credential = self.storage.get_credential(credential_id)
        if not credential:
            return None, "Credential not found"
        if not credential["is_active"]:
            return None, "Credential is deactivated"
        return credential, None

    def find_workflows(self, credential_id, event_type=None):
        all_workflows = self.storage.get_workflows()
        matching = []
        for wf in all_workflows:
            if wf["status"] != "active":
                continue
            trigger = wf.get("trigger", {})
            if trigger.get("credential_id") != credential_id:
                continue
            if event_type and trigger.get("event_type") and trigger["event_type"] != event_type:
                continue
            matching.append(wf)
        return matching

    def process_event(self, credential, event_type, payload):
        workflows = self.find_workflows(credential["id"], event_type)
        if not workflows:
            log = self.storage.create_event_log({
                "credential_id": credential["id"],
                "source_app": credential.get("app_type", "custom"),
                "event_type": event_type or "unknown",
                "payload": payload,
                "status": "skipped",
                "error": "No active workflows matched",
            })
            return {"processed": 0, "skipped": 1, "logs": [log]}

        results = []
        for wf in workflows:
            action = wf.get("action", {})
            action_type = action.get("type", "apps_script_api")

            if action_type == "apps_script_api":
                result = self.script_service.run_script(
                    action["script_id"],
                    action["function_name"],
                    parameters=payload,
                )
            elif action_type == "web_app":
                result = self.script_service.call_web_app(
                    action["web_app_url"],
                    payload=payload,
                )
            else:
                result = {"success": False, "error": f"Unknown action type: {action_type}"}

            log = self.storage.create_event_log({
                "workflow_id": wf["id"],
                "credential_id": credential["id"],
                "source_app": credential.get("app_type", "custom"),
                "event_type": event_type or "unknown",
                "payload": payload,
                "status": "success" if result.get("success") else "failed",
                "response": result.get("response", {}),
                "error": result.get("error", ""),
                "processing_time_ms": result.get("processing_time_ms", 0),
            })

            self.storage.update_workflow(wf["id"], {
                "last_triggered": self.storage._now(),
                "trigger_count": wf.get("trigger_count", 0) + 1,
            })

            results.append(log)

        succeeded = sum(1 for r in results if r["status"] == "success")
        failed = sum(1 for r in results if r["status"] == "failed")
        return {"processed": succeeded, "failed": failed, "logs": results}

    # ── Telegram-specific: extract event type from update ──
    @staticmethod
    def parse_telegram_event(update):
        if "message" in update:
            msg = update["message"]
            text = msg.get("text", "")
            if text.startswith("/"):
                return "command", update
            return "message", update
        if "callback_query" in update:
            return "callback_query", update
        if "edited_message" in update:
            return "edited_message", update
        if "inline_query" in update:
            return "inline_query", update
        return "unknown", update

    # ── ServiceNow-specific: extract event type from payload ──
    @staticmethod
    def parse_servicenow_event(payload):
        event_type = (
            payload.get("event_type")
            or payload.get("sys_action")
            or payload.get("type")
            or "custom"
        )
        return event_type, payload
