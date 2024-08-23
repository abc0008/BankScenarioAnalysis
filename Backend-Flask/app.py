import sys
print("Python version:", sys.version)
print("Python path:", sys.path)

import os
print("Current working directory:", os.getcwd())

import importlib.util  # Changed this line
print("os module:", importlib.util.find_spec("os"))

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from flask_restful import Api
from config import Config
from models import db, init_db, check_gl_fact_table
import logging
from logging.config import dictConfig

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
    app = Flask(__name__, static_folder='../bank-dashboard/build', static_url_path='')
    app.config.from_object(Config)
    Config.init_app(app)

    # Initialize extensions
    CORS(app)
    api = Api(app)
    init_db(app)

    # Additional check for GL_Fact table
    with app.app_context():
        check_gl_fact_table(app)

    # Import and initialize routes within the application context
    with app.app_context():
        from routes import initialize_routes
        initialize_routes(api)

    @app.route('/api/')
    def api_root():
        app.logger.info("Accessed API root route")
        return jsonify({"message": "Welcome to the Bank API"}), 200

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve(path):
        if path.startswith('api/'):
            # This is an API route, let Flask-RESTful handle it
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