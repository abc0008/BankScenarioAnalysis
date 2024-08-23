import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_flask_dir = os.path.abspath(os.path.join(current_dir, '..', 'Backend-Flask'))
sys.path.insert(0, backend_flask_dir)
from flask import Flask
from models import db, GLFact, init_db, check_gl_fact_table
from config import Config

# Create a test Flask app
app = Flask(__name__)
app.config.from_object(Config)
Config.init_app(app)

# Initialize the database with the app
init_db(app)

# Additional check for GL_Fact table
with app.app_context():
    check_gl_fact_table(app)

def test_database_connection():
    with app.app_context():
        try:
            # Get the total number of records
            total_records = GLFact.query.count()
            print(f"Total records in GLFact table: {total_records}")

            # Fetch a sample of records
            sample_records = GLFact.query.limit(5).all()
            print("\nSample records from GLFact table:")
            for record in sample_records:
                print(f"Period: {record.Period}, Scenario: {record.Scenario}, "
                      f"Major GL Account: {record.Major_GL_Account}, Value: {record.Value}")

            # Check for records with Major_GL_Account as 'Assets'
            assets_count = GLFact.query.filter(GLFact.Major_GL_Account == 'Assets').count()
            print(f"\nNumber of records with Major_GL_Account 'Assets': {assets_count}")

            # Check for unique scenarios
            scenarios = db.session.query(GLFact.Scenario.distinct()).all()
            print("\nUnique Scenarios in the database:")
            for scenario in scenarios:
                print(scenario[0])

        except Exception as e:
            print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    test_database_connection()