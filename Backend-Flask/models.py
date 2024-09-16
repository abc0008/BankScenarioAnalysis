# models.py

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

db = SQLAlchemy()

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

def init_db(app):
    with app.app_context():
        try:
            db.create_all()
            app.logger.info("Database tables created successfully")
        except SQLAlchemyError as e:
            app.logger.error(f"Error creating database tables: {str(e)}")

def check_gl_fact_table(app):
    with app.app_context():
        try:
            result = db.session.execute(text("SELECT COUNT(*) FROM GL_Fact")).scalar()
            app.logger.info(f"GL_Fact table exists and contains {result} rows.")
            
            inspector = inspect(db.engine)
            columns = inspector.get_columns('GL_Fact')
            app.logger.info(f"GL_Fact table columns: {[col['name'] for col in columns]}")
            
            sample_row = db.session.execute(text("SELECT * FROM GL_Fact LIMIT 1")).fetchone()
            app.logger.info(f"Sample row from GL_Fact: {sample_row}")
        except SQLAlchemyError as e:
            app.logger.error(f"Error checking GL_Fact contents: {str(e)}")