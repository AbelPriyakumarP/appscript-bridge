from flask import Blueprint, redirect, request, session, url_for, jsonify, current_app
from google_auth_oauthlib.flow import Flow
import os
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _create_flow():
    config = current_app.config
    return Flow.from_client_config(
        {
            "web": {
                "client_id": config["GOOGLE_CLIENT_ID"],
                "client_secret": config["GOOGLE_CLIENT_SECRET"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [config["GOOGLE_REDIRECT_URI"]],
            }
        },
        scopes=config["SCOPES"],
        redirect_uri=config["GOOGLE_REDIRECT_URI"],
    )


@auth_bp.route("/login")
def login():
    flow = _create_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    session["oauth_state"] = state
    return redirect(auth_url)


@auth_bp.route("/callback")
def callback():
    flow = _create_flow()
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    storage = current_app.config["STORAGE"]

    # Save expiry so _get_credentials() can detect stale tokens and auto-refresh.
    expiry_iso = credentials.expiry.isoformat() if credentials.expiry else None

    tokens = {
        "access_token":  credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri":     credentials.token_uri,
        "client_id":     credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes":        list(credentials.scopes) if credentials.scopes else [],
        "expiry":        expiry_iso,
    }
    storage.save_google_tokens(tokens)
    session["google_connected"] = True

    import requests as req
    try:
        userinfo = req.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {credentials.token}"},
            timeout=10,
        ).json()
        session["user_email"]   = userinfo.get("email", "")
        session["user_name"]    = userinfo.get("name", "")
        session["user_picture"] = userinfo.get("picture", "")
    except Exception:
        pass

    return redirect(url_for("dashboard.index"))


@auth_bp.route("/status")
def status():
    storage = current_app.config["STORAGE"]
    tokens = storage.get_google_tokens()
    connected = bool(tokens and tokens.get("access_token"))
    return jsonify({
        "connected": connected,
        "email": session.get("user_email", ""),
        "name": session.get("user_name", ""),
    })


@auth_bp.route("/disconnect", methods=["POST"])
def disconnect():
    storage = current_app.config["STORAGE"]
    storage.save_google_tokens({})
    session.clear()
    return jsonify({"success": True})
