from flask import request, jsonify, current_app
from flask_restful import Resource
from models import db, GLFact, BankParameter, EconomicAssumption
from sqlalchemy import func, and_, text, inspect
from marshmallow import Schema, fields
from RMProForma_Calculations import calculate_pro_forma
import traceback  # Add this import
import logging

logger = logging.getLogger(__name__)

class LoanBalanceSchema(Schema):
    Period_EndDate = fields.String()
    Scenario = fields.String()
    TotalValue = fields.Float()

class BankParameterSchema(Schema):
    key = fields.String()
    base = fields.Float()
    forecast = fields.Float()

class EconomicAssumptionSchema(Schema):
    key = fields.String()
    year = fields.Integer()
    base = fields.Float()
    forecast = fields.Float()

class AssetBalanceSchema(Schema):
    Period_EndDate = fields.String()
    Scenario = fields.String()
    TotalValue = fields.Float()

loan_balance_schema = LoanBalanceSchema(many=True)
bank_parameter_schema = BankParameterSchema(many=True)
economic_assumption_schema = EconomicAssumptionSchema(many=True)
asset_balance_schema = AssetBalanceSchema(many=True)

class LoanBalanceResource(Resource):
    def get(self):
        current_app.logger.info("Accessed LoanBalanceResource GET method")
        try:
            loan_balances = db.session.query(
                GLFact.Period_EndDate,
                GLFact.Scenario,
                func.sum(GLFact.Value).label('TotalValue')
            ).filter(
                and_(
                    GLFact.Major_GL_Account == 'Assets',
                    GLFact.Scenario.in_(['Actual', 'Budget', 'Forecast'])
                )
            ).group_by(
                GLFact.Period_EndDate,
                GLFact.Scenario
            ).order_by(
                GLFact.Period_EndDate,
                GLFact.Scenario
            ).all()

            result = loan_balance_schema.dump(loan_balances)
            current_app.logger.info(f"LoanBalanceResource GET method successful, returning {len(result)} records")
            return jsonify(result)
        except Exception as e:
            current_app.logger.error(f"Error in LoanBalanceResource GET method: {str(e)}")
            return {"error": str(e)}, 500

class BankParameterResource(Resource):
    def get(self):
        current_app.logger.info("Accessed BankParameterResource GET method")
        try:
            parameters = BankParameter.query.all()
            result = bank_parameter_schema.dump(parameters)
            current_app.logger.info(f"BankParameterResource GET method successful, returning {len(result)} records")
            return jsonify(result)
        except Exception as e:
            current_app.logger.error(f"Error in BankParameterResource GET method: {str(e)}")
            return {"error": str(e)}, 500

    def post(self):
        current_app.logger.info("Accessed BankParameterResource POST method")
        try:
            data = request.get_json()
            for param in data:
                existing = BankParameter.query.filter_by(key=param['key']).first()
                if existing:
                    existing.base = param['base']
                    existing.forecast = param['forecast']
                else:
                    new_param = BankParameter(key=param['key'], base=param['base'], forecast=param['forecast'])
                    db.session.add(new_param)
            db.session.commit()
            current_app.logger.info("BankParameterResource POST method successful")
            return {"message": "Bank parameters updated successfully"}, 200
        except Exception as e:
            current_app.logger.error(f"Error in BankParameterResource POST method: {str(e)}")
            db.session.rollback()
            return {"error": str(e)}, 500

class EconomicAssumptionResource(Resource):
    def get(self):
        current_app.logger.info("Accessed EconomicAssumptionResource GET method")
        try:
            assumptions = EconomicAssumption.query.all()
            result = economic_assumption_schema.dump(assumptions)
            current_app.logger.info(f"EconomicAssumptionResource GET method successful, returning {len(result)} records")
            return jsonify(result)
        except Exception as e:
            current_app.logger.error(f"Error in EconomicAssumptionResource GET method: {str(e)}")
            return {"error": str(e)}, 500

    def post(self):
        current_app.logger.info("Accessed EconomicAssumptionResource POST method")
        try:
            data = request.get_json()
            for assumption in data:
                existing = EconomicAssumption.query.filter_by(key=assumption['key'], year=assumption['year']).first()
                if existing:
                    existing.base = assumption['base']
                    existing.forecast = assumption['forecast']
                else:
                    new_assumption = EconomicAssumption(
                        key=assumption['key'],
                        year=assumption['year'],
                        base=assumption['base'],
                        forecast=assumption['forecast']
                    )
                    db.session.add(new_assumption)
            db.session.commit()
            current_app.logger.info("EconomicAssumptionResource POST method successful")
            return {"message": "Economic assumptions updated successfully"}, 200
        except Exception as e:
            current_app.logger.error(f"Error in EconomicAssumptionResource POST method: {str(e)}")
            db.session.rollback()
            return {"error": str(e)}, 500

class AssetBalanceResource(Resource):
    def get(self):
        current_app.logger.info("Accessed AssetBalanceResource GET method")
        try:
            inspector = inspect(db.engine)
            if 'GL_Fact' not in inspector.get_table_names():
                current_app.logger.error("GL_Fact table does not exist in the database")
                return {"error": "Database is not properly initialized"}, 500

            count = db.session.query(GLFact).count()
            
            if count == 0:
                current_app.logger.error("GL_Fact table is empty")
                return {"error": "GL_Fact table is empty"}, 404

            query = db.session.query(
                GLFact.Period_EndDate,
                GLFact.Scenario,
                func.sum(GLFact.Value).label('TotalValue')
            ).filter(
                and_(
                    GLFact.Major_GL_Account == 'Assets',
                    GLFact.Scenario.in_(['Actual', 'Budget', 'Forecast'])
                )
            ).group_by(
                GLFact.Period_EndDate,
                GLFact.Scenario
            ).order_by(
                GLFact.Period_EndDate,
                GLFact.Scenario
            )
            
            current_app.logger.info(f"Executing query: {query}")
            
            result = query.all()

            asset_balances = [
                {
                    "Period_EndDate": row.Period_EndDate,
                    "Scenario": row.Scenario,
                    "TotalValue": float(row.TotalValue)
                } for row in result
            ]

            if len(asset_balances) == 0:
                current_app.logger.warning("No asset balance data found for the given parameters")
                return {"message": "No asset balance data found for the given parameters"}, 404
            
            current_app.logger.info(f"AssetBalanceResource GET method successful, returning {len(asset_balances)} records")
            return jsonify(asset_balances)
        except Exception as e:
            current_app.logger.error(f"Error in AssetBalanceResource GET method: {str(e)}")
            return {"error": str(e)}, 500

class RMProFormaCalculation(Resource):
    def post(self):
        current_app.logger.info("Accessed RMProFormaCalculation POST method")
        try:
            data = request.get_json()
            current_app.logger.info(f"Received data: {data}")
            
            # Perform calculations
            result = calculate_pro_forma(data)
            
            # Validate result
            if 'annualSummary' not in result:
                current_app.logger.error(f"Missing annualSummary in calculation result: {result}")
                raise ValueError("Calculation failed to produce annual summary data")
            
            if 'cumulativePayback' not in result:
                current_app.logger.warning(f"Missing cumulativePayback in calculation result: {result}")
                result['cumulativePayback'] = None
            
            current_app.logger.info("RMProFormaCalculation POST method successful")
            return jsonify(result)
        except Exception as e:
            current_app.logger.error(f"Error in RMProFormaCalculation POST method: {str(e)}")
            current_app.logger.error(f"Traceback: {traceback.format_exc()}")
            return {'error': str(e)}, 400

class YieldCurveResource(Resource):
    def post(self):
        current_app.logger.info("Accessed YieldCurveResource POST method")
        try:
            data = request.get_json()
            current_app.logger.info(f"Received yield curve data: {data}")
            
            # Validate the received data
            if not isinstance(data, dict):
                raise ValueError("Invalid data format. Expected a dictionary.")
            
            for year, curve in data.items():
                if not isinstance(curve, dict):
                    raise ValueError(f"Invalid curve data for year {year}. Expected a dictionary.")
                
                for term, rate in curve.items():
                    if not isinstance(rate, (int, float)):
                        raise ValueError(f"Invalid rate for year {year}, term {term}. Expected a number.")
            
            # Process the data (in this case, we're just returning it as-is)
            result = data
            
            current_app.logger.info("YieldCurveResource POST method successful")
            return jsonify(result)
        except Exception as e:
            current_app.logger.error(f"Error in YieldCurveResource POST method: {str(e)}")
            current_app.logger.error(f"Traceback: {traceback.format_exc()}")
            return {'error': str(e)}, 400

class GLFactStatusResource(Resource):
    def get(self):
        current_app.logger.info("Accessed GLFactStatusResource GET method")
        try:
            inspector = inspect(db.engine)
            
            status = {
                "table_exists": 'GL_Fact' in inspector.get_table_names(),
                "record_count": db.session.query(GLFact).count(),
                "columns": [col['name'] for col in inspector.get_columns('GL_Fact')],
                "scenarios": [s[0] for s in db.session.query(GLFact.Scenario).distinct().all()]
            }
            
            if status["record_count"] > 0:
                sample = db.session.query(GLFact).first()
                status["sample_record"] = {c.name: getattr(sample, c.name) for c in sample.__table__.columns}
            
            return jsonify(status)
        except Exception as e:
            current_app.logger.error(f"Error in GLFactStatusResource GET method: {str(e)}")
            return {"error": str(e)}, 500

class DatabaseStatusResource(Resource):
    def get(self):
        current_app.logger.info("Accessed DatabaseStatusResource GET method")
        try:
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            status = {
                "database_uri": current_app.config['SQLALCHEMY_DATABASE_URI'],
                "tables": tables,
                "gl_fact_count": 0
            }
            
            if 'GL_Fact' in tables:
                query = text('SELECT COUNT(*) FROM "GL_Fact"')
                result = db.session.execute(query)
                status["gl_fact_count"] = result.scalar()
            
            current_app.logger.info(f"Database status: {status}")
            return jsonify(status)
        except Exception as e:
            current_app.logger.error(f"Error in DatabaseStatusResource GET method: {str(e)}")
            return {"error": str(e)}, 500

class RMProFormaIntegrationTest(Resource):
    def get(self):
        current_app.logger.info("Running RM ProForma Integration Test")
        try:
            test_data = {
                'annualProduction': [{'loans': 500000, 'deposits': 300000} for _ in range(5)],
                'loanVsLinePercentage': 50,
                'goingOnYields': [{'loans': 3, 'lines': 2, 'deposits': 3} for _ in range(5)],
                'lineUtilizationPercentage': 50,
                'originationFeePercentage': 0.25,
                'unusedCommitmentFeePercentage': 0.25,
                'salary': 75000,
                'annualMeritIncrease': 3,
                'discretionaryExpenses': 6000,
                'deferredCostsPerLoan': 1,
                'averageLifeLoans': 5,
                'averageLifeLines': 3,
                'prepayPercentageOfBalance': 25
            }
            
            result = calculate_pro_forma(test_data)
            
            return {"message": "Integration test passed", "result": result}, 200
        except Exception as e:
            current_app.logger.error(f"Integration test failed: {str(e)}")
            return {"message": f"Integration test failed: {str(e)}"}, 500

class YieldCurveResource(Resource):
    def post(self):
        current_app.logger.info("Accessed YieldCurveResource POST method")
        try:
            data = request.get_json()
            current_app.logger.info(f"Received yield curve data: {data}")
            
            # Validate the received data
            if not isinstance(data, dict):
                raise ValueError("Invalid data format. Expected a dictionary.")
            
            for year, curve in data.items():
                if not isinstance(curve, dict):
                    raise ValueError(f"Invalid curve data for year {year}. Expected a dictionary.")
                
                for term, rate in curve.items():
                    if not isinstance(rate, (int, float)):
                        raise ValueError(f"Invalid rate for year {year}, term {term}. Expected a number.")
            
            # Process the data (in this case, we're just returning it as-is)
            result = data
            
            current_app.logger.info("YieldCurveResource POST method successful")
            return jsonify(result)
        except Exception as e:
            current_app.logger.error(f"Error in YieldCurveResource POST method: {str(e)}")
            current_app.logger.error(f"Traceback: {traceback.format_exc()}")
            return {'error': str(e)}, 400

def initialize_routes(api):
    current_app.logger.info("Initializing routes")
    api.add_resource(LoanBalanceResource, '/api/loan-balances')
    api.add_resource(BankParameterResource, '/api/bank-parameters')
    api.add_resource(EconomicAssumptionResource, '/api/economic-assumptions')
    api.add_resource(AssetBalanceResource, '/api/asset-balances')
    api.add_resource(GLFactStatusResource, '/api/gl-fact-status')
    api.add_resource(DatabaseStatusResource, '/api/database-status')
    api.add_resource(RMProFormaCalculation, '/api/rm-pro-forma-calculate')
    api.add_resource(YieldCurveResource, '/api/yield-curves')
    api.add_resource(RMProFormaIntegrationTest, '/api/rm-pro-forma-integration-test')
    current_app.logger.info("Routes initialized successfully")