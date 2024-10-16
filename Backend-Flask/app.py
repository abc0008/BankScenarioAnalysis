# app.py

import sys
import os
import importlib.util
import logging
from logging.config import dictConfig
import traceback

from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from config import Config
from models import db, init_db, check_gl_fact_table
from routes import initialize_routes

# Configure logging
dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    }},
    'handlers': {'wsgi': {
        'class': 'logging.StreamHandler',
        'stream': 'ext://flask.logging.wsgi_errors_stream',
        'formatter': 'default'
    }},
    'root': {
        'level': 'INFO',
        'handlers': ['wsgi']
    }
})

def create_app():
    app = Flask(__name__, static_folder='build', static_url_path='')
    app.config.from_object(Config)
    Config.init_app(app)

    # Print the full path of the database file
    db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
    print(f"Database file path: {os.path.abspath(db_path)}")
    print(f"Database file exists: {os.path.exists(os.path.abspath(db_path))}")

    # Initialize extensions
    CORS(app)  # Enables CORS for all routes
    init_db(app)

    # Additional check for GL_Fact table
    with app.app_context():
        check_gl_fact_table(app)

    # Initialize routes
    with app.app_context():
        initialize_routes(app)

    # Enhanced Error Logging: Log all registered routes and methods
    routes = {}
    for rule in app.url_map.iter_rules():
        routes[rule.rule] = sorted([method for method in rule.methods if method not in ('HEAD', 'OPTIONS')])
    app.logger.info(f"Registered Routes: {routes}")

    @app.route('/api/')
    def api_root():
        app.logger.info("Accessed API root route")
        return jsonify({"message": "Welcome to the Bank API"}), 200

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve(path):
        if path.startswith('api/'):
            # This is an API route, let Flask handle it
            return app.handle_http_exception(404)
        elif path != "" and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        else:
            return send_from_directory(app.static_folder, 'index.html')

    return app

def get_table_names(app):
    with app.app_context():
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        app.logger.info(f"Tables in the database: {tables}")
        return tables

def test_database_connection(app):
    with app.app_context():
        try:
            result = db.session.execute(text("SELECT 1")).fetchone()
            print("Database connection successful:", result)
        except SQLAlchemyError as e:
            print("Database connection failed:", str(e))

app = create_app()

if __name__ == '__main__':
    app.logger.info("Starting the Flask application")
    app.logger.info(f"Using database: {app.config['SQLALCHEMY_DATABASE_URI']}")
    app.run(host='127.0.0.1', port=5001, debug=Config.DEBUG)