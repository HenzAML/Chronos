from flask import Flask, jsonify
from flask_cors import CORS

from app.config import Config
from app.extensions import db, migrate, jwt


def create_app(database_url=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if database_url:        # tests point the app at their own database
        app.config["SQLALCHEMY_DATABASE_URI"] = database_url

    db.init_app(app)

    # Imported for the side effect of registering models on db.metadata,
    # which Flask-Migrate needs for autogenerate.
    from app import models  # noqa: F401

    migrate.init_app(app, db)
    jwt.init_app(app)
    CORS(app)

    from app.api import register_api
    register_api(app)

    @app.get("/api/health")
    def health():
        return jsonify(status="ok")

    return app
