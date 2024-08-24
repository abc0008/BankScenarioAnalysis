import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from scipy import interpolate
import logging
import traceback  # Add this import

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
        self.rm_hire_date = datetime.strptime(self.inputs['rmHireDate'], '%Y-%m-%d')
        self.first_production_date = datetime.strptime(self.inputs['firstProductionDate'], '%Y-%m-%d')
        self.end_date = self.first_production_date + timedelta(days=30*60)  # 5 years from first production
        self.dates = pd.date_range(start=self.rm_hire_date, end=self.end_date, freq='MS')
        self.yield_curves = self._initialize_yield_curves()
        self.incentive_compensation_percentage = self.inputs['incentiveCompensationPercentage']

    def validate_inputs(self):
        """Validate that all required input fields are present."""
        required_fields = ['rmHireDate', 'firstProductionDate', 'annualProduction', 'loanVsLinePercentage', 
                           'goingOnYields', 'lineUtilizationPercentage', 'originationFeePercentage', 
                           'unusedCommitmentFeePercentage', 'salary', 'annualMeritIncrease',
                           'discretionaryExpenses', 'deferredCostsPerLoan', 'averageLifeLoans', 
                           'averageLifeLines', 'prepayPercentageOfBalance', 'incentiveCompensationPercentage',
                           'avgLoanExposureAtOrigination'  # Add this new field
                           ]
        for field in required_fields:
            if field not in self.inputs:
                raise ValueError(f"Missing required input: {field}")
        
        # Validate dates
        try:
            rm_hire_date = datetime.strptime(self.inputs['rmHireDate'], '%Y-%m-%d')
            first_production_date = datetime.strptime(self.inputs['firstProductionDate'], '%Y-%m-%d')
            if first_production_date < rm_hire_date:
                raise ValueError("First Production Date cannot be earlier than RM Hire Date")
        except ValueError as e:
            raise ValueError(f"Invalid date format or value: {str(e)}")
        
        # Convert percentage inputs to floats
        percentage_fields = ['loanVsLinePercentage', 'lineUtilizationPercentage', 'originationFeePercentage', 
                             'unusedCommitmentFeePercentage', 'annualMeritIncrease', 'prepayPercentageOfBalance', 'incentiveCompensationPercentage']
        for field in percentage_fields:
            self.inputs[field] = float(self.inputs[field])
        
        # Convert nested structures
        self.inputs['annualProduction'] = [
            {'loans': float(year['loans']), 'deposits': float(year['deposits'])} 
            for year in self.inputs['annualProduction']
        ]
        self.inputs['goingOnYields'] = [
            {'loans': float(year['loans']), 'lines': float(year['lines']), 'deposits': float(year['deposits'])} 
            for year in self.inputs['goingOnYields']
        ]

    def _initialize_yield_curves(self):
        """Initialize yield curves for each year based on input rates."""
        tenors = [0.25, 0.5, 1, 2, 3, 5, 10, 30]
        base_rates = [0.01, 0.015, 0.02, 0.025, 0.03, 0.035, 0.04, 0.045]
        yield_curves = {}
        for year in range(5):
            year_start = self.first_production_date + timedelta(days=365*year)
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
            'deferred_origination_fees'
        ])
        
        for i, date in enumerate(self.dates):
            try:
                year = (date - self.first_production_date).days // 365
                month = (date - self.first_production_date).days // 30 + 1

                # Calculate expenses from RM Hire Date
                if date >= self.rm_hire_date:
                    months_since_hire = (date - self.rm_hire_date).days // 30
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
                    
                    df.loc[date, 'deferred_origination_fees'], df.loc[date, 'origination_fees'] = self._calculate_origination_fees(i, df)
                    df.loc[date, 'unused_commitment_fees'] = self._calculate_unused_commitment_fees(i, df)
                    df.loc[date, 'non_interest_income'] = df.loc[date, 'origination_fees'] + df.loc[date, 'unused_commitment_fees']
                    
                    df.loc[date, 'provision_expense'] = self._calculate_provision_expense(i, df)
                    df.loc[date, 'fas91_balance'] = self._calculate_fas91_balance(i, df)
                else:
                    # Initialize all balance sheet and income statement items to 0 for dates before first production
                    for col in df.columns:
                        if col not in ['salary_expense', 'benefits_expense', 'discretionary_expense']:
                            df.loc[date, col] = 0

                df.loc[date, 'non_interest_expense'] = (
                    df.loc[date, 'salary_expense'] +
                    df.loc[date, 'benefits_expense'] +
                    df.loc[date, 'incentive_compensation_expense'] +
                    df.loc[date, 'discretionary_expense']
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
                
                df.loc[date, 'total_assets'] = df.loc[date, 'loan_balance'] + df.loc[date, 'line_balance']
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
            return 0
        
        months_since_production = (date - self.first_production_date).days // 30
        year = min(months_since_production // 12, 4)
        
        # Find the most recent yield curve date
        yield_curve_date = max(d for d in self.yield_curves.keys() if d <= date)
        yield_curve = self.yield_curves[yield_curve_date]
        loan_yield = yield_curve.get_rate(self.inputs['averageLifeLoans']) / 12
        
        return df.iloc[i]['loan_balance'] * loan_yield

    def _calculate_interest_income_lines(self, i, df):
        """Calculate interest income for lines."""
        date = df.index[i]
        if date < self.first_production_date:
            return 0
        
        months_since_production = (date - self.first_production_date).days // 30
        year = min(months_since_production // 12, 4)
        
        # Find the most recent yield curve date
        yield_curve_date = max(d for d in self.yield_curves.keys() if d <= date)
        yield_curve = self.yield_curves[yield_curve_date]
        line_yield = yield_curve.get_rate(self.inputs['averageLifeLines']) / 12
        
        return df.iloc[i]['line_balance'] * line_yield

    def _calculate_origination_fees(self, i, df):
        """Calculate origination fees, considering deferral, amortization, and prepayments."""
        date = df.index[i]
        if date < self.first_production_date:
            return 0, 0  # Return 0 for both new fees and recognized income
        
        months_since_production = (date - self.first_production_date).days // 30
        year = min(months_since_production // 12, 4)
        
        # Calculate new origination fees
        monthly_loan_production = self.inputs['annualProduction'][year]['loans'] / 12
        monthly_line_production = monthly_loan_production * self.inputs['loanVsLinePercentage'] / (100 - self.inputs['loanVsLinePercentage'])
        new_origination_fees = (monthly_loan_production + monthly_line_production) * self.inputs['originationFeePercentage'] / 100
        
        # Get previous deferred balance
        if i == 0 or df.index[i-1] < self.first_production_date:
            previous_deferred_balance = 0
            previous_loan_balance = 0
        else:
            previous_deferred_balance = df.iloc[i-1]['deferred_origination_fees']
            previous_loan_balance = df.iloc[i-1]['loan_balance'] + df.iloc[i-1]['line_balance']
        
        # Calculate regular amortization
        regular_amortization = previous_deferred_balance / (self.inputs['averageLifeLoans'] * 12)
        
        # Calculate prepayment-related amortization
        prepayment_rate = self.inputs['prepayPercentageOfBalance'] / 12
        prepayment_amount = previous_loan_balance * prepayment_rate
        prepayment_amortization = (prepayment_amount / previous_loan_balance) * previous_deferred_balance if previous_loan_balance > 0 else 0
        
        # Total amortization
        total_amortization = regular_amortization + prepayment_amortization
        
        # Calculate new deferred balance
        new_deferred_balance = previous_deferred_balance + new_origination_fees - total_amortization
        
        # Return new deferred balance and recognized income (total amortization)
        return new_deferred_balance, total_amortization

    def _calculate_unused_commitment_fees(self, i, df):
        """Calculate unused commitment fees."""
        date = df.index[i]
        if date < self.first_production_date:
            return 0
        
        months_since_production = (date - self.first_production_date).days // 30
        year = min(months_since_production // 12, 4)
        
        monthly_line_production = self.inputs['annualProduction'][year]['loans'] * self.inputs['loanVsLinePercentage'] / (100 - self.inputs['loanVsLinePercentage']) / 12
        unused_balance = monthly_line_production * (1 - self.inputs['lineUtilizationPercentage'] / 100)
        return unused_balance * self.inputs['unusedCommitmentFeePercentage'] / 100






    def _calculate_salary_expense(self, months_since_hire):
        """Calculate salary expense based on RM Hire Date."""
        years_since_hire = months_since_hire // 12
        base_salary = self.inputs['salary'] * (1 + self.inputs['annualMeritIncrease']) ** years_since_hire
        return base_salary / 12

    

    def _calculate_loan_balance(self, i, df):
        """Calculate loan balance considering production and prepayments."""
        date = df.index[i]
        if date < self.first_production_date:
            return {
                'monthly_production': 0,
                'prepayment_amount': 0,
                'scheduled_amortization': 0,
                'new_balance': 0
            }
        
        months_since_production = (date - self.first_production_date).days // 30
        year = months_since_production // 12
        monthly_production = self.inputs['annualProduction'][min(year, 4)]['loans'] / 12
        prepayment_rate = self.inputs['prepayPercentageOfBalance'] / 12
        
        if i == 0 or df.index[i-1] < self.first_production_date:
            return {
                'monthly_production': monthly_production,
                'prepayment_amount': 0,
                'scheduled_amortization': 0,
                'new_balance': monthly_production
            }
        else:
            previous_balance = df.iloc[i-1]['loan_balance']
            prepayment_amount = previous_balance * prepayment_rate
            scheduled_amortization = previous_balance / (self.inputs['averageLifeLoans'] * 12)
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
                'monthly_production': 0,
                'prepayment_amount': 0,
                'utilization_production': 0,
                'new_balance': 0
            }
        
        months_since_production = (date - self.first_production_date).days // 30
        year = months_since_production // 12
        monthly_production = self.inputs['annualProduction'][min(year, 4)]['loans'] * self.inputs['loanVsLinePercentage'] / (100 - self.inputs['loanVsLinePercentage']) / 12
        utilization_rate = self.inputs['lineUtilizationPercentage'] 
        prepayment_rate = self.inputs['prepayPercentageOfBalance'] / 12 
        
        if i == 0 or df.index[i-1] < self.first_production_date:
            utilization_production = monthly_production * utilization_rate
            return {
                'monthly_production': monthly_production,
                'prepayment_amount': 0,
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
            return 0
        
        months_since_production = (date - self.first_production_date).days // 30
        year = months_since_production // 12
        monthly_production = self.inputs['annualProduction'][min(year, 4)]['deposits'] / 12
        
        if i == 0 or df.index[i-1] < self.first_production_date:
            return monthly_production
        else:
            previous_balance = df.iloc[i-1]['deposit_balance']
            return previous_balance + monthly_production
        

        ##ISSUE HERE BELOW

    def _calculate_interest_expense(self, i, df):
        """Calculate interest expense on deposits."""
        date = df.index[i]
        if date < self.first_production_date:
            return 0
        
        months_since_production = (date - self.first_production_date).days // 30
        year = min(months_since_production // 12, 4)
        deposit_yield = self.inputs['goingOnYields'][year]['deposits'] / 100 / 12
        return df.iloc[i]['deposit_balance'] * deposit_yield

    def _calculate_non_interest_expense(self, i, df):
        """Calculate non-interest expenses including salary, benefits, and other costs."""
        date = df.index[i]
        monthly_salary = df.iloc[i]['salary_expense']
        fringe_benefits = monthly_salary * 0.28
        monthly_discretionary = self.inputs['discretionaryExpenses'] / 12
        
        if date < self.first_production_date:
            return monthly_salary + fringe_benefits + monthly_discretionary
        
        months_since_production = (date - self.first_production_date).days // 30
        year = min(months_since_production // 12, 4)
        monthly_loan_production = self.inputs['annualProduction'][year]['loans'] / 12
        monthly_line_production = monthly_loan_production * self.inputs['loanVsLinePercentage'] / (100 - self.inputs['loanVsLinePercentage'])
        
        # Calculate indirect costs
        total_production = monthly_loan_production + monthly_line_production
        indirect_costs = (total_production / self.inputs['avgLoanExposureAtOrigination']) * 1000
        
        return monthly_salary + fringe_benefits + monthly_discretionary + indirect_costs

    def _calculate_provision_expense(self, i, df):
        """Calculate loan loss provision expense (simplified version)."""
        date = df.index[i]
        if date < self.first_production_date:
            return 0
        
        months_since_production = (date - self.first_production_date).days // 30
        year = min(months_since_production // 12, 4)
        monthly_loan_production = self.inputs['annualProduction'][year]['loans'] / 12
        provision_rate = 0.01  # 1% provision rate, adjust as needed
        # Additional market-based adjustment could be implemented here
        return monthly_loan_production * provision_rate

    def _calculate_fas91_balance(self, i, df):
        """Calculate FAS 91 balance considering new deferrals and amortization."""
        date = df.index[i]
        if date < self.first_production_date:
            return 0
        
        if i == 0 or df.index[i-1] < self.first_production_date:
            previous_balance = 0
        else:
            previous_balance = df.iloc[i-1]['fas91_balance']
        
        months_since_production = (date - self.first_production_date).days // 30
        year = min(months_since_production // 12, 4)
        monthly_loan_production = self.inputs['annualProduction'][year]['loans'] / 12
        monthly_line_production = monthly_loan_production * self.inputs['loanVsLinePercentage'] / (100 - self.inputs['loanVsLinePercentage'])
        
        # Calculate new FAS 91 balance
        total_production = monthly_loan_production + monthly_line_production
        new_fas91 = (total_production / self.inputs['avgLoanExposureAtOrigination']) * self.inputs['deferredCostsPerLoan']
        
        amortization = previous_balance / (self.inputs['averageLifeLoans'] * 12)
        
        return previous_balance + new_fas91 - amortization


        #ISSUE HERE ENDs



    def _generate_annual_summary(self, monthly_schedule):
        """Generate annual summary from monthly schedule."""
        aggregation_dict = {}
        for column in monthly_schedule.columns:
            if column in ['loan_balance', 'line_balance', 'deposit_balance', 'total_assets', 'total_liabilities', 'total_equity']:
                aggregation_dict[column] = 'mean'
            elif column in ['efficiency_ratio']:
                aggregation_dict[column] = lambda x: x.mean() if len(x) > 0 else 0
            elif column == 'deferred_origination_fees':
                aggregation_dict[column] = 'last'  # Take the last value of the year
            else:
                aggregation_dict[column] = 'sum'

        annual_summary = monthly_schedule.resample('YE').agg(aggregation_dict)

        # Calculate additional metrics
        annual_summary['net_interest_margin'] = ((annual_summary['interest_income_loans'] + 
                                                 annual_summary['interest_income_lines'] + 
                                                 annual_summary['origination_fees'] - 
                                                 annual_summary['interest_expense']) / 
                                                annual_summary['total_assets'])
        annual_summary['return_on_average_assets'] = annual_summary['net_income'] / annual_summary['total_assets']
        annual_summary['return_on_average_equity'] = annual_summary['net_income'] / annual_summary['total_equity']

        return annual_summary
    
    def _calculate_cumulative_payback(self, monthly_schedule):
        """Calculate cumulative payback period based on monthly schedule."""
        logger.debug("Entering _calculate_cumulative_payback method")
        logger.debug(f"Monthly schedule shape: {monthly_schedule.shape}")

        cumulative_profit = monthly_schedule['cumulative_profit']
        logger.debug(f"Cumulative profit series head: \n{cumulative_profit.head()}")
        logger.debug(f"Cumulative profit series tail: \n{cumulative_profit.tail()}")

        if (cumulative_profit > 0).any():
            # Find the first positive cumulative profit
            first_positive_index = cumulative_profit[cumulative_profit > 0].index[0]
            previous_index = cumulative_profit.index[cumulative_profit.index.get_loc(first_positive_index) - 1]

            logger.debug(f"First positive cumulative profit at: {first_positive_index}")
            logger.debug(f"Previous month: {previous_index}")

            # Calculate the fraction of the month
            profit_at_positive = cumulative_profit[first_positive_index]
            profit_at_previous = cumulative_profit[previous_index]
            fraction = abs(profit_at_previous) / (profit_at_positive - profit_at_previous)

            logger.debug(f"Profit at positive: {profit_at_positive}")
            logger.debug(f"Profit at previous: {profit_at_previous}")
            logger.debug(f"Fraction of month: {fraction}")

            # Calculate time from start to payback point
            start_date = monthly_schedule.index[0]
            days_to_payback = (previous_index - start_date).days + (fraction * 30)  # Assuming 30 days per month
            years_from_start = days_to_payback / 365.25

            logger.debug(f"Start date: {start_date}")
            logger.debug(f"Days to payback: {days_to_payback}")
            logger.debug(f"Years from start to payback: {years_from_start}")

            return years_from_start
        else:
            logger.debug("No positive cumulative profit found")
            return None


         # Payback not achieved within the projection period



    def calculate_pro_forma(self):
        """Main method to calculate pro forma financials."""
        try:
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
                'average_total_assets': annual_summary['total_assets'].mean(),
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

            # Calculate compound annual growth rate (CAGR) for key metrics
            logger.debug(f"Annual summary index: {annual_summary.index}")
            logger.debug(f"Annual summary index type: {type(annual_summary.index)}")

            if len(annual_summary.index) < 2:
                logger.error("Not enough data points to calculate CAGR")
                return {
                    'monthlySchedule': monthly_schedule.reset_index().to_dict(orient='records'),
                    'annualSummary': annual_summary.reset_index().to_dict(orient='records'),
                    'totalMetrics': total_metrics,
                    'cumulativePayback': cumulative_payback
                }

            start_year = annual_summary.index[0]
            end_year = annual_summary.index[-1]
            logger.debug(f"Start year: {start_year}, Type: {type(start_year)}")
            logger.debug(f"End year: {end_year}, Type: {type(end_year)}")
            
            if isinstance(start_year, pd.Timestamp):
                start_year = start_year.year
            if isinstance(end_year, pd.Timestamp):
                end_year = end_year.year

            logger.debug(f"Processed start year: {start_year}, Type: {type(start_year)}")
            logger.debug(f"Processed end year: {end_year}, Type: {type(end_year)}")

            years = end_year - start_year
            logger.debug(f"Years: {years}")

            # Minimum time difference to calculate CAGR (e.g., 1 month)
            min_time_diff = 1/12


            for metric in ['loan_balance', 'line_balance', 'deposit_balance', 'total_assets', 'net_income']:
                try:
                    start_value = annual_summary[metric].iloc[0]
                    end_value = annual_summary[metric].iloc[-1]
                    
                    logger.debug(f"Calculating CAGR for {metric}")
                    logger.debug(f"Start value: {start_value}, End value: {end_value}")
                    
                    if years >= min_time_diff and start_value > 0:
                        cagr = (end_value / start_value) ** (1/years) - 1
                        total_metrics[f'{metric}_cagr'] = cagr
                        logger.debug(f"CAGR for {metric}: {cagr}")
                    else:
                        total_metrics[f'{metric}_cagr'] = 0
                        logger.warning(f"Unable to calculate meaningful CAGR for {metric}. Years: {years}, Start value: {start_value}")
                except Exception as e:
                    logger.error(f"Error calculating CAGR for {metric}: {str(e)}")
                    total_metrics[f'{metric}_cagr'] = 0

                    
            logger.info(f"Annual Summary: {annual_summary.to_dict()}")
            logger.info(f"Total Metrics: {total_metrics}")
            logger.info(f"Cumulative Payback: {cumulative_payback}")
            logger.info(f"Annual Summary: {annual_summary.to_dict()}")
            logger.info(f"Total Metrics: {total_metrics}")
            logger.info(f"Cumulative Payback: {cumulative_payback}")

            # Add yield curve data to the results
            yield_curve_data = {}
            for date, curve in self.yield_curves.items():
                tenors = [0.25, 0.5, 1, 2, 3, 5, 10, 30]  # Assuming these are the tenors used
                rates = [curve.get_rate(tenor) for tenor in tenors]
                yield_curve_data[date.strftime('%Y-%m-%d')] = dict(zip(tenors, rates))

            # Include FAS 91 balance in total metrics
            total_metrics['total_fas91_balance'] = annual_summary['fas91_balance'].iloc[-1]

            # Calculate net loan balance and net assets
            total_metrics['net_loan_balance'] = (
                total_metrics['average_loan_balance'] + 
                total_metrics['total_fas91_balance'] - 
                total_metrics['total_deferred_origination_fees']
            )
            total_metrics['net_assets'] = (
                total_metrics['average_total_assets'] + 
                total_metrics['total_fas91_balance'] - 
                total_metrics['total_deferred_origination_fees']
            )

            return {
                'monthlySchedule': monthly_schedule.reset_index().to_dict(orient='records'),
                'annualSummary': annual_summary.reset_index().to_dict(orient='records'),
                'totalMetrics': total_metrics,
                'cumulativePayback': cumulative_payback,
                'yieldCurves': yield_curve_data  # Add this line
            }
            
        except Exception as e:
            logger.error(f"Error in calculate_pro_forma: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

        
def calculate_pro_forma(inputs):
    """Main function to calculate RM Pro Forma financials."""
    try:
        logger.info(f"Received inputs: {inputs}")
        model = RMProFormaModel(inputs)
        results = model.calculate_pro_forma()
        
        # Convert numpy arrays and pandas objects to Python native types for JSON serialization
        for key in ['monthlySchedule', 'annualSummary']:
            results[key] = [
                {k: v.item() if hasattr(v, 'item') else v for k, v in row.items()}
                for row in results[key]
            ]
        
        # Ensure yield curve data is JSON serializable
        results['yieldCurves'] = {k: {str(tenor): float(rate) for tenor, rate in v.items()} 
                                  for k, v in results['yieldCurves'].items()}
        
        logger.info(f"Calculation results: {results}")
        
        return results
    except Exception as e:
        logger.error(f"Error in calculate_pro_forma: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise

# Example usage:
#result = calculate_pro_forma(inputs)
#print(result)