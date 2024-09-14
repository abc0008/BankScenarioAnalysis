import os
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.exc import SQLAlchemyError

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

class GLFact(db.Model):
    __tablename__ = 'GL_Fact'

    Period = db.Column(db.String, primary_key=True)
    InterCo = db.Column(db.String)
    GL_Account = db.Column("GL Account", db.Integer)
    Project = db.Column(db.String)
    Scenario = db.Column(db.String)
    Entity = db.Column(db.String)
    Measure = db.Column(db.String)
    Product = db.Column(db.String)
    Value = db.Column(db.Float)
    Financial_Value = db.Column(db.Float)
    Period_EndDate = db.Column(db.String)
    Major_GL_Account = db.Column("Major GL Account", db.String)

class BankParameter(db.Model):
    __tablename__ = 'bank_parameter'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), nullable=False, unique=True)
    base = db.Column(db.Float, nullable=False)
    forecast = db.Column(db.Float, nullable=False)

class EconomicAssumption(db.Model):
    __tablename__ = 'economic_assumption'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    base = db.Column(db.Float, nullable=False)
    forecast = db.Column(db.Float, nullable=False)

    __table_args__ = (db.UniqueConstraint('key', 'year', name='_key_year_uc'),)

def check_gl_fact_table(app):
    with app.app_context():
        try:
            result = db.session.execute(text("SELECT COUNT(*) FROM GL_Fact")).scalar()
            app.logger.info(f"GL_Fact table exists and contains {result} rows.")
            
            # Get column information
            inspector = inspect(db.engine)
            columns = inspector.get_columns('GL_Fact')
            app.logger.info(f"GL_Fact table columns: {[col['name'] for col in columns]}")
            
            # Get a sample row
            sample_row = db.session.execute(text("SELECT * FROM GL_Fact LIMIT 1")).fetchone()
            app.logger.info(f"Sample row from GL_Fact: {sample_row}")
        except SQLAlchemyError as e:
            app.logger.error(f"Error checking GL_Fact contents: {str(e)}")

def init_db(app):
    db.init_app(app)
    with app.app_context():
        try:
            db.engine.connect()
            app.logger.info(f"Successfully connected to the database: {app.config['SQLALCHEMY_DATABASE_URI']}")
            
            db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
            app.logger.info(f"Database file path: {db_path}")
            app.logger.info(f"Database file exists: {os.path.exists(db_path)}")

            if not os.path.exists(db_path):
                app.logger.error(f"Database file does not exist: {db_path}")
                return

            inspector = inspect(db.engine)
            table_names = inspector.get_table_names()
            app.logger.info(f"Tables in the database: {', '.join(table_names)}")

            check_gl_fact_table(app)

        except Exception as e:
            app.logger.error(f"Error during database initialization: {str(e)}")

        app.logger.info("Database initialization complete.")