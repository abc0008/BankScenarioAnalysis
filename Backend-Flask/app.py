# app.py

import sys
import os
import logging
from logging.config import dictConfig

from flask import Flask, jsonify, send_from_directory
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
    app.logger.info(f"Database file path: {os.path.abspath(db_path)}")
    app.logger.info(f"Database file exists: {os.path.exists(os.path.abspath(db_path))}")

    # Initialize extensions
    CORS(app)  # Enables CORS for all routes
    db.init_app(app)
    
    with app.app_context():
        init_db(app)  # Create tables
        check_gl_fact_table(app)  # Check GL_Fact table

    # Initialize routes
    initialize_routes(app)

    @app.route('/api/')
    def api_root():
        app.logger.info("Accessed API root route")
        return jsonify({"message": "Welcome to the Bank API"}), 200

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve(path):
        if path.startswith('api/'):
            return app.handle_http_exception(404)
        elif path != "" and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        else:
            return send_from_directory(app.static_folder, 'index.html')

    return app

app = create_app()

if __name__ == '__main__':
    app.logger.info("Starting the Flask application")
    app.logger.info(f"Using database: {app.config['SQLALCHEMY_DATABASE_URI']}")
    app.run(host='127.0.0.1', port=5001, debug=Config.DEBUG)