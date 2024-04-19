from pyomo.environ import *
from pyomo.opt import SolverFactory
from flask import Flask, request, jsonify
from flask_cors import CORS
# npx create-react-app optimization-frontend
# cd optimization-frontend


app = Flask(__name__)
# You would need to install Flask-CORS using pip: pip install flask-cors
CORS(app)


# Model setup
def run_optimization(sms_usage_input, voice_usage_input, budget_input):
    model = ConcreteModel()

    # Parameters for SMS Pricing
    sms_tiers = {
        1: {'min_messages': 1, 'max_messages': 150000, 'price_outbound': 0.0079, 'price_inbound': 0.0079},
        2: {'min_messages': 150001, 'max_messages': 300000, 'price_outbound': 0.0077, 'price_inbound': 0.0077},
        3: {'min_messages': 300001, 'max_messages': 500000, 'price_outbound': 0.0075, 'price_inbound': 0.0075},
        4: {'min_messages': 500001, 'max_messages': 750000, 'price_outbound': 0.0073, 'price_inbound': 0.0073},
        5: {'min_messages': 750001, 'max_messages': 1000000, 'price_outbound': 0.0071, 'price_inbound': 0.0071},
        6: {'min_messages': 1000001, 'max_messages': float('inf'), 'price_outbound': 0.0069, 'price_inbound': 0.0069},
    }

    # Decision Variables for SMS Tiers
    model.sms_usage = Var(sms_tiers.keys(), domain=NonNegativeIntegers, bounds=(0, None))
    model.use_committed_sms = Var(domain=Binary)
    committed_sms_discount = 0.95  # Example: 5% discount
    
    

    # Phone Number Pricing
    phone_number_pricing = {
        'long_codes': {'monthly_cost': 1.15, 'setup_fee': 0},
        'toll_free': {'monthly_cost': 2.15, 'setup_fee': 0},
        'random_short_code': {'monthly_cost': 1000 / 3, 'setup_fee': 500},  # Quarterly costs converted to monthly
        'vanity_short_code': {'monthly_cost': 1500 / 3, 'setup_fee': 500},  # Quarterly costs converted to monthly
        'bring_your_own': {'monthly_cost': 0.5, 'setup_fee': 0},
    }
    # Decision Variables for Phone Numbers
    for phone_type in phone_number_pricing:
        model.add_component(f"{phone_type}_selected", Var(domain=Binary))
    # Phone Number Volume Discounts
    phone_number_volumes = {
        'long_code': {'threshold': 1000, 'cost_below_threshold': 1.15, 'cost_above_threshold': 0.575},
        'toll_free': {'threshold': 1000, 'cost_below_threshold': 2.15, 'cost_above_threshold': 1.63},
    }
    # Decision Variables for Phone Numbers Below and Above Threshold
    for phone_type, values in phone_number_volumes.items():
        model.add_component(f"{phone_type}_below_threshold", Var(domain=NonNegativeReals))
        model.add_component(f"{phone_type}_above_threshold", Var(domain=NonNegativeReals))

    # Parameters for Voice Calls
    regular_cost_per_voice = 0.014  # Rate for making/receiving calls
    committed_cost_per_voice = 0.01  # Committed-use rate for voice calls
    estimated_voice_usage = 50000  # Estimated monthly voice call minutes
    customer_budget = 800  # Customer's budget

    # Binary decision for Voice Call pricing
    model.use_committed_voice = Var(domain=Binary)

    # Example constraint for long codes - adjust similarly for toll-free numbers
    def long_code_threshold_constraint(model):
        return model.long_code_below_threshold <= phone_number_volumes['long_code']['threshold']

    model.long_code_threshold_constraint = Constraint(rule=long_code_threshold_constraint)


    # Objective Function: Minimize total cost including SMS and Voice Calls
    def total_cost_rule_updated(model):
        # Original SMS and voice costs
        sms_cost = sum(model.sms_usage[tier] * (sms_tiers[tier]['price_outbound'] * (committed_sms_discount if model.use_committed_sms == 1 else 1)) for tier in sms_tiers)
        voice_cost = (regular_cost_per_voice * (1 - model.use_committed_voice) + committed_cost_per_voice * model.use_committed_voice) * estimated_voice_usage
        
        # Update for phone number costs with volume discounts
        phone_number_cost = sum(
            getattr(model, f"{phone_type}_below_threshold") * values['cost_below_threshold'] +
            max(0, getattr(model, f"{phone_type}_above_threshold") - values['threshold']) * values['cost_above_threshold']
            for phone_type, values in phone_number_volumes.items()
        )
        
        return sms_cost + voice_cost + phone_number_cost


    model.total_cost = Objective(rule=total_cost_rule_updated, sense=minimize)


    # Constraints
    # Budget Constraint: Total cost must not exceed customer's budget
    def budget_constraint_rule(model):
        return model.total_cost.expr <= customer_budget

    model.budget_constraint = Constraint(rule=budget_constraint_rule)

    # Solver Setup and Execution
    solver = SolverFactory('glpk')
    solver.solve(model)

    # Output Decisions and Total Cost
    use_committed_decision_voice = value(model.use_committed_voice)
    total_cost_value = value(model.total_cost)

    print(f"Use Committed Pricing Decision for Voice Calls: {use_committed_decision_voice}")
    print(f"Total Cost: ${total_cost_value:.4f}")

    # Return a dictionary of results
    return {
        'use_committed_decision_voice': use_committed_decision_voice,
        'total_cost': total_cost_value,
    }

@app.route('/optimize', methods=['POST'])
def optimize():
    # Ensure you parse JSON data correctly
    data = request.json
    sms_usage = data.get('sms_usage')
    voice_usage = data.get('voice_usage')
    budget = data.get('budget')
    
    # Call the optimization function with parsed inputs
    results = run_optimization(sms_usage, voice_usage, budget)
    
    # Return the optimization results as JSON
    return jsonify(results)

if __name__ == '__main__':
    # Set debug to False for production
    app.run(debug=True)
