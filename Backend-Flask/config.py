import os

class Config:
    basedir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.abspath(os.path.join(basedir, '..', 'Sample_BankData.db'))
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or f'sqlite:///{db_path}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = os.environ.get('FLASK_DEBUG', 'True') == 'True'
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key'

    @staticmethod
    def init_app(app):
        print(f"Using database: {app.config['SQLALCHEMY_DATABASE_URI']}")
        print(f"Database file path: {Config.db_path}")
        print(f"Database file exists: {os.path.exists(Config.db_path)}")
        # Set the database path as an environment variable
        os.environ['DATABASE_URL'] = app.config['SQLALCHEMY_DATABASE_URI']