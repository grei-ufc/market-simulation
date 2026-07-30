from networkx.convert_matrix import _generate_weighted_edges
import pyomo.pysp.util.rapper as rapper
from pyomo.pysp.scenariotree.tree_structure_model import CreateAbstractScenarioTreeModel
import pyomo.environ as pyo

import numpy as np
import matplotlib.pyplot as plt
import random as rnd

import pathlib
import time
import sys
sys.path.append(str(pathlib.Path(__file__).parent.absolute()))

from generate_scenarios import main as update_scenarios


def main(data):
    retry = False
    while True:
        if retry:
            data['node_id'] += 1

        update_scenarios(scenarios_qtd=9, reduced_scenarios_qtd=3, data=data)
        solvername = 'cplex'
        path = str(pathlib.Path(__file__).parent.absolute())

        abstract_tree = CreateAbstractScenarioTreeModel()
        concrete_tree = abstract_tree.create_instance(path + '/ScenarioStructure.dat')

        stsolver = rapper.StochSolver(fsfile=path + '/ReferenceModel.py',
                                      # fsfct='pysp_instance_creation_callback',
                                      tree_model=concrete_tree)

        # ef_sol = stsolver.solve_ef(solvername)

        ef_sol = stsolver.solve_ef(solvername,
                                   generate_weighted_cvar=True,
                                   cvar_weight=1.0,
                                   risk_alpha=0.1)

        if ef_sol.solver.termination_condition != pyo.TerminationCondition.optimal:
            print('Not optimal solution: {}'.format(ef_sol.solver.termination_condition))
            retry = True
            continue
        else:
            retry = False
            print('Optimal solution finded: {}'.format(ef_sol.solver.termination_condition))
            # for varname, varvalue in stsolver.root_Var_solution():
            #     print(varname, str(varvalue))

        scenarios = stsolver.scenario_tree.scenarios

        model = rnd.choice(scenarios).instance
        break

    del scenarios
    del stsolver
    del ef_sol
    del abstract_tree
    del concrete_tree

    return model

if __name__ == '__main__':

    config = dict()
    config['has_storage'] = True
    config['storage_rate'] = 0.2
    config['storage_size'] = 10.0
    config['max_energy_flow'] = config['storage_rate'] * config['storage_size']
    config['max_soc'] = config['storage_size']
    config['min_soc'] = 0.1 * config['storage_size']

    config['bilateral_price'] = 38.0
    config['bilateral_max'] = 5.0

    config['node_id'] = 32
    config['load_kw'] = 4.0
    config['gen_kw'] = 1.0

    for i in range(1):
        config['node_id'] += 1
        model = main(data=config)

    soc_data = list(model.soc.get_values().values())
    time_data = [t / 4 for t in range(len(soc_data))]
    plt.subplot(2, 2, 1)
    plt.step(time_data, soc_data)
    plt.title('soc')
    plt.grid(True)

    p_spot_data = list(model.p_spot.get_values().values())
    p_bilateral_data = list(model.p_bilateral.get_values().values())
    time_data = [t / 4 for t in range(len(p_spot_data))]
    
    plt.subplot(2, 2, 2)
    plt.step(time_data, p_spot_data, time_data, p_bilateral_data)
    plt.title('spot power')
    plt.legend(['spot', 'bilateral'])
    plt.grid(True)

    demand_data = np.array([i.value for i in model.demand.values()])
    p_charge_data = np.array(list(model.p_charge.get_values().values()))
    p_discharge_data = np.array(list(model.p_discharge.get_values().values()))
    p_storage_data = p_charge_data - p_discharge_data
    
    time_data = [t / 4 for t in range(len(demand_data))]
    plt.subplot(2, 2, 3)
    plt.step(time_data, demand_data, time_data, p_storage_data, time_data, demand_data+p_storage_data)
    plt.legend(['load+gen.', 'storage', 'load+gen.+stor.'])
    plt.title('liquid-demand')
    plt.grid(True)

    spot_prices_data = [i.value for i in model.spot_prices.values()]
    time_data = [t / 4 for t in range(len(spot_prices_data))]
    plt.subplot(2, 2, 4)
    plt.step(time_data, spot_prices_data)
    plt.title('prices')
    plt.grid(True)

    plt.show()
