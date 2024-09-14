# RMProForma_Calculations.py
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from scipy import interpolate
import logging
import traceback
import re
from dateutil.parser import parse as dateutil_parse
import json
from dateutil.relativedelta import relativedelta

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class YieldCurve:
    """Represents a yield curve for interest rate interpolation."""
    def __init__(self, tenors, rates):
        self.curve = interpolate.interp1d(tenors, rates, kind='cubic', fill_value='extrapolate')

    def get_rate(self, tenor):
        """Get interpolated rate for a given tenor."""
        return float(self.curve(tenor))


class RMProFormaModel:
    def __init__(self, inputs):
        self.inputs = inputs
        self.validate_inputs()
        self.rm_hire_date = pd.Timestamp(self.inputs['rmHireDate'])  # Convert to Timestamp
        self.first_production_date = pd.Timestamp(self.inputs['firstProductionDate'])  # Convert to Timestamp
        self.end_date = self.first_production_date + relativedelta(years=5)  # 5 years from first production
        self.dates = pd.date_range(start=self.rm_hire_date, end=self.end_date, freq='MS')
        self.yield_curves = self._initialize_yield_curves()
        self.incentive_compensation_percentage = self.inputs['incentiveCompensationPercentage']
        self.direct_cost_per_loan = self.inputs['deferredCostsPerLoan']
        self.indirect_cost_per_loan = self.inputs.get('indirectCostsPerLoan', 0)  # New input for indirect costs

    @staticmethod
    def parse_date(date_value):
        """Parse date string into datetime object or return datetime object unchanged."""
        if isinstance(date_value, datetime):
            return date_value
        if isinstance(date_value, str):
            try:
                return datetime.strptime(date_value, "%Y-%m-%d").date()
            except ValueError as e:
                logger.error(f"Error parsing date: {date_value}. Error: {str(e)}")
                raise ValueError(f"Invalid date format: {date_value}. Expected format: YYYY-MM-DD")
        raise ValueError(f"Unsupported date type: {type(date_value)}")


    def validate_inputs(self):
        """Validate that all required input fields are present and in the correct format."""
        logger.info("Starting input validation")
        required_fields = ['rmHireDate', 'firstProductionDate', 'annualProduction', 'loanVsLinePercentage', 
                           'goingOnYields', 'lineUtilizationPercentage', 'originationFeePercentage', 
                           'unusedCommitmentFeePercentage', 'salary', 'annualMeritIncrease',
                           'discretionaryExpenses', 'deferredCostsPerLoan', 'averageLifeLoans', 
                           'averageLifeLines', 'prepayPercentageOfBalance', 'incentiveCompensationPercentage',
                           'avgLoanExposureAtOrigination']
        
        for field in required_fields:
            if field not in self.inputs:
                logger.error(f"Missing required input: {field}")
                raise ValueError(f"Missing required input: {field}")
            else:
                logger.debug(f"Found required input: {field}")
        
        # Validate dates
        date_fields = ['rmHireDate', 'firstProductionDate']
        for field in date_fields:
            try:
                logger.debug(f"Parsing date for {field}: {self.inputs[field]}")
                self.inputs[field] = self.parse_date(self.inputs[field])
                logger.debug(f"Parsed date for {field}: {self.inputs[field]}")
            except ValueError as e:
                logger.error(f"Invalid date format for {field}: {str(e)}")
                raise ValueError(f"Invalid date format for {field}: {str(e)}")
        
        if self.inputs['firstProductionDate'] < self.inputs['rmHireDate']:
            logger.error("First Production Date cannot be earlier than RM Hire Date")
            raise ValueError("First Production Date cannot be earlier than RM Hire Date")
        
        # Convert percentage inputs to floats
        percentage_fields = ['loanVsLinePercentage', 'lineUtilizationPercentage', 'originationFeePercentage', 
                             'unusedCommitmentFeePercentage', 'annualMeritIncrease', 'prepayPercentageOfBalance',
                             'incentiveCompensationPercentage']
        for field in percentage_fields:
            try:
                logger.debug(f"Parsing percentage for {field}: {self.inputs[field]}")
                self.inputs[field] = self.parse_percentage(self.inputs[field])
                logger.debug(f"Parsed percentage for {field}: {self.inputs[field]}")
            except ValueError as e:
                logger.error(f"Invalid percentage value for {field}: {str(e)}")
                raise ValueError(f"Invalid percentage value for {field}: {str(e)}")
        
        # Convert nested structures
        try:
            logger.debug("Parsing annualProduction")
            self.inputs['annualProduction'] = [
                {'loans': self.parse_number(year['loans']), 'deposits': self.parse_number(year['deposits'])} 
                for year in self.inputs['annualProduction']
            ]
            logger.debug(f"Parsed annualProduction: {self.inputs['annualProduction']}")
            
            logger.debug("Parsing goingOnYields")
            self.inputs['goingOnYields'] = [
                {'loans': self.parse_percentage(year['loans']), 
                 'lines': self.parse_percentage(year['lines']), 
                 'deposits': self.parse_percentage(year['deposits'])} 
                for year in self.inputs['goingOnYields']
            ]
            logger.debug(f"Parsed goingOnYields: {self.inputs['goingOnYields']}")
        except (KeyError, ValueError) as e:
            logger.error(f"Invalid structure in annualProduction or goingOnYields: {str(e)}")
            raise ValueError(f"Invalid structure in annualProduction or goingOnYields: {str(e)}")
        
        # Convert other numeric fields
        numeric_fields = ['salary', 'discretionaryExpenses', 'deferredCostsPerLoan', 'averageLifeLoans', 
                          'averageLifeLines', 'avgLoanExposureAtOrigination']
        for field in numeric_fields:
            try:
                logger.debug(f"Parsing numeric value for {field}: {self.inputs[field]}")
                self.inputs[field] = self.parse_number(self.inputs[field])
                logger.debug(f"Parsed numeric value for {field}: {self.inputs[field]}")
            except ValueError as e:
                logger.error(f"Invalid numeric value for {field}: {str(e)}")
                raise ValueError(f"Invalid numeric value for {field}: {str(e)}")
        
        logger.info("Input validation completed successfully")

    @staticmethod
    def parse_percentage(value):
        """Parse percentage value to float."""
        if isinstance(value, (int, float)):
            return float(value) / 100
        elif isinstance(value, str):
            value = value.strip().rstrip('%')
            return float(value) / 100
        else:
            raise ValueError(f"Invalid percentage value: {value}")

    @staticmethod
    def parse_number(value):
        """Parse number value to float."""
        if isinstance(value, (int, float)):
            return float(value)
        elif isinstance(value, str):
            # Remove commas and other non-numeric characters except for decimal point
            value = re.sub(r'[^\d.-]', '', value)
            return float(value)
        else:
            raise ValueError(f"Invalid numeric value: {value}")

    def _initialize_yield_curves(self):
        """Initialize yield curves for each year based on input rates."""
        tenors = [0.25, 0.5, 1, 2, 3, 5, 10, 30]
        base_rates = [0.01, 0.015, 0.02, 0.025, 0.03, 0.035, 0.04, 0.045]
        yield_curves = {}
        for year in range(5):
            year_start = self.first_production_date + pd.DateOffset(years=year)
            year_rates = [r + self.inputs['goingOnYields'][year]['loans']/100 for r in base_rates]
            yield_curves[year_start] = YieldCurve(tenors, year_rates)
        return yield_curves


    def _generate_monthly_schedule(self):
        """Generate monthly financial schedule over 5 years."""
        df = pd.DataFrame(index=self.dates, columns=[
            'loan_balance', 'line_balance', 'deposit_balance',
            'interest_income_loans', 'interest_income_lines',
            'interest_expense', 'non_interest_income',
            'non_interest_expense', 'provision_expense', 'net_income',
            'cumulative_income', 'cumulative_expenses', 'cumulative_profit',
            'fas91_balance', 'efficiency_ratio',
            'origination_fees', 'unused_commitment_fees',
            'salary_expense', 'incentive_compensation_expense', 'benefits_expense', 'discretionary_expense',
            'total_assets', 'total_liabilities', 'total_equity',
            'loan_monthly_production', 'loan_prepayment_amount', 'loan_scheduled_amortization',
            'line_monthly_production', 'line_prepayment_amount', 'line_utilization_production',
            'deferred_origination_fees', 'deferred_costs', 'deferred_cost_amortization',
            'indirect_costs'
        ])
        
        # Initialize 'fas91_balance' to 0 to avoid NaN
        df['fas91_balance'] = 0.0

        for i, date in enumerate(self.dates):
            try:
                year = (date.year - self.first_production_date.year)  # Adjusted for correct year indexing
                month = (date.month - self.first_production_date.month + 12 * (date.year - self.first_production_date.year)) + 1

                # Calculate expenses from RM Hire Date
                if date >= self.rm_hire_date:
                    months_since_hire = (date.year - self.rm_hire_date.year) * 12 + (date.month - self.rm_hire_date.month)
                    df.loc[date, 'salary_expense'] = self._calculate_salary_expense(months_since_hire)
                    df.loc[date, 'benefits_expense'] = df.loc[date, 'salary_expense'] * 0.28
                    df.loc[date, 'incentive_compensation_expense'] = df.loc[date, 'salary_expense'] * self.incentive_compensation_percentage
                    df.loc[date, 'discretionary_expense'] = self.inputs['discretionaryExpenses'] / 12
                else:
                    df.loc[date, 'salary_expense'] = 0
                    df.loc[date, 'benefits_expense'] = 0
                    df.loc[date, 'incentive_compensation_expense'] = 0
                    df.loc[date, 'discretionary_expense'] = 0
                
                # Calculate balance sheet items from First Production Date
                if date >= self.first_production_date:
                    loan_details = self._calculate_loan_balance(i, df)
                    line_details = self._calculate_line_balance(i, df)
                    
                    # Assign loan details
                    df.loc[date, 'loan_balance'] = loan_details['new_balance']
                    df.loc[date, 'loan_monthly_production'] = loan_details['monthly_production']
                    df.loc[date, 'loan_prepayment_amount'] = loan_details['prepayment_amount']
                    df.loc[date, 'loan_scheduled_amortization'] = loan_details['scheduled_amortization']
                    
                    # Assign line details
                    df.loc[date, 'line_balance'] = line_details['new_balance']
                    df.loc[date, 'line_monthly_production'] = line_details['monthly_production']
                    df.loc[date, 'line_prepayment_amount'] = line_details['prepayment_amount']
                    df.loc[date, 'line_utilization_production'] = line_details['utilization_production']
                    
                    df.loc[date, 'deposit_balance'] = self._calculate_deposit_balance(i, df)
                    
                    df.loc[date, 'interest_income_loans'] = self._calculate_interest_income_loans(i, df)
                    df.loc[date, 'interest_income_lines'] = self._calculate_interest_income_lines(i, df)
                    df.loc[date, 'interest_expense'] = self._calculate_interest_expense(i, df)
                    
                    df.loc[date, 'deferred_origination_fees'], df.loc[date, 'deferred_costs'], \
                    df.loc[date, 'origination_fees'], df.loc[date, 'deferred_cost_amortization'], \
                    df.loc[date, 'indirect_costs'] = self._calculate_deferred_fees_and_costs(i, df)
                    df.loc[date, 'unused_commitment_fees'] = self._calculate_unused_commitment_fees(i, df)
                    df.loc[date, 'non_interest_income'] = df.loc[date, 'origination_fees'] + df.loc[date, 'unused_commitment_fees']
                    
                    df.loc[date, 'provision_expense'] = self._calculate_provision_expense(i, df)
                else:
                    # Initialize all balance sheet and income statement items to 0 for dates before first production
                    for col in df.columns:
                        if col not in ['salary_expense', 'benefits_expense', 'discretionary_expense', 'fas91_balance']:
                            df.loc[date, col] = 0.0

                df.loc[date, 'non_interest_expense'] = (
                    df.loc[date, 'salary_expense'] +
                    df.loc[date, 'benefits_expense'] +
                    df.loc[date, 'incentive_compensation_expense'] +
                    df.loc[date, 'discretionary_expense'] +
                    df.loc[date, 'deferred_cost_amortization'] +
                    df.loc[date, 'indirect_costs']
                )

                df.loc[date, 'net_income'] = (
                    df.loc[date, 'interest_income_loans'] +
                    df.loc[date, 'interest_income_lines'] +
                    df.loc[date, 'non_interest_income'] -
                    df.loc[date, 'interest_expense'] -
                    df.loc[date, 'non_interest_expense'] -
                    df.loc[date, 'provision_expense']
                )

                if i == 0:
                    df.loc[date, 'cumulative_income'] = df.loc[date, 'interest_income_loans'] + df.loc[date, 'interest_income_lines'] + df.loc[date, 'non_interest_income']
                    df.loc[date, 'cumulative_expenses'] = df.loc[date, 'interest_expense'] + df.loc[date, 'non_interest_expense'] + df.loc[date, 'provision_expense']
                else:
                    df.loc[date, 'cumulative_income'] = df.iloc[i-1]['cumulative_income'] + df.loc[date, 'interest_income_loans'] + df.loc[date, 'interest_income_lines'] + df.loc[date, 'non_interest_income']
                    df.loc[date, 'cumulative_expenses'] = df.iloc[i-1]['cumulative_expenses'] + df.loc[date, 'interest_expense'] + df.loc[date, 'non_interest_expense'] + df.loc[date, 'provision_expense']
                
                df.loc[date, 'cumulative_profit'] = df.loc[date, 'cumulative_income'] - df.loc[date, 'cumulative_expenses']
                
                df.loc[date, 'efficiency_ratio'] = self._calculate_efficiency_ratio(df.loc[date])
                
                df.loc[date, 'total_assets'] = (
                    df.loc[date, 'loan_balance'] + 
                    df.loc[date, 'line_balance'] + 
                    df.loc[date, 'deferred_costs'] - 
                    df.loc[date, 'deferred_origination_fees']
                )
                df.loc[date, 'total_liabilities'] = df.loc[date, 'deposit_balance']
                df.loc[date, 'total_equity'] = df.loc[date, 'total_assets'] - df.loc[date, 'total_liabilities']
            
            except Exception as e:
                logger.error(f"Error in _generate_monthly_schedule for date {date}: {str(e)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                raise

        return df


    def _calculate_efficiency_ratio(self, row):
        """Calculate efficiency ratio as non-interest expense divided by total revenue minus interest expense."""
        total_revenue = row['interest_income_loans'] + row['interest_income_lines'] + row['origination_fees'] + row['unused_commitment_fees'] - row['interest_expense']
        if total_revenue <= 0:
            return float('inf')
        return (row['non_interest_expense'] / total_revenue)


    def _calculate_interest_income_loans(self, i, df):
        """Calculate interest income for loans."""
        date = df.index[i]
        if date < self.first_production_date:
            return 0.0
        
        # Determine the current yield curve based on the date
        yield_curve_date = max(d for d in self.yield_curves.keys() if d <= date)
        yield_curve = self.yield_curves[yield_curve_date]
        loan_yield = yield_curve.get_rate(self.inputs['averageLifeLoans']) / 12
        
        return df.iloc[i]['loan_balance'] * loan_yield


    def _calculate_interest_income_lines(self, i, df):
        """Calculate interest income for lines."""
        date = df.index[i]
        if date < self.first_production_date:
            return 0.0
        
        # Determine the current yield curve based on the date
        yield_curve_date = max(d for d in self.yield_curves.keys() if d <= date)
        yield_curve = self.yield_curves[yield_curve_date]
        line_yield = yield_curve.get_rate(self.inputs['averageLifeLines']) / 12
        
        return df.iloc[i]['line_balance'] * line_yield


    def _calculate_deferred_fees_and_costs(self, i, df):
        """Calculate deferred fees and costs, considering deferral, amortization, and prepayments."""
        date = df.index[i]
        if date < self.first_production_date:
            return 0.0, 0.0, 0.0, 0.0, 0.0  # Return 0 for all deferred fees and costs
        
        months_since_production = (date.year - self.first_production_date.year) * 12 + (date.month - self.first_production_date.month)
        year = min(months_since_production // 12, 4)

        # Calculate new origination fees and direct costs
        monthly_loan_production = self.inputs['annualProduction'][year]['loans'] / 12.0
        monthly_line_production = self.inputs['annualProduction'][year]['loans'] * self.inputs['loanVsLinePercentage'] / (100 - self.inputs['loanVsLinePercentage']) / 12.0
        total_production = monthly_loan_production + monthly_line_production

        new_origination_fees = total_production * self.inputs['originationFeePercentage']
        new_direct_costs = (total_production / self.inputs['avgLoanExposureAtOrigination']) * self.direct_cost_per_loan

        # Calculate indirect costs (to be expensed immediately)
        indirect_costs = (total_production / self.inputs['avgLoanExposureAtOrigination']) * self.indirect_cost_per_loan

        # Get previous deferred balance
        if i == 0 or df.index[i-1] < self.first_production_date:
            previous_deferred_fees = 0.0
            previous_deferred_costs = 0.0
            previous_loan_balance = 0.0
        else:
            previous_deferred_fees = df.iloc[i-1]['deferred_origination_fees']
            previous_deferred_costs = df.iloc[i-1]['deferred_costs']
            previous_loan_balance = df.iloc[i-1]['loan_balance'] + df.iloc[i-1]['line_balance']

        # Calculate regular amortization using effective interest method
        average_life = self.inputs['averageLifeLoans'] * 12  # Convert to months
        effective_interest_rate = (new_origination_fees - new_direct_costs) / total_production / average_life

        regular_fee_amortization = previous_deferred_fees * effective_interest_rate
        regular_cost_amortization = previous_deferred_costs * effective_interest_rate

        # Calculate prepayment-related amortization
        prepayment_rate = self.inputs['prepayPercentageOfBalance'] / 12.0
        prepayment_amount = previous_loan_balance * prepayment_rate
        if previous_loan_balance > 0:
            prepayment_fee_amortization = (prepayment_amount / previous_loan_balance) * previous_deferred_fees
            prepayment_cost_amortization = (prepayment_amount / previous_loan_balance) * previous_deferred_costs
        else:
            prepayment_fee_amortization = 0.0
            prepayment_cost_amortization = 0.0

        # Total amortization
        total_fee_amortization = regular_fee_amortization + prepayment_fee_amortization
        total_cost_amortization = regular_cost_amortization + prepayment_cost_amortization

        # Calculate new deferred balances
        new_deferred_fees = previous_deferred_fees + new_origination_fees - total_fee_amortization
        new_deferred_costs = previous_deferred_costs + new_direct_costs - total_cost_amortization

        return new_deferred_fees, new_deferred_costs, total_fee_amortization, total_cost_amortization, indirect_costs


    def _calculate_unused_commitment_fees(self, i, df):
        """Calculate unused commitment fees."""
        date = df.index[i]
        if date < self.first_production_date:
            return 0.0
        
        months_since_production = (date.year - self.first_production_date.year) * 12 + (date.month - self.first_production_date.month)
        year = min(months_since_production // 12, 4)
        
        monthly_line_production = self.inputs['annualProduction'][year]['loans'] * self.inputs['loanVsLinePercentage'] / (100 - self.inputs['loanVsLinePercentage']) / 12.0
        unused_balance = monthly_line_production * (1 - self.inputs['lineUtilizationPercentage'])
        return unused_balance * self.inputs['unusedCommitmentFeePercentage']


    def _calculate_salary_expense(self, months_since_hire):
        """Calculate salary expense based on RM Hire Date."""
        years_since_hire = months_since_hire // 12
        base_salary = self.inputs['salary'] * ((1 + self.inputs['annualMeritIncrease']) ** years_since_hire)
        return base_salary / 12.0


    def _calculate_loan_balance(self, i, df):
        """Calculate loan balance considering production and prepayments."""
        date = df.index[i]
        if date < self.first_production_date:
            return {
                'monthly_production': 0.0,
                'prepayment_amount': 0.0,
                'scheduled_amortization': 0.0,
                'new_balance': 0.0
            }
        
        months_since_production = (date.year - self.first_production_date.year) * 12 + (date.month - self.first_production_date.month)
        year = min(months_since_production // 12, 4)
        monthly_production = self.inputs['annualProduction'][year]['loans'] / 12.0
        prepayment_rate = self.inputs['prepayPercentageOfBalance'] / 12.0 
        
        if i == 0 or df.index[i-1] < self.first_production_date:
            return {
                'monthly_production': monthly_production,
                'prepayment_amount': 0.0,
                'scheduled_amortization': 0.0,
                'new_balance': monthly_production
            }
        else:
            previous_balance = df.iloc[i-1]['loan_balance']
            prepayment_amount = previous_balance * prepayment_rate
            scheduled_amortization = previous_balance / (self.inputs['averageLifeLoans'] * 12.0)
            new_balance = previous_balance - prepayment_amount - scheduled_amortization + monthly_production
            return {
                'monthly_production': monthly_production,
                'prepayment_amount': prepayment_amount,
                'scheduled_amortization': scheduled_amortization,
                'new_balance': new_balance
            }


    def _calculate_line_balance(self, i, df):
        """Calculate line balance considering production, utilization, and prepayments."""
        date = df.index[i]
        if date < self.first_production_date:
            return {
                'monthly_production': 0.0,
                'prepayment_amount': 0.0,
                'utilization_production': 0.0,
                'new_balance': 0.0
            }
        
        months_since_production = (date.year - self.first_production_date.year) * 12 + (date.month - self.first_production_date.month)
        year = min(months_since_production // 12, 4)
        monthly_production = self.inputs['annualProduction'][year]['loans'] * self.inputs['loanVsLinePercentage'] / (100 - self.inputs['loanVsLinePercentage']) / 12.0
        utilization_rate = self.inputs['lineUtilizationPercentage'] 
        prepayment_rate = self.inputs['prepayPercentageOfBalance'] / 12.0 
        
        if i == 0 or df.index[i-1] < self.first_production_date:
            utilization_production = monthly_production * utilization_rate
            return {
                'monthly_production': monthly_production,
                'prepayment_amount': 0.0,
                'utilization_production': utilization_production,
                'new_balance': utilization_production
            }
        else:
            previous_balance = df.iloc[i-1]['line_balance']
            prepayment_amount = previous_balance * prepayment_rate
            utilization_production = monthly_production * utilization_rate
            new_balance = previous_balance - prepayment_amount + utilization_production
            return {
                'monthly_production': monthly_production,
                'prepayment_amount': prepayment_amount,
                'utilization_production': utilization_production,
                'new_balance': new_balance
            }


    def _calculate_deposit_balance(self, i, df):
        """Calculate deposit balance based on monthly production."""
        date = df.index[i]
        if date < self.first_production_date:
            return 0.0
        
        months_since_production = (date.year - self.first_production_date.year) * 12 + (date.month - self.first_production_date.month)
        year = min(months_since_production // 12, 4)
        monthly_production = self.inputs['annualProduction'][year]['deposits'] / 12.0
        
        if i == 0 or df.index[i-1] < self.first_production_date:
            return monthly_production
        else:
            previous_balance = df.iloc[i-1]['deposit_balance']
            return previous_balance + monthly_production


    def _calculate_interest_expense(self, i, df):
        """Calculate interest expense on deposits."""
        date = df.index[i]
        if date < self.first_production_date:
            return 0.0
        
        months_since_production = (date.year - self.first_production_date.year) * 12 + (date.month - self.first_production_date.month)
        year = min(months_since_production // 12, 4)
        deposit_yield = self.inputs['goingOnYields'][year]['deposits'] / 100.0 / 12.0
        return df.iloc[i]['deposit_balance'] * deposit_yield


    def _calculate_provision_expense(self, i, df):
        """Calculate loan loss provision expense (simplified version)."""
        date = df.index[i]
        if date < self.first_production_date:
            return 0.0
        
        months_since_production = (date.year - self.first_production_date.year) * 12 + (date.month - self.first_production_date.month)
        year = min(months_since_production // 12, 4)
        monthly_loan_production = self.inputs['annualProduction'][year]['loans'] / 12.0
        provision_rate = 0.01  # 1% provision rate, adjust as needed
        # Additional market-based adjustment could be implemented here
        return monthly_loan_production * provision_rate


    def calculate_pro_forma(self):
        """Main method to calculate pro forma financials."""
        try:
            logger.info("Starting pro forma calculation")
            monthly_schedule = self._generate_monthly_schedule()
            annual_summary = self._generate_annual_summary(monthly_schedule)
            
            # Ensure the index is datetime
            monthly_schedule.index = pd.to_datetime(monthly_schedule.index)
            annual_summary.index = pd.to_datetime(annual_summary.index)
            
            cumulative_payback = self._calculate_cumulative_payback(monthly_schedule)
            logger.info(f"Calculated cumulative payback: {cumulative_payback}")

            # Calculate the payback date
            if cumulative_payback is not None:
                start_date = monthly_schedule.index[0]
                payback_date = start_date + pd.Timedelta(days=int(cumulative_payback * 365.25))
                logger.info(f"Payback achieved on: {payback_date.strftime('%b %Y')}")

            # Calculate total metrics for the entire period
            total_metrics = {
                # Sum metrics
                'total_interest_income_loans': annual_summary['interest_income_loans'].sum(),
                'total_interest_income_lines': annual_summary['interest_income_lines'].sum(),
                'total_interest_income': (annual_summary['interest_income_loans'].sum() + 
                                        annual_summary['interest_income_lines'].sum() + 
                                        annual_summary['origination_fees'].sum()),  # Include amortized origination fees
                'total_interest_expense': annual_summary['interest_expense'].sum(),
                'total_non_interest_income': annual_summary['non_interest_income'].sum(),
                'total_non_interest_expense': annual_summary['non_interest_expense'].sum(),
                'total_provision_expense': annual_summary['provision_expense'].sum(),
                'total_net_income': annual_summary['net_income'].sum(),
                'total_salary_expense': annual_summary['salary_expense'].sum(),
                'total_incentive_compensation_expense': annual_summary['incentive_compensation_expense'].sum(),
                'total_benefits_expense': annual_summary['benefits_expense'].sum(),
                'total_discretionary_expense': annual_summary['discretionary_expense'].sum(),
                'total_origination_fees': annual_summary['origination_fees'].sum(),
                'total_unused_commitment_fees': annual_summary['unused_commitment_fees'].sum(),
                'total_deferred_origination_fees': annual_summary['deferred_origination_fees'].iloc[-1],  # Last value
                'total_amortized_origination_fees': annual_summary['origination_fees'].sum(),

                # Average metrics
                'average_loan_balance': annual_summary['loan_balance'].mean(),
                'average_line_balance': annual_summary['line_balance'].mean(),
                'average_deposit_balance': annual_summary['deposit_balance'].mean(),
                'average_total_assets': (
                    annual_summary['loan_balance'].mean() + 
                    annual_summary['line_balance'].mean() + 
                    annual_summary['deferred_costs'].mean() - 
                    annual_summary['deferred_origination_fees'].mean()
                ),
                'average_total_liabilities': annual_summary['total_liabilities'].mean(),
                'average_total_equity': annual_summary['total_equity'].mean(),
                'average_efficiency_ratio': annual_summary['efficiency_ratio'].mean(),

                # Calculated metrics
                'total_revenue': (annual_summary['interest_income_loans'].sum() + 
                                 annual_summary['interest_income_lines'].sum() + 
                                 annual_summary['origination_fees'].sum() + 
                                 annual_summary['non_interest_income'].sum()),
                'net_interest_margin': ((annual_summary['interest_income_loans'].sum() + 
                                         annual_summary['interest_income_lines'].sum() + 
                                         annual_summary['origination_fees'].sum() - 
                                         annual_summary['interest_expense'].sum()) / 
                                        annual_summary['total_assets'].mean()),
                'return_on_average_assets': (annual_summary['net_income'].sum() / 
                                             annual_summary['total_assets'].mean()),
                'return_on_average_equity': (annual_summary['net_income'].sum() / 
                                             annual_summary['total_equity'].mean()),
            }

            # Calculate AAGR for net_income
            try:
                net_income_values = annual_summary['net_income']
                annual_growth_rates = [(net_income_values[i] - net_income_values[i-1]) / net_income_values[i-1] 
                                       for i in range(1, len(net_income_values)) if net_income_values[i-1] != 0]
                aagr = np.mean(annual_growth_rates) if annual_growth_rates else 0.0
                total_metrics['net_income_aagr'] = aagr
                logger.debug(f"AAGR for net_income: {aagr}")
            except Exception as e:
                logger.error(f"Error calculating AAGR for net_income: {str(e)}")
                total_metrics['net_income_aagr'] = 0.0

            # Log the monthly schedule
            logger.info(f"Monthly Schedule: {monthly_schedule.to_dict()}")

            # Log the annual summary
            logger.info(f"Annual Summary: {annual_summary.to_dict()}")

            # Log the total metrics
            logger.info(f"Total Metrics: {total_metrics}")

            # Log the cumulative payback
            logger.info(f"Cumulative Payback: {cumulative_payback}")

            # Add yield curve data to the results
            yield_curve_data = {}
            for date_key, curve in self.yield_curves.items():
                tenors = [0.25, 0.5, 1, 2, 3, 5, 10, 30]  # Assuming these are the tenors used
                rates = [curve.get_rate(tenor) for tenor in tenors]
                yield_curve_data[date_key.strftime('%Y-%m-%dT%H:%M:%SZ')] = dict(zip(tenors, rates))

            # Update total metrics to include deferred costs
            total_metrics['total_deferred_costs'] = annual_summary['deferred_costs'].iloc[-1]
            total_metrics['total_deferred_cost_amortization'] = annual_summary['deferred_cost_amortization'].sum()
            total_metrics['total_indirect_costs'] = annual_summary['indirect_costs'].sum()

            logger.info("Pro forma calculation completed successfully")
            
            # Create the final results dictionary
            final_results = {
                'monthlySchedule': monthly_schedule.reset_index().rename(columns={'index': 'index'}).to_dict(orient='records'),
                'annualSummary': annual_summary.reset_index().rename(columns={'index': 'index'}).to_dict(orient='records'),
                'totalMetrics': total_metrics,
                'cumulativePayback': cumulative_payback,
                'yieldCurves': yield_curve_data
            }
            
            # Convert datetime index to ISO 8601 strings
            monthly_schedule.index = monthly_schedule.index.strftime('%Y-%m-%dT%H:%M:%SZ')
            annual_summary.index = annual_summary.index.strftime('%Y-%m-%dT%H:%M:%SZ')

            # Convert dates in yieldCurves to ISO 8601 format
            final_results['yieldCurves'] = {
                datetime.strptime(date, '%Y-%m-%dT%H:%M:%SZ').strftime('%Y-%m-%dT%H:%M:%SZ'): rates
                for date, rates in final_results['yieldCurves'].items()
            }

            # Ensure all values are JSON serializable and handle NaN
            def json_serial(obj):
                if isinstance(obj, (datetime, pd.Timestamp)):
                    return obj.strftime('%Y-%m-%dT%H:%M:%SZ')
                elif isinstance(obj, float):
                    if np.isnan(obj):
                        return None
                    return obj
                elif isinstance(obj, (int, str, dict, list)):
                    return obj
                else:
                    raise TypeError(f"Type {type(obj)} not serializable")

            final_results = json.loads(json.dumps(final_results, default=json_serial))

            logger.debug(f"Calculation results: {final_results}")
            
            return final_results
            
        except ValueError as ve:
            logger.error(f"Validation error in calculate_pro_forma: {str(ve)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise ValueError(f"Validation error: {str(ve)}")
        except Exception as e:
            logger.error(f"Unexpected error in calculate_pro_forma: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise ValueError(f"An unexpected error occurred: {str(e)}")    

    def _generate_annual_summary(self, monthly_schedule):
        """Generate annual summary from monthly schedule."""
        annual_summary = monthly_schedule.resample('A').sum()
        return annual_summary

    def _calculate_cumulative_payback(self, monthly_schedule):
        """Calculate cumulative payback period."""
        cumulative_net = monthly_schedule['net_income'].cumsum()
        break_even = cumulative_net[cumulative_net >= 0].first_valid_index()
        if break_even:
            delta = break_even - monthly_schedule.index[0]
            return delta.days / 365.25  # Approximate years
        return None

def calculate_pro_forma(inputs):
    """Main function to calculate RM Pro Forma financials."""
    try:
        logger.info("Starting pro forma calculation")
        logger.info(f"Received inputs: {inputs}")
        
        logger.debug("Initializing RMProFormaModel")
        model = RMProFormaModel(inputs)
        
        logger.debug("Calling calculate_pro_forma method")
        results = model.calculate_pro_forma()
        
        logger.debug("Processing calculation results")
        # Convert numpy arrays and pandas objects to Python native types for JSON serialization
        for key in ['monthlySchedule', 'annualSummary']:
            results[key] = [
                {k: (v if not isinstance(v, (float, int)) or not np.isnan(v) else None) for k, v in row.items()}
                for row in results[key]
            ]
        
        # Ensure yield curve data is JSON serializable
        results['yieldCurves'] = {
            k: {str(tenor): float(rate) for tenor, rate in v.items()} 
            for k, v in results['yieldCurves'].items()
        }
        
        logger.info("Pro forma calculation completed successfully")
        logger.debug(f"Calculation results: {results}")
        
        return results
    except ValueError as ve:
        logger.error(f"Validation error in calculate_pro_forma: {str(ve)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise ValueError(f"Validation error: {str(ve)}")
    except Exception as e:
        logger.error(f"Unexpected error in calculate_pro_forma: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise ValueError(f"An unexpected error occurred: {str(e)}")
    

__all__ = ['calculate_pro_forma']

# Example usage:
# result = calculate_pro_forma(inputs)
# print(result)