from pyomo.environ import *
import pandas as pd
import numpy as np
from random import randint, sample

from load_data import get_load_data, get_gen_data

import pyutilib.subprocess.GlobalData
pyutilib.subprocess.GlobalData.DEFINE_SIGNAL_HANDLERS_DEFAULT = False

# ----------------------------------
# index sets
# ----------------------------------
PRICES_INDEX = range(24*4)
TIME_INDEX = range(24*4)

def solve_the_model(config):
    # ----------------------------------
    # model definition
    # ----------------------------------
    model = ConcreteModel(name="A")

    # ----------------------------------
    # parameters of the model
    # ----------------------------------
    model.max_p_charge = Param(initialize=config['MAX_ENERGY_FLOW'])
    model.max_p_discharge = Param(initialize=config['MAX_ENERGY_FLOW'])
    model.storage_size = Param(initialize=config['STORAGE_SIZE'])
    model.prices = Param(PRICES_INDEX, initialize={i: j for i, j in zip(PRICES_INDEX, config['PRICES'])})
    model.load_ = Param(TIME_INDEX, initialize={i: j for i, j in zip(TIME_INDEX, config['LOAD'])})
    model.gen = Param(TIME_INDEX, initialize={i: j for i, j in zip(TIME_INDEX, config['GEN'])})
    model.min_soc = Param(initialize=config['MIN_SOC'])
    model.max_soc = Param(initialize=config['MAX_SOC'])

    # ----------------------------------
    # variables of the model
    # ----------------------------------

    model.charging = Var(TIME_INDEX, within=Binary)
    model.discharging = Var(TIME_INDEX, within=Binary)
    model.p_charge = Var(TIME_INDEX, domain=NonNegativeReals)
    model.p_discharge = Var(TIME_INDEX, domain=NonNegativeReals)
    model.soc = Var(TIME_INDEX, domain=NonNegativeReals, bounds=(model.min_soc, model.max_soc))
    # model.z_1 = Var(TIME_INDEX, domain=NonNegativeReals)
    # model.z_2 = Var(TIME_INDEX, domain=NonNegativeReals)
    # model.z_3 = Var(TIME_INDEX, domain=NonNegativeReals)
    # model.z_4 = Var(TIME_INDEX, domain=NonNegativeReals)

    # ----------------------------------
    # objective function of the model
    # ----------------------------------
    # def obj_rule(model):
    #     p_sell = dict()
    #     p_buy = dict()
    #     a = list()
    #     for t in TIME_INDEX:
    #         p_sell[t] = model.exp_energy[t] * (model.gen[t] - model.load_[t]) - model.z_1[t] + model.z_2[t]
    #
    #         p_buy[t] = model.imp_energy[t] * (model.gen[t] - model.load_[t]) - model.z_3[t] + model.z_4[t]
    #
    #         a.append(p_sell[t] * model.energy_sell_price + p_buy[t] * model.energy_buy_price)
    #     a = sum(a)
    #     return a

    def obj_rule(model):
        p_net = dict()
        a = list()
        for t in TIME_INDEX:
            p_net[t] = model.gen[t] - model.load_[t] - model.p_charge[t] + model.p_discharge[t]
            a.append(p_net[t] * model.prices[t])
        a = sum(a)
        return a

    model.obj = Objective(rule=obj_rule, sense=maximize)

    # ----------------------------------
    # constraints of the model
    # ----------------------------------
    # def p_sell_constraint(model, t):
    #     p_sell = model.exp_energy[t] * (model.gen[t] - model.load_[t]) - model.z_1[t] + model.z_2[t]
    #     return p_sell >= 0
    #
    # def p_buy_constraint(model, t):
    #     p_buy = model.imp_energy[t] * (model.gen[t] - model.load_[t]) - model.z_3[t] + model.z_4[t]
    #     return p_buy <= 0

    def charging_discharging_energy_constraint(model, t):
        return model.charging[t] + model.discharging[t] == 1

    model.charge_discharge_energy_constraint = Constraint(TIME_INDEX, rule=charging_discharging_energy_constraint)

    def max_charge_rate_constraint(model, t):
        return model.p_charge[t] <= model.charging[t] * model.max_p_charge

    model.max_charge_rate_constraint = Constraint(TIME_INDEX, rule=max_charge_rate_constraint)

    def max_discharge_rate_constraint(model, t):
        return model.p_discharge[t] <= model.discharging[t] * model.max_p_discharge

    model.max_discharge_rate_constraint = Constraint(TIME_INDEX, rule=max_discharge_rate_constraint)

    model.init_soc_constraint = Constraint(expr=model.soc[0] == 0.5 * model.max_soc)

    # model.soc_memory_constraint = ConstraintList()
    # for t_m, t in zip(TIME_INDEX[:-1], TIME_INDEX[1:]):
    #     expr = model.soc[t_m] + ((model.z_1[t_m] + model.z_3[t_m]) - (model.z_2[t_m] + model.z_4[t_m])) * 0.25
    #     model.soc_memory_constraint.add(model.soc[t] == expr)

    model.soc_memory_constraint = ConstraintList()
    for t_m, t in zip(TIME_INDEX[:-1], TIME_INDEX[1:]):
        expr = model.soc[t_m] + (model.p_charge[t_m] - model.p_discharge[t_m]) * 0.25
        model.soc_memory_constraint.add(model.soc[t] == expr)

    charging = config.get('FIXED_CHARGING_STATES')
    if charging is not None:
        model.charging_fixed_states_constraint = ConstraintList()
        for t in charging:
            model.charging_fixed_states_constraint.add(model.p_charge[t] == model.max_p_charge)

    discharging = config.get('FIXED_DISCHARGING_STATES')
    if discharging is not None:
        model.discharging_fixed_states_constraint = ConstraintList()
        for t in discharging:
            model.discharging_fixed_states_constraint.add(model.p_discharge[t] == model.max_p_discharge)
    # def z_1_constraint(model, t):
    #     return model.z_1[t] == model.exp_energy[t] * model.exp_charge[t] * model.p_charge[t]
    #
    # model.z_1_constraint = Constraint(TIME_INDEX, rule=z_1_constraint)
    #
    #
    # def z_2_constraint(model, t):
    #     return model.z_2[t] == model.exp_energy[t] * model.exp_discharge[t] * model.p_discharge[t]
    #
    # model.z_2_constraint = Constraint(TIME_INDEX, rule=z_2_constraint)
    #
    # def z_3_constraint(model, t):
    #     return model.z_3[t] == model.imp_energy[t] * model.imp_charge[t] * model.p_charge[t]
    #
    # model.z_3_constraint = Constraint(TIME_INDEX, rule=z_3_constraint)
    #
    # def z_4_constraint(model, t):
    #     return model.z_4[t] == model.imp_energy[t] * model.imp_discharge[t] * model.p_discharge[t]
    #
    # model.z_4_constraint = Constraint(TIME_INDEX, rule=z_4_constraint)

    # ----------------------------------
    # Solving the model
    # ----------------------------------
    solver = SolverFactory('cplex')
    results = solver.solve(model)
    # results = solver.solve(model, tee=True)

    return model

if __name__ == '__main__':
    config = dict()

    prices_data = pd.read_excel('epex_sample.xlsx', sheet_name='spot_data', index_col=0)
    _prices = prices_data.iloc[:, randint(0, 6)].to_numpy()
    prices = np.array([])
    for i in _prices:
        prices = np.concatenate((prices, np.ones(4) * i))
    # prices = np.concatenate((prices, prices))
    load = list(get_load_data(5.0).pload[:24 * 4].values)
    # load = np.concatenate((load, load))
    gen = list(get_gen_data(5.0).pgen[:24 * 4].values)
    # gen = np.concatenate((gen,gen))
    config['PRICES'] = prices
    config['LOAD'] = load
    config['GEN'] = gen
    config['STORAGE_RATE'] = 0.1
    config['STORAGE_SIZE'] = 2.0
    config['MAX_ENERGY_FLOW'] = config['STORAGE_RATE'] * config['STORAGE_SIZE']
    config['MAX_SOC'] = config['STORAGE_SIZE']
    config['MIN_SOC'] = 0.1 * config['STORAGE_SIZE']
    config['FIXED_CHARGING_STATES'] = range(25, 40)
    config['FIXED_DISCHARGING_STATES'] = range(50, 70)

    model = solve_the_model(config)

    import numpy as np
    import matplotlib.pyplot as plt

    p_charge = np.array(list(model.p_charge.get_values().values()))
    p_discharge = np.array(list(model.p_discharge.get_values().values()))

    plt.subplot(2, 2, 1)
    plt.plot(list(model.soc.get_values().values()))
    plt.title('soc')
    plt.grid(True)
    # plt.subplot(2, 2, 1)
    # plt.plot(p_charge - p_discharge)
    # plt.title('storage')
    # plt.grid(True)
    plt.subplot(2, 2, 2)
    plt.plot(list(model.gen.values()))
    plt.title('gen')
    plt.grid(True)
    plt.subplot(2, 2, 3)
    plt.plot(list(model.load_.values()))
    plt.title('load')
    plt.grid(True)
    plt.subplot(2, 2, 4)
    plt.plot(list(model.prices.values()))
    plt.title('prices')
    plt.grid(True)
