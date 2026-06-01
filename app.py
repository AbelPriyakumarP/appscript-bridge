import os
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

from flask import Flask
from flask_cors import CORS
from config import Config
from services.storage import JSONStorage
from services.apps_script import AppsScriptService
from services.event_processor import EventProcessor


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(app)

    storage = JSONStorage(Config.DATA_DIR)
    apps_script = AppsScriptService(storage)
    event_processor = EventProcessor(storage, apps_script)

    app.config["STORAGE"] = storage
    app.config["APPS_SCRIPT"] = apps_script
    app.config["EVENT_PROCESSOR"] = event_processor

    from routes.auth import auth_bp
    from routes.webhook import webhook_bp
    from routes.api import api_bp
    from routes.dashboard import dashboard_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(webhook_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(dashboard_bp)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)
