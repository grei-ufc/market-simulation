from pyomo.environ import *
import numpy as np
import json
import pathlib

import pyutilib.subprocess.GlobalData
pyutilib.subprocess.GlobalData.DEFINE_SIGNAL_HANDLERS_DEFAULT = False

# ----------------------------------
# index sets
# ----------------------------------
PRICES_INDEX = range(24*4)
TIME_INDEX = range(24*4)

# ----------------------------------
# DATA
# ----------------------------------
path = str(pathlib.Path(__file__).parent.absolute())
with open(path + '/config.json', 'r') as f:
    CONFIG = json.load(f)

DEMAND = dict()
SPOT_PRICES = dict()
for i, j in CONFIG['scenarios'].items():
    data = {k: l for k, l in zip(TIME_INDEX, j['demand_data'])}
    DEMAND[i] = data

    data = {k: l for k, l in zip(TIME_INDEX, j['spot_price_data'])}
    SPOT_PRICES[i] = data

# ----------------------------------
# model definition
# ----------------------------------
model = ConcreteModel(name="A")

# ----------------------------------
# parameters of the model
# ----------------------------------
if CONFIG['has_storage']:
    model.max_p_charge = Param(initialize=CONFIG['max_energy_flow'])
    model.max_p_discharge = Param(initialize=CONFIG['max_energy_flow'])
    model.storage_size = Param(initialize=CONFIG['storage_size'])
    model.min_soc = Param(initialize=CONFIG['min_soc'])
    model.max_soc = Param(initialize=CONFIG['max_soc'])

model.bilateral_price = Param(initialize=CONFIG['bilateral_price'])

# ----------------------------------
# parameters with stochasticity
# ----------------------------------
model.spot_prices = Param(PRICES_INDEX,
                          initialize={i: j for i, j in zip(PRICES_INDEX, np.zeros(len(TIME_INDEX)))},
                          mutable=True)
model.demand = Param(TIME_INDEX,
                     initialize={i: j for i, j in zip(TIME_INDEX, np.zeros(len(TIME_INDEX)))},
                     mutable=True)


# ----------------------------------
# variables of the model
# ----------------------------------
if CONFIG['has_storage']:
    model.charging = Var(TIME_INDEX, within=Binary)
    model.discharging = Var(TIME_INDEX, within=Binary)
    model.p_charge = Var(TIME_INDEX,
                         initialize={i: j for i, j in zip(TIME_INDEX, np.zeros(len(TIME_INDEX)))},
                         domain=NonNegativeReals)
    model.p_discharge = Var(TIME_INDEX,
                            initialize={i: j for i, j in zip(TIME_INDEX, np.zeros(len(TIME_INDEX)))},
                            domain=NonNegativeReals)
    model.soc = Var(TIME_INDEX, domain=NonNegativeReals, bounds=(model.min_soc, model.max_soc))

model.p_bilateral = Var(TIME_INDEX,
                        initialize={i: j for i, j in zip(TIME_INDEX, np.zeros(len(TIME_INDEX)))},
                        domain=NonNegativeReals,
                        bounds=(0.0, CONFIG['bilateral_max']))

model.p_spot = Var(TIME_INDEX,
                   initialize={i: j for i, j in zip(TIME_INDEX, np.zeros(len(TIME_INDEX)))},
                   domain=Reals)

# ----------------------------------
# objctive function model
# ----------------------------------
def obj_rule(model):
    custo = dict()
    aux = list()
    dt = 0.25  # 15 min
    for t in TIME_INDEX:
        custo[t] = model.p_bilateral[t] * model.bilateral_price +\
         model.p_spot[t] * model.spot_prices[t]
        aux.append(custo[t] * dt)
    aux = sum(aux)
    return aux

model.obj = Objective(rule=obj_rule, sense=minimize)

# ----------------------------------
# constraints of the model
# ----------------------------------
def balance_energy_constraint(model, t):
    aux1 = model.p_bilateral[t] + model.p_spot[t]
    if CONFIG['has_storage']:
        aux2 = model.demand[t] + (model.p_charge[t] - model.p_discharge[t])
    else:
        aux2 = model.demand[t]

    # a restrição definida aqui estabelece que:
    # 1) caso a demanda liquida seja positiva, ou seja, o consumo supere a producao,
    #    o prosumidor precisa garantir o balanço energético por meio da compra
    #    de energia no mercado bilateral e no mercado de tempo real.
    # 2) caso a demanda liquida seja negativa, ou seja a prosução supere o consumo,
    #    o prosumidor precisa garantir que o excesso de energia seja ou armazenado
    #    ou vendido no mercado de tempo real.
    if value(aux2) >= 0.0:      # consumo maior que producao
        return aux1 >= aux2
    else:                       # carga menor que producao
        return model.p_spot[t] >= aux2

model.balance_energy_constraint = Constraint(TIME_INDEX, rule=balance_energy_constraint)

def spot_energy_rule_constraint(model, t):

    # a restrição definida aqui estabelece que:
    # não é possível ao prosumidor a venda de energia no mercado de tempo real
    # da energia que foi adquirida no mercado de contratação bilateral.
    if CONFIG['has_storage']:
        aux = model.demand[t] + (model.p_charge[t] - model.p_discharge[t])
    else:
        aux = model.demand[t]

    if value(aux) >= 0.0:  # consumo maior que producao
        return model.p_spot[t] >= 0
    else:                   # carga menor que producao
        return model.p_spot[t] <= 0

model.spot_energy_rule_constraint = Constraint(TIME_INDEX, rule=spot_energy_rule_constraint)

if CONFIG['has_storage']:
    def charging_discharging_energy_constraint(model, t):
        return model.charging[t] + model.discharging[t] <= 1

    model.charge_discharge_energy_constraint = Constraint(TIME_INDEX, rule=charging_discharging_energy_constraint)

    def max_charge_rate_constraint(model, t):
        return model.p_charge[t] <= model.charging[t] * model.max_p_charge

    model.max_charge_rate_constraint = Constraint(TIME_INDEX, rule=max_charge_rate_constraint)

    def max_discharge_rate_constraint(model, t):
        return model.p_discharge[t] <= model.discharging[t] * model.max_p_discharge

    model.max_discharge_rate_constraint = Constraint(TIME_INDEX, rule=max_discharge_rate_constraint)

    model.init_soc_constraint = Constraint(expr=model.soc[0] == 0.2 * model.max_soc)

    model.soc_memory_constraint = ConstraintList()
    for t_m, t in zip(TIME_INDEX[:-1], TIME_INDEX[1:]):
        expr = model.soc[t_m] + (model.p_charge[t_m] - model.p_discharge[t_m]) * 0.25
        model.soc_memory_constraint.add(model.soc[t] == expr)

    charging = CONFIG.get('fixed_charging_states')
    if charging is not None:
        model.charging_fixed_states_constraint = ConstraintList()
        for t in charging:
            model.charging_fixed_states_constraint.add(model.p_charge[t] == model.max_p_charge)

    discharging = CONFIG.get('fixed_discharging_states')
    if discharging is not None:
        model.discharging_fixed_states_constraint = ConstraintList()
        for t in discharging:
            model.discharging_fixed_states_constraint.add(model.p_discharge[t] == model.max_p_discharge)

#
# Stage-specific cost computations
#

def ComputeStageCost_rule(model):
    return model.bilateral_price

model.StageCost = Expression(rule=ComputeStageCost_rule)


# ----------------------------------
# Solving the model
# ----------------------------------
# solver = SolverFactory('cplex')
# results = solver.solve(model)
# if (results.solver.status == SolverStatus.ok) and (results.solver.termination_condition == TerminationCondition.optimal):
#     print ("this is feasible and optimal")
# elif results.solver.termination_condition == TerminationCondition.infeasible:
#     print ("do something about it? or exit?")
# else:
#     # something else is wrong
#     print (str(results.solver))


def pysp_instance_creation_callback(scenario_name, node_names):
    instance = model.clone()
    instance.demand.store_values(DEMAND[scenario_name])
    instance.spot_prices.store_values(SPOT_PRICES[scenario_name])
    instance.balance_energy_constraint.reconstruct()
    instance.spot_energy_rule_constraint.reconstruct()
    return instance
