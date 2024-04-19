from flask import Flask, request, jsonify
from flask_cors import CORS
from pyomo.environ import *
from pyomo.opt import SolverFactory

app = Flask(__name__)
CORS(app)  # Enable Cross-Origin Resource Sharing

# Define the optimization model function
def run_optimization(sms_usage_input, voice_usage_input, budget_input):
    model = ConcreteModel()

    # Parameters for SMS Pricing
    sms_tiers = {
        1: {'min_messages': 1, 'max_messages': 150000, 'price_outbound': 0.0079, 'price_inbound': 0.0079},
        2: {'min_messages': 150001, 'max_messages': 300000, 'price_outbound': 0.0077, 'price_inbound': 0.0077},
        3: {'min_messages': 300001, 'max_messages': 500000, 'price_outbound': 0.0075, 'price_inbound': 0.0075},
        4: {'min_messages': 500001, 'max_messages': 750000, 'price_outbound': 0.0073, 'price_inbound': 0.0073},
        5: {'min_messages': 750001, 'max_messages': 1000000, 'price_outbound': 0.0071, 'price_inbound': 0.0071},
        6: {'min_messages': 1000001, 'max_messages': float('inf'), 'price_outbound': 0.0069, 'price_inbound': 0.0069}
    }

    # Decision Variables for SMS
    model.sms_usage = Var(sms_tiers.keys(), domain=NonNegativeIntegers)
    model.use_committed_sms = Var(domain=Binary)
    committed_sms_discount = 0.95

    # Phone Number Pricing
    phone_number_pricing = {
        'long_codes': {'monthly_cost': 1.15, 'setup_fee': 0},
        'toll_free': {'monthly_cost': 2.15, 'setup_fee': 0},
        'random_short_code': {'monthly_cost': 1000 / 3, 'setup_fee': 500},
        'vanity_short_code': {'monthly_cost': 1500 / 3, 'setup_fee': 500},
        'bring_your_own': {'monthly_cost': 0.5, 'setup_fee': 0}
    }

    # Decision Variables for Phone Numbers
    for phone_type in phone_number_pricing:
        model.add_component(f"{phone_type}_selected", Var(domain=Binary))

    # Parameters and Decision Variables for Voice Calls
    regular_cost_per_voice = 0.014
    committed_cost_per_voice = 0.01
    estimated_voice_usage = 50000  # Estimated usage in minutes
    customer_budget = 800  # Customer's budget
    model.use_committed_voice = Var(domain=Binary)

    # Objective Function: Minimize total cost
    def total_cost_rule(model):
        sms_cost = sum(model.sms_usage[tier] * (sms_tiers[tier]['price_outbound'] * (committed_sms_discount if model.use_committed_sms == 1 else 1)) for tier in sms_tiers)
        voice_cost = (regular_cost_per_voice * (1 - model.use_committed_voice) + committed_cost_per_voice * model.use_committed_voice) * estimated_voice_usage
        return sms_cost + voice_cost

    model.total_cost = Objective(rule=total_cost_rule, sense=minimize)

    # Budget Constraint
    def budget_constraint_rule(model):
        return model.total_cost.expr <= customer_budget
    model.budget_constraint = Constraint(rule=budget_constraint_rule)

    # Solver setup and execution
    solver = SolverFactory('glpk')
    result = solver.solve(model)

    # Output decisions and total cost
    use_committed_decision_voice = value(model.use_committed_voice)
    total_cost_value = value(model.total_cost)

    # Return results as a dictionary
    return {
        'use_committed_decision_voice': use_committed_decision_voice,
        'total_cost': total_cost_value
    }

# Define API endpoint
@app.route('/optimize', methods=['GET', 'POST'])
def optimize():
    try:
        if request.method == 'GET':
            sms_usage = int(request.args.get('sms_usage', 0))
            voice_usage = int(request.args.get('voice_usage', 0))
            budget = float(request.args.get('budget', 0))
        elif request.method == 'POST':
            sms_usage = int(request.form.get('sms_usage', 0))
            voice_usage = int(request.form.get('voice_usage', 0))
            budget = float(request.form.get('budget', 0))

        # You might want to add additional checks to ensure values are within a sensible range
        if sms_usage < 0 or voice_usage < 0 or budget < 0:
            raise ValueError("Negative values are not allowed.")

        results = run_optimization(sms_usage, voice_usage, budget)
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True)  # Set debug to False for production
