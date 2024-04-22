from flask import Flask, request, jsonify
from flask_cors import CORS
from pyomo.environ import ConcreteModel, Var, NonNegativeIntegers, Binary, Objective, minimize, Constraint, value
from pyomo.opt import SolverFactory
import os

# Initialize Flask application
app = Flask(__name__)
CORS(app)  # Enable CORS for all domains

# Home route for basic API check
@app.route('/')
def home():
    return "Welcome to the API!"

# Function to run the optimization model
def run_optimization(sms_usage, voice_usage, budget):
    model = ConcreteModel()

    # SMS pricing tiers
    sms_tiers = {
        1: {'min_messages': 1, 'max_messages': 150000, 'price_outbound': 0.0079, 'price_inbound': 0.0079},
        2: {'min_messages': 150001, 'max_messages': 300000, 'price_outbound': 0.0077, 'price_inbound': 0.0077},
        3: {'min_messages': 300001, 'max_messages': 500000, 'price_outbound': 0.0075, 'price_inbound': 0.0075},
        4: {'min_messages': 500001, 'max_messages': 750000, 'price_outbound': 0.0073, 'price_inbound': 0.0073},
        5: {'min_messages': 750001, 'max_messages': 1000000, 'price_outbound': 0.0071, 'price_inbound': 0.0071},
        6: {'min_messages': 1000001, 'max_messages': float('inf'), 'price_outbound': 0.0069, 'price_inbound': 0.0069}
    }

    # Decision variables for SMS usage
    model.sms_usage = Var(sms_tiers.keys(), domain=NonNegativeIntegers)
    model.use_committed_sms = Var(domain=Binary)
    committed_sms_discount = 0.95  # Discount factor for committing to SMS plans

    # Decision variables for voice
    regular_cost_per_voice = 0.014
    committed_cost_per_voice = 0.01
    model.voice_usage = voice_usage
    model.use_committed_voice = Var(domain=Binary)

    # Objective Function to minimize total cost
    def total_cost_rule(model):
        sms_cost = sum((model.sms_usage[tier] * sms_tiers[tier]['price_outbound'] * (1 - model.use_committed_sms) + 
                        model.sms_usage[tier] * sms_tiers[tier]['price_outbound'] * committed_sms_discount * model.use_committed_sms)
                       for tier in sms_tiers)
        voice_cost = (regular_cost_per_voice * (1 - model.use_committed_voice) + 
                      committed_cost_per_voice * model.use_committed_voice) * model.voice_usage
        return sms_cost + voice_cost
    model.total_cost = Objective(rule=total_cost_rule, sense=minimize)

    # Budget constraint
    model.budget_constraint = Constraint(expr=model.total_cost <= budget)

    # Solve the model
    solver = SolverFactory('glpk')
    solution = solver.solve(model, tee=True)

    # Output decisions and total cost
    results = {
        'use_committed_sms': value(model.use_committed_sms),
        'use_committed_voice': value(model.use_committed_voice),
        'total_cost': value(model.total_cost)
    }
    return results

@app.route('/optimize', methods=['GET', 'POST'])
def optimize():
    try:
        sms_usage = int(request.args.get('sms_usage', 0))
        voice_usage = int(request.args.get('voice_usage', 0))
        budget = float(request.args.get('budget', 0))

        if sms_usage < 0 or voice_usage < 0 or budget < 0:
            return jsonify({"error": "Negative values are not allowed."}), 400

        results = run_optimization(sms_usage, voice_usage, budget)
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
