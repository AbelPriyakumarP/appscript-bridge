import requests
from flask import Blueprint, request, jsonify, current_app

webhook_bp = Blueprint("webhook", __name__, url_prefix="/webhook")


@webhook_bp.route("/trigger", methods=["POST"])
def trigger():
    api_key = (
        request.headers.get("X-API-Key")
        or request.args.get("api_key")
        or (request.json or {}).get("api_key")
    )
    if not api_key:
        return jsonify({"error": "Missing API key. Provide via X-API-Key header, query param, or body."}), 401

    event_type = (
        request.headers.get("X-Event-Type")
        or (request.json or {}).get("event_type")
        or request.args.get("event_type")
    )

    processor = current_app.config["EVENT_PROCESSOR"]
    credential, error = processor.validate_api_key(api_key)
    if error:
        return jsonify({"error": error}), 401

    payload = request.json or {}
    payload.pop("api_key", None)
    payload.pop("event_type", None)

    result = processor.process_event(credential, event_type, payload)
    status_code = 200 if result.get("processed", 0) > 0 else 202
    return jsonify(result), status_code


# ── Telegram webhook ──
# Telegram sends updates directly to this URL (no API key needed, identified by credential_id)
@webhook_bp.route("/telegram/<credential_id>", methods=["POST"])
def telegram_webhook(credential_id):
    processor = current_app.config["EVENT_PROCESSOR"]
    credential, error = processor.validate_credential(credential_id)
    if error:
        return jsonify({"error": error}), 404

    if credential.get("app_type") != "telegram":
        return jsonify({"error": "Not a Telegram credential"}), 400

    update = request.json or {}
    event_type, payload = processor.parse_telegram_event(update)
    result = processor.process_event(credential, event_type, payload)
    return jsonify({"ok": True}), 200


# ── ServiceNow webhook ──
@webhook_bp.route("/servicenow/<credential_id>", methods=["POST"])
def servicenow_webhook(credential_id):
    processor = current_app.config["EVENT_PROCESSOR"]
    credential, error = processor.validate_credential(credential_id)
    if error:
        return jsonify({"error": error}), 404

    if credential.get("app_type") != "servicenow":
        return jsonify({"error": "Not a ServiceNow credential"}), 400

    payload = request.json or {}
    event_type, payload = processor.parse_servicenow_event(payload)
    result = processor.process_event(credential, event_type, payload)
    status_code = 200 if result.get("processed", 0) > 0 else 202
    return jsonify(result), status_code


# ── Telegram Bot: register webhook with Telegram API ──
@webhook_bp.route("/telegram/<credential_id>/register", methods=["POST"])
def register_telegram_webhook(credential_id):
    storage = current_app.config["STORAGE"]
    credential = storage.get_credential(credential_id)
    if not credential or credential.get("app_type") != "telegram":
        return jsonify({"error": "Telegram credential not found"}), 404

    bot_token = credential.get("config", {}).get("bot_token", "")
    if not bot_token:
        return jsonify({"error": "Bot token not configured"}), 400

    base_url = current_app.config["BASE_URL"]
    webhook_url = f"{base_url}/webhook/telegram/{credential_id}"

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{bot_token}/setWebhook",
            json={"url": webhook_url},
            timeout=10,
        )
        result = resp.json()
        if result.get("ok"):
            storage.update_credential(credential_id, {"webhook_registered": True})
            return jsonify({"success": True, "webhook_url": webhook_url})
        return jsonify({"success": False, "error": result.get("description", "Unknown error")}), 400
    except requests.RequestException as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ── Telegram Bot: get webhook info ──
@webhook_bp.route("/telegram/<credential_id>/info", methods=["GET"])
def telegram_webhook_info(credential_id):
    storage = current_app.config["STORAGE"]
    credential = storage.get_credential(credential_id)
    if not credential or credential.get("app_type") != "telegram":
        return jsonify({"error": "Telegram credential not found"}), 404

    bot_token = credential.get("config", {}).get("bot_token", "")
    if not bot_token:
        return jsonify({"error": "Bot token not configured"}), 400

    try:
        resp = requests.get(f"https://api.telegram.org/bot{bot_token}/getWebhookInfo", timeout=10)
        return jsonify(resp.json())
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 500


@webhook_bp.route("/test", methods=["POST"])
def test_webhook():
    return jsonify({
        "success": True,
        "message": "Webhook endpoint is reachable",
        "received": {
            "method": request.method,
            "content_type": request.content_type,
            "body": request.json,
        },
    })
