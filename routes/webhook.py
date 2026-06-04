import requests
from flask import Blueprint, request, jsonify, current_app

webhook_bp = Blueprint("webhook", __name__, url_prefix="/webhook")


def _processor():
    return current_app.config["EVENT_PROCESSOR"]


# ── Generic webhook (any credential with X-API-Key) ──────────────────────────

@webhook_bp.route("/trigger", methods=["POST"])
def trigger():
    api_key = (
        request.headers.get("X-API-Key")
        or request.args.get("api_key")
        or (request.json or {}).get("api_key")
    )
    if not api_key:
        return jsonify({
            "error": "Missing API key.",
            "hint":  "Send via X-API-Key header, ?api_key= query param, or body field.",
        }), 401

    event_type = (
        request.headers.get("X-Event-Type")
        or (request.json or {}).get("event_type")
        or request.args.get("event_type")
    )

    credential, err = _processor().validate_api_key(api_key)
    if err:
        return jsonify({"error": err}), 401

    payload = dict(request.json or {})
    payload.pop("api_key",    None)
    payload.pop("event_type", None)

    result      = _processor().process_event(credential, event_type, payload)
    status_code = 200 if result.get("processed", 0) > 0 else 202
    return jsonify(result), status_code


# ── Telegram webhook ──────────────────────────────────────────────────────────
# Telegram sends updates directly here — identified by credential_id in the URL.

@webhook_bp.route("/telegram/<credential_id>", methods=["POST"])
def telegram_webhook(credential_id):
    credential, err = _processor().validate_credential(credential_id)
    if err:
        # Always return 200 to Telegram so it doesn't keep retrying.
        return jsonify({"ok": True, "warning": err}), 200

    if credential.get("app_type") != "telegram":
        return jsonify({"ok": True, "warning": "Not a Telegram credential"}), 200

    update     = request.json or {}
    event_type, payload = _processor().parse_telegram_event(update)
    _processor().process_event(credential, event_type, payload)

    # Telegram requires HTTP 200 with {"ok": true} — always.
    return jsonify({"ok": True}), 200


# ── ServiceNow webhook ────────────────────────────────────────────────────────

@webhook_bp.route("/servicenow/<credential_id>", methods=["POST"])
def servicenow_webhook(credential_id):
    credential, err = _processor().validate_credential(credential_id)
    if err:
        return jsonify({"error": err}), 404

    if credential.get("app_type") != "servicenow":
        return jsonify({"error": "Not a ServiceNow credential"}), 400

    payload    = dict(request.json or {})
    event_type, payload = _processor().parse_servicenow_event(payload)
    result     = _processor().process_event(credential, event_type, payload)

    status_code = 200 if result.get("processed", 0) > 0 else 202
    return jsonify(result), status_code


# ── Telegram: register webhook with Telegram API ─────────────────────────────

@webhook_bp.route("/telegram/<credential_id>/register", methods=["POST"])
def register_telegram_webhook(credential_id):
    storage    = current_app.config["STORAGE"]
    credential = storage.get_credential(credential_id)
    if not credential or credential.get("app_type") != "telegram":
        return jsonify({"error": "Telegram credential not found"}), 404

    bot_token = credential.get("config", {}).get("bot_token", "").strip()
    if not bot_token:
        return jsonify({"error": "Bot token not configured in credential"}), 400

    base_url    = current_app.config["BASE_URL"]
    webhook_url = f"{base_url}/webhook/telegram/{credential_id}"

    try:
        # First delete any existing webhook, then set the new one.
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/deleteWebhook",
            timeout=10,
        )
        resp   = requests.post(
            f"https://api.telegram.org/bot{bot_token}/setWebhook",
            json={"url": webhook_url, "allowed_updates": [
                "message", "edited_message", "callback_query",
                "inline_query", "channel_post",
            ]},
            timeout=10,
        )
        result = resp.json()
        if result.get("ok"):
            storage.update_credential(credential_id, {"webhook_registered": True})
            return jsonify({"success": True, "webhook_url": webhook_url,
                            "telegram_response": result})
        return jsonify({
            "success": False,
            "error":   result.get("description", "Unknown Telegram error"),
            "telegram_response": result,
        }), 400
    except requests.RequestException as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ── Telegram: get webhook info ────────────────────────────────────────────────

@webhook_bp.route("/telegram/<credential_id>/info", methods=["GET"])
def telegram_webhook_info(credential_id):
    storage    = current_app.config["STORAGE"]
    credential = storage.get_credential(credential_id)
    if not credential or credential.get("app_type") != "telegram":
        return jsonify({"error": "Telegram credential not found"}), 404

    bot_token = credential.get("config", {}).get("bot_token", "").strip()
    if not bot_token:
        return jsonify({"error": "Bot token not configured"}), 400

    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{bot_token}/getWebhookInfo",
            timeout=10,
        )
        data = resp.json()
        # Add a human-readable status field
        data["_registered"] = bool(data.get("result", {}).get("url"))
        return jsonify(data)
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 500


# ── Telegram: send a message via the bot (for testing) ───────────────────────

@webhook_bp.route("/telegram/<credential_id>/send", methods=["POST"])
def telegram_send_message(credential_id):
    """
    POST {"chat_id": "...", "text": "..."} to send a test message via the bot.
    Useful for verifying the bot token works end-to-end.
    """
    storage    = current_app.config["STORAGE"]
    credential = storage.get_credential(credential_id)
    if not credential or credential.get("app_type") != "telegram":
        return jsonify({"error": "Telegram credential not found"}), 404

    bot_token = credential.get("config", {}).get("bot_token", "").strip()
    body      = request.json or {}
    chat_id   = body.get("chat_id")
    text      = body.get("text", "Test message from AppScript Bridge 🚀")

    if not chat_id:
        return jsonify({"error": "chat_id is required"}), 400

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        return jsonify(resp.json())
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 500


# ── Datadog webhook ───────────────────────────────────────────────────────────
# Setup: Datadog → Integrations → Webhooks → Add Webhook
# URL: BASE_URL/webhook/datadog/<credential_id>
# Payload template (custom JSON): {"alert_type":"$ALERT_TYPE","alert_transition":"$ALERT_TRANSITION",
#   "event_title":"$EVENT_TITLE","metric":"$METRIC","host":"$HOSTNAME","tags":"$TAGS",
#   "org_name":"$ORG_NAME","url":"$URL","id":"$ID","priority":"$PRIORITY"}

@webhook_bp.route("/datadog/<credential_id>", methods=["POST"])
def datadog_webhook(credential_id):
    credential, err = _processor().validate_credential(credential_id)
    if err:
        return jsonify({"error": err}), 404

    if credential.get("app_type") != "datadog":
        return jsonify({"error": "Not a Datadog credential"}), 400

    # Validate optional shared secret
    secret = credential.get("config", {}).get("webhook_secret", "")
    if secret:
        sent = (request.headers.get("X-Datadog-Webhook-Secret")
                or request.headers.get("X-Webhook-Secret", ""))
        if sent != secret:
            return jsonify({"error": "Invalid webhook secret"}), 401

    payload = dict(request.json or {})

    # Derive event_type from Datadog's alert_type + alert_transition fields
    alert_type       = (payload.get("alert_type") or "").lower().replace(" ", "_")
    alert_transition = (payload.get("alert_transition") or "").lower()

    if alert_type and alert_transition:
        event_type = f"{alert_type}_{alert_transition}"
    elif alert_type:
        event_type = f"monitor_{alert_type}"
    else:
        event_type = (
            payload.pop("event_type", None)
            or request.headers.get("X-Event-Type")
            or "monitor_alert"
        )

    result      = _processor().process_event(credential, event_type, payload)
    status_code = 200 if result.get("processed", 0) > 0 else 202
    return jsonify(result), status_code


@webhook_bp.route("/datadog/<credential_id>/test", methods=["GET", "POST"])
def datadog_test(credential_id):
    """Returns connectivity status — paste this URL into Datadog Webhook test."""
    storage    = current_app.config["STORAGE"]
    credential = storage.get_credential(credential_id)
    if not credential or credential.get("app_type") != "datadog":
        return jsonify({"error": "Datadog credential not found"}), 404
    return jsonify({
        "success":       True,
        "credential_id": credential_id,
        "name":          credential.get("name"),
        "message":       "AppScript Bridge Datadog connection verified",
        "webhook_url":   f"{current_app.config['BASE_URL']}/webhook/datadog/{credential_id}",
    })


# ── Jira webhook ──────────────────────────────────────────────────────────────
# Setup: Jira Settings → System → WebHooks → Create WebHook
# URL: BASE_URL/webhook/jira/<credential_id>
# Events: select issue created/updated/deleted, sprint, board, etc.
# Jira Cloud also supports Jira Automation → "Send web request" action.

@webhook_bp.route("/jira/<credential_id>", methods=["POST"])
def jira_webhook(credential_id):
    credential, err = _processor().validate_credential(credential_id)
    if err:
        return jsonify({"error": err}), 404

    if credential.get("app_type") != "jira":
        return jsonify({"error": "Not a Jira credential"}), 400

    # Validate optional shared secret
    secret = credential.get("config", {}).get("webhook_secret", "")
    if secret:
        sent = (request.headers.get("X-Hub-Signature")
                or request.headers.get("X-Jira-Webhook-Secret", ""))
        if sent != secret:
            return jsonify({"error": "Invalid webhook secret"}), 401

    payload = dict(request.json or {})

    # Jira sends event type as "webhookEvent" field
    event_type = (
        payload.get("webhookEvent")
        or payload.pop("event_type", None)
        or request.headers.get("X-Event-Type")
        or "jira:issue_updated"
    )
    # Normalise: "jira:issue_created" → keep as-is (already clean)
    event_type = event_type.lower().strip()

    result      = _processor().process_event(credential, event_type, payload)
    status_code = 200 if result.get("processed", 0) > 0 else 202
    return jsonify(result), status_code


@webhook_bp.route("/jira/<credential_id>/test", methods=["GET", "POST"])
def jira_test(credential_id):
    """Connectivity test — paste this URL into Jira Webhook settings to verify."""
    storage    = current_app.config["STORAGE"]
    credential = storage.get_credential(credential_id)
    if not credential or credential.get("app_type") != "jira":
        return jsonify({"error": "Jira credential not found"}), 404
    return jsonify({
        "success":       True,
        "credential_id": credential_id,
        "name":          credential.get("name"),
        "message":       "AppScript Bridge Jira connection verified",
        "webhook_url":   f"{current_app.config['BASE_URL']}/webhook/jira/{credential_id}",
    })


# ── Connectivity test ─────────────────────────────────────────────────────────

@webhook_bp.route("/test", methods=["GET", "POST"])
def test_webhook():
    return jsonify({
        "success": True,
        "message": "AppScript Bridge webhook endpoint is reachable",
        "received": {
            "method":       request.method,
            "content_type": request.content_type,
            "body":         request.json,
        },
    })
