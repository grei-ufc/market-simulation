from pyomo.environ import *
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from random import randint

import pyutilib.subprocess.GlobalData
pyutilib.subprocess.GlobalData.DEFINE_SIGNAL_HANDLERS_DEFAULT = False

# FIX PARAMETERS
PRICES_DATA = pd.read_excel('epex_sample.xlsx', sheet_name='spot_data', index_col=0)
PRICES_INDEX = range(24*4)


def solve_the_model(config):
    # MODEL DECLARATION
    model = ConcreteModel(name='Storage Optimal Model')

    # PARAMETERS DECLARATION
    prices = {i: j for i, j in zip(PRICES_INDEX, config['SPOT_PRICES'])}
    model.prices = Param(PRICES_INDEX, initialize=prices)
    model.storage_rate = Param(initialize=config['STORAGE_RATE'])
    model.storage_size = Param(initialize=config['STORAGE_SIZE'])
    model.max_energy_flow = Param(initialize=config['STORAGE_RATE'] * config['STORAGE_SIZE'])
    model.max_soc = Param(initialize=config['STORAGE_SIZE'])
    model.min_soc = Param(initialize=0.1 * config['STORAGE_SIZE'])

    # VARIABLES DECLARATION
    model.soc = Var(PRICES_INDEX, domain=PositiveReals, bounds=(model.min_soc, model.max_soc))
    model.charge = Var(PRICES_INDEX, domain=PositiveReals)
    model.discharge = Var(PRICES_INDEX, domain=PositiveReals)

    # OBJECTIVE DECLARATION
    model.z = Objective(rule=obj_rule)

    # CONSTRAINTS DECLARATION
    model.CapacityChargeConstraint = Constraint(PRICES_INDEX, rule=capacity_charge_constraint_rule)
    model.CapacityDischargeConstraint = ConstraintList()
    for p in PRICES_INDEX:
        model.CapacityDischargeConstraint.add(model.discharge[p] <= model.max_energy_flow)

    model.InitSocConstraint = Constraint(expr=model.soc[0] == 4.0 * model.min_soc)

    model.SocMemoryConstraint = ConstraintList()
    for p_minus, p in zip(PRICES_INDEX[:-1], PRICES_INDEX[1:]):
        model.SocMemoryConstraint.add(model.soc[p] == model.soc[p_minus] + (model.charge[p] - model.discharge[p]))

    # SOLVING THE MODEL
    solver = SolverFactory('cplex')
    results = solver.solve(model)
    # model.pprint()

    # SHOWING THE RESULTS
    # plt.plot(list(model.soc.get_values().values()))
    # plt.plot(list(model.prices.values()))
    # plt.grid(True)
    # plt.show()

    return model

def obj_rule(model):
    return sum(model.prices[i] * (model.charge[i] - model.discharge[i]) for i in PRICES_INDEX)


def capacity_charge_constraint_rule(model, p):
    return model.charge[p] <= model.max_energy_flow


if __name__ == '__main__':
    for i in range(5):
        # INPUT DATA DECLARATION
        config = dict()
        # load the spot prices in an one hour base
        # its necessary to adapt this to a 15 min. base
        config['SPOT_PRICES'] = PRICES_DATA.iloc[:, randint(0, 6)].to_numpy()
        new_prices = np.array([])
        for i in config['SPOT_PRICES']:
            new_prices = np.concatenate((new_prices, np.ones(4) * i))
        config['SPOT_PRICES'] = new_prices

        config['STORAGE_RATE'] = 0.2
        config['STORAGE_SIZE'] = 10.0
        config['MAX_ENERGY_FLOW'] = config['STORAGE_RATE'] * config['STORAGE_SIZE']
        config['MAX_SOC'] = config['STORAGE_SIZE']
        config['MIN_SOC'] = 0.1 * config['STORAGE_SIZE']

        model = solve_the_model(config)
