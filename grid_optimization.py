import pyomo.environ as pyo
from pyomo.opt import SolverFactory, SolverStatus, TerminationCondition

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import pandapower as pp
from pandapower.timeseries import DFData
from pandapower.timeseries import OutputWriter
from pandapower.timeseries.run_time_series import run_timeseries
from pandapower.control import ConstControl

import json
import random
import datetime as dt
import tqdm
import itertools
import h5py

from mosaik_mygrid import model as mgmodel
from load_data import get_load_data, get_gen_data
# from storage_optimization_2 import solve_the_model
from stochastic_model.run_stochastic_model import main as solve_the_model

from scipy.linalg import inv


TIME_INTERV_QTD = 24*4
TIME_INDEX = range(TIME_INTERV_QTD)

with open('force.json', 'r') as f:
    GRID_ELEMENTS, ENTITY_MODEL = mgmodel.load_case(f)

with open('force.json') as f:
    GRID_DATA = json.load(f)

with open('config.json') as f:
    CONFIG_DATA = json.load(f)

times_ = [dt.time(hour=int(i / 4), minute=i % 4 * 15, second=0) for i in range(24 * 4)]


def load_data(tx_bess_prosumers, tx_bess_dso):
    detailed_load = dict()
    for node in GRID_DATA['nodes']:
        if node['voltage_level'] == 'low voltage':
            laux = get_load_data(random.uniform(2.0, 5.0), load_index=int(node['name']))
            # laux = get_load_data(random.uniform(2.0, 5.0))
            if random.random() <= 0.5:
                gaux = get_gen_data(random.uniform(1.0, 3.0))
                detailed_load[str(node['name'])] = laux.pload[:TIME_INTERV_QTD].values - gaux.pgen[:TIME_INTERV_QTD].values
            else:
                detailed_load[str(node['name'])] = laux.pload[:TIME_INTERV_QTD].values
        elif node['voltage_level'] == 'medium voltage':
            detailed_load[str(node['name'])] = np.zeros(TIME_INTERV_QTD)

    # creating storages
    bess_storage_nodes = dict()
    for t in GRID_DATA['transformers']:
        bess_storage_nodes[str(t['source'])] = random.sample(t['nodes'], int(len(t['nodes']) * tx_bess_prosumers))

    control_bess_storage_nodes = dict()
    for t in GRID_DATA['transformers']:
        control_bess_storage_nodes[str(t['source'])] = random.sample(t['nodes'], int(len(t['nodes']) * tx_bess_dso))

    nodes_with_storage = list(itertools.chain.from_iterable(bess_storage_nodes.values()))
    nodes_with_control_storage = list(itertools.chain.from_iterable(control_bess_storage_nodes.values()))

    config_bess_prosumer_dict = dict()
    for n in nodes_with_storage:
        config_bess_prosumer = dict()
        config_bess_prosumer['has_storage'] = True
        config_bess_prosumer['storage_rate'] = random.sample([0.1, 0.2, 0.3], 1)[0]
        config_bess_prosumer['storage_size'] = float(random.randint(5, 15))
        config_bess_prosumer['max_energy_flow'] = config_bess_prosumer['storage_rate'] * config_bess_prosumer['storage_size']
        config_bess_prosumer['max_soc'] = config_bess_prosumer['storage_size']
        config_bess_prosumer['min_soc'] = 0.1 * config_bess_prosumer['storage_size']

        config_bess_prosumer['bilateral_price'] = 40.0
        config_bess_prosumer['bilateral_max'] = 2.0

        config_bess_prosumer_dict[n] = config_bess_prosumer

    config_bess_dso_dict = dict()
    for n in nodes_with_control_storage:
        config_bess_dso = dict()
        config_bess_dso['storage_rate'] = random.sample([0.1, 0.2, 0.3], 1)[0]
        config_bess_dso['storage_size'] = float(random.randint(10, 20))
        config_bess_dso['max_energy_flow'] = config_bess_dso['storage_rate'] * config_bess_dso['storage_size']
        config_bess_dso['max_soc'] = config_bess_dso['storage_size']
        config_bess_dso['min_soc'] = 0.1 * config_bess_dso['storage_size']

        config_bess_dso_dict[n] = config_bess_dso

    storage_detailed_load = dict()
    storage_detailed_soc = dict()
    for node in tqdm.tqdm(GRID_DATA['nodes'], desc='Solving the prosumers storages scheduling'):
        if node['name'] in nodes_with_storage:
            model = solve_the_model(data=config_bess_prosumer_dict[node['name']])

            config_bess_prosumer_dict[node['name']].pop('scenarios')

            p_charge = np.array(list(model.p_charge.get_values().values()))
            p_discharge = np.array(list(model.p_discharge.get_values().values()))
            soc = np.array(list(model.soc.get_values().values()))

            storage_detailed_load[str(node['name'])] = (p_charge - p_discharge)
            storage_detailed_soc[str(node['name'])] = soc

            # detailed_load[str(node['name'])] = detailed_load[str(node['name'])] + (p_charge - p_discharge)
            detailed_load[str(node['name'])] = detailed_load[str(node['name'])]
        else:
            storage_detailed_load[str(node['name'])] = np.zeros(TIME_INTERV_QTD)
            storage_detailed_soc[str(node['name'])] = np.zeros(TIME_INTERV_QTD)

    return (detailed_load, storage_detailed_load,
            bess_storage_nodes, control_bess_storage_nodes,
            config_bess_prosumer_dict, config_bess_dso_dict)


def solve_bess_reschedule(nodes,
                          load_profiles,
                          lagrangians,
                          config_dict):

    assert type(nodes) is list, 'The type of nodes is not list'
    for i in nodes:
        assert type(i) is int, 'An element of nodes is not int'

    assert type(load_profiles) is dict, 'The type of load_profiles is not dict'
    for i, j in load_profiles.items():
        assert type(i) is str, 'An key element of load_profiles is not str'
        assert type(j) is np.ndarray, 'An value element of load_profiles is not ndarray'

    assert type(lagrangians) is dict, 'The type of lagrangians is not dict'
    for i, j in lagrangians.items():
        assert type(i) is int, 'An key element of lagrangians is not int'
        assert type(j) is np.ndarray, 'An value element of lagrangians is not ndarray'

    assert type(config_dict) is dict, 'The type of config_dict is not dict'
    for i, j in config_dict.items():
        assert type(i) is int, 'An key element of config_dict is not int'
        assert type(j) is dict, 'An value element of config_dict is not dict'

    # verify if all the detailed_load values have the same lenght
    aux1 = [len(v) for k, v in load_profiles.items()]
    if aux1[1:] == aux1[:-1]:
        time_qtd = aux1[0]
    else:
        raise(Exception('The length of data in detailed_load is not the same!'))

    nodes.sort()
    time_index = range(time_qtd)
    nodes_storage = [i for i in config_dict.keys() if i in nodes]

    model = pyo.ConcreteModel()

    model.set_node = pyo.Set(initialize=nodes)
    model.set_storage_node = pyo.Set(initialize=nodes_storage)
    model.set_time = pyo.Set(initialize=time_index)
    model.set_power = pyo.Set(initialize=model.set_node * model.set_time)
    model.set_storage_power = pyo.Set(initialize=model.set_storage_node * model.set_time)

    init_power = dict()
    for node in model.set_node:
        for t, value in enumerate(load_profiles[str(node)]):
            init_power[node, t] = value / (1.0e3)

    model.param_power = pyo.Param(model.set_power, initialize=init_power)

    init_lagrangian = dict()
    for node in model.set_node:
        for t, value in enumerate(load_profiles[str(node)]):
            init_lagrangian[node, t] = lagrangians[node][t]

    model.param_lagrangian = pyo.Param(model.set_power,
                                       initialize=init_lagrangian)

    model.ck = pyo.Param(initialize=1.0)
    model.var_power = pyo.Var(model.set_power, within=pyo.Reals)
    model.var_soc = pyo.Var(model.set_storage_power,
                            domain=pyo.NonNegativeReals)

    model.init_soc_constraint = pyo.ConstraintList()
    for n in model.set_storage_node:
        model.init_soc_constraint.add(
            model.var_soc[n, 0] == 0.2 * config_dict[n]['max_soc'])

    model.soc_bounds_constraint = pyo.ConstraintList()
    for p in model.set_storage_power:
        model.soc_bounds_constraint.add(model.var_soc[p] >= config_dict[p[0]]['min_soc'])
        model.soc_bounds_constraint.add(model.var_soc[p] <= config_dict[p[0]]['max_soc'])

    def constraint_max_storage_power(model, n, t):
        STORAGE_MAX_POWER_FLOW = config_dict[n]['max_energy_flow'] / 1e3
        return (-STORAGE_MAX_POWER_FLOW,
                model.var_power[n, t],
                STORAGE_MAX_POWER_FLOW)

    model.constraint_max_storage_power = pyo.Constraint(model.set_storage_power,
                                                        rule=constraint_max_storage_power)

    model.soc_memory_constraint = pyo.ConstraintList()
    for n in model.set_storage_node:
        for t_m, t in zip(time_index[:-1], time_index[1:]):
            expr = model.var_soc[n, t_m] + (model.var_power[n, t_m]) * 0.25
            model.soc_memory_constraint.add(model.var_soc[n, t] == expr)

    def energy_constraint(model, n):
        aux = 0.0
        for t in model.set_time:
            aux += pyo.value(model.param_power[n, t])
        energy = aux

        aux = list()
        for t in model.set_time:
            aux.append(model.var_power[n, t])

        ft = 0.8
        if energy > 0:
            return sum(aux) >= ft * energy
        else:
            return sum(aux) <= ft * energy

    model.energy_constraint = pyo.Constraint(model.set_storage_node, rule=energy_constraint)

    #  somente os nós com storage podem ter seu schedule alterado
    model.constraint_nodes_with_storage = pyo.ConstraintList()
    for p in model.set_power:
        if int(p[0]) not in model.set_storage_node:
            model.constraint_nodes_with_storage.add(model.var_power[p] == model.param_power[p])

    def obj_rule(model):
        a = list()
        for n in model.set_node:
            b = list()
            for t in model.set_time:
                b.append(model.ck * (model.var_power[n, t] - model.param_power[n, t])**2 + model.param_lagrangian[n, t] * model.var_power[n, t])
                a.append(sum(b))
        return sum(a)

    model.obj = pyo.Objective(rule=obj_rule)
    opt = SolverFactory('cplex')
    opt.solve(model)
    return model


def solve_dso_reschedule(base_profiles,
                         storage_profiles,
                         control_storage_profiles,
                         bess_storage_nodes,
                         control_bess_storage_nodes,
                         v0_pu_array,
                         jac_inv_21_array,
                         lagrangian_array,
                         power_flow_matrix,
                         branch_dict,
                         config_dict,
                         config_prosumer_dict):
    # asserttion analysis
    assert type(base_profiles) is dict, 'The type of base_profiles is not dict'
    for i, j in base_profiles.items():
        assert type(i) is str, 'An key element of base_profiles is not str'
        assert type(j) is np.ndarray, 'An value element of base_profiles is not ndarray'

    assert type(storage_profiles) is dict, 'The type of storage_profiles is not dict'
    for i, j in storage_profiles.items():
        assert type(i) is str, 'An key element of storage_profiles is not str'
        assert type(j) is np.ndarray, 'An value element of storage_profiles is not ndarray'

    assert type(control_storage_profiles) is dict, 'The type of control_storage_profiles is not dict'
    for i, j in control_storage_profiles.items():
        assert type(i) is str, 'An key element of control_storage_profiles is not str'
        assert type(j) is np.ndarray, 'An value element of control_storage_profiles is not ndarray'

    assert type(bess_storage_nodes) is dict, 'The type of bess_storage_nodes is not dict'
    for i, j in bess_storage_nodes.items():
        assert type(i) is str, 'An key element of bess_storage_nodes is not str'
        assert type(j) is list, 'An value element of bess_storage_nodes is not list'

    assert type(control_bess_storage_nodes) is dict, 'The type of control_bess_storage_nodes is not dict'
    for i, j in control_bess_storage_nodes.items():
        assert type(i) is str, 'An key element of control_bess_storage_nodes is not str'
        assert type(j) is list, 'An value element of control_bess_storage_nodes is not list'

    assert type(v0_pu_array) is list, 'The type of v0_pu_array is not list'
    for i in v0_pu_array:
        assert type(i) is pd.core.series.Series, 'An key element of v0_pu_array is not pandas Series'

    assert type(jac_inv_21_array) is list, 'The type of jac_inv_21_array is not list'
    for i in jac_inv_21_array:
        assert type(i) is np.ndarray, 'An key element of jac_inv_21_array is not ndarray'

    assert type(lagrangian_array) is dict, 'The type of lagrangian_array is not dict'
    for i, j in lagrangian_array.items():
        assert type(i) is int, 'An key element of lagrangian_array is not int'
        assert type(j) is np.ndarray, 'An value element of lagrangian_array is not ndarray'

    assert type(power_flow_matrix) is np.ndarray, 'The type of power_flow_matrix is not ndarray'

    assert type(branch_dict) is dict, 'The type of branch_dict is not dict'
    for i, j in branch_dict.items():
        assert type(i) is int, 'An key element of branch_dict is not int'
        assert type(j) is tuple, 'An value element of branch_dict is not tuple'

    assert type(config_dict) is dict, 'The type of config_dict is not dict'
    for i, j in config_dict.items():
        assert type(i) is int, 'An key element of config_dict is not int'
        assert type(j) is dict, 'An value element of config_dict is not dict'

    assert type(config_prosumer_dict) is dict, 'The type of config_prosumer_dict is not dict'
    for i, j in config_prosumer_dict.items():
        assert type(i) is int, 'An key element of config_prosumer_dict is not int'
        assert type(j) is dict, 'An value element of config_prosumer_dict is not dict'

    # verify if all the detailed_load values have the same lenght
    aux1 = [len(v) for k, v in storage_profiles.items()]
    if aux1[1:] == aux1[:-1]:
        time_qtd = aux1[0]
    else:
        raise(Exception('The length of data in detailed_load is not the same!'))

    # definição do modelo de otimização
    model = pyo.ConcreteModel()

    nodes = [int(i) for i in storage_profiles.keys()]
    nodes.sort()
    nodes_with_storage = list(itertools.chain.from_iterable(bess_storage_nodes.values()))
    control_nodes_with_storage = list(itertools.chain.from_iterable(control_bess_storage_nodes.values()))
    branchs = [int(i) for i in branch_dict.keys()]
    # cria uma array n(linhas)xt(colunas) em que 'n' é o numero de nos da rede
    # e 't' o numero de intervalos analisados, para facilitar no calculo das
    # restrições de tensão e de corrente

    # cria uma array b(linhas)xt(colunas) em que 'b' é o numero de ramos da rede
    # e 't' o numero de intervalos analisados, para facilitar no calculo das
    # das restrições de tensão e de corrente
    aux = dict(base_profiles)
    try:
        aux.pop('0')
    except KeyError as e:
        pass
    base_profiles_array = np.array([i for i in aux.values()]) / 1.0e3

    time_index = range(time_qtd)

    # inicializa os Sets que serão utilizados pelo modelo
    model.set_node = pyo.Set(initialize=nodes)
    model.set_prosumer_storage_node = pyo.Set(initialize=nodes_with_storage)
    model.set_storage_node = pyo.Set(initialize=control_nodes_with_storage)
    model.set_branch = pyo.Set(initialize=branchs)
    model.set_time = pyo.Set(initialize=time_index)
    model.set_power = pyo.Set(initialize=model.set_node * model.set_time)
    model.set_prosumer_storage_power = pyo.Set(initialize=model.set_prosumer_storage_node * model.set_time)
    model.set_storage_power = pyo.Set(initialize=model.set_storage_node * model.set_time)
    model.set_power_flow = pyo.Set(initialize=model.set_branch * model.set_time)

    # inicializa o parametro param_power com os valores
    # de potencia ativa, em todos os nós e para cada instante de tempo analisado
    init_power = dict()
    for node in nodes:
        for t, value in enumerate(storage_profiles[str(node)]):
            init_power[node, t] = value / 1.0e3

    model.param_power = pyo.Param(model.set_power, initialize=init_power)

    # inicializa o parametro param_control_power com os valores
    # de potencia ativa, em todos os nós e para cada instante de tempo analisado
    init_control_power = dict()
    for node in nodes:
        for t, value in enumerate(control_storage_profiles[str(node)]):
            init_control_power[node, t] = value / 1.0e3

    model.param_control_power = pyo.Param(model.set_power, initialize=init_control_power)

    # inicializa o parametro param_lagrangian com os valores
    # passados, em todos os nós e para cada instante de tempo analisado
    init_lagrangian = dict()
    for node in model.set_node:
        for t in model.set_time:
            init_lagrangian[node, t] = lagrangian_array[node][t]

    model.param_lagrangian = pyo.Param(model.set_power, initialize=init_lagrangian)

    # inicialização dos parametros de PESO dos sistemas de armazenamento dos prosumidores (p1)
    # e dos sistemas de armazenamento de rede (p2)
    model.p1 = pyo.Param(initialize=0.2, mutable=True)
    model.p2 = pyo.Param(initialize=0.8, mutable=True)

    # define a variavel var_power e indexa os seus indices com os indices de cada nó
    # para cada instante de tempo analisado
    model.var_power = pyo.Var(model.set_power, within=pyo.Reals)
    model.var_control_power = pyo.Var(model.set_power, within=pyo.Reals)
    model.var_control_soc = pyo.Var(model.set_storage_power,
                                    domain=pyo.NonNegativeReals)

    model.init_control_soc_constraint = pyo.ConstraintList()
    for n in model.set_storage_node:
        model.init_control_soc_constraint.add(
            model.var_control_soc[n, 0] == 0.4 * config_dict[n]['max_soc'])

    # definição da restrição de tensão para todos os nós em cada instante de tempo
    model.param_min_voltage = pyo.Param(initialize=0.97)
    model.param_max_voltage = pyo.Param(initialize=1.03)

    # inicialização do parametro de tensao inicial
    init_voltage = dict()
    for t, values in enumerate(v0_pu_array):
        for node, value in enumerate(values):
            if node != 0:
                init_voltage[node, t] = value
    model.param_init_voltage = pyo.Param(model.set_power, initialize=init_voltage)

    # #########################################################
    # declaração das restrições do modelo de otimização
    # #########################################################

    model.soc_bounds_constraint = pyo.ConstraintList()
    for p in model.set_storage_power:
        model.soc_bounds_constraint.add(model.var_control_soc[p] >= config_dict[p[0]]['min_soc'])
        model.soc_bounds_constraint.add(model.var_control_soc[p] <= config_dict[p[0]]['max_soc'])

    if len(time_index) > 1:
        model.control_soc_memory_constraint = pyo.ConstraintList()
        for n in model.set_storage_node:
            for t_m, t in zip(time_index[:-1], time_index[1:]):
                expr = model.var_control_soc[n, t_m] + (model.var_control_power[n, t_m]) * 0.25
                model.control_soc_memory_constraint.add(model.var_control_soc[n, t] == expr)

    # print('Calculating the voltages mismatches...')
    voltage_delta_dict = dict()
    for t in model.set_time:
        # print('>>> calculating delta voltage for t={}'.format(t))
        power = np.array(list(model.var_power[:, t]))
        power = np.reshape(power, (len(nodes), 1))

        control_power = np.array(list(model.var_control_power[:, t]))
        control_power = np.reshape(control_power, (len(nodes), 1))

        voltage_delta_array = np.dot(-jac_inv_21_array[t], power + control_power)
        voltage_delta_dict[t] = voltage_delta_array

    def voltage_constraint(model, n, t):
        # print('>>> setting the constraint for index: {} - {}'.format(n, t))
        return (model.param_min_voltage,
                model.param_init_voltage[n, t] + voltage_delta_dict[t][n-1, 0],
                model.param_max_voltage)

    model.constraint_voltage_limits = pyo.Constraint(model.set_power, rule=voltage_constraint)

    var_power_array = np.array(list(model.var_power.values()))
    var_power_array = np.reshape(var_power_array, (len(nodes), time_qtd))

    var_control_power_array = np.array(list(model.var_control_power.values()))
    var_control_power_array = np.reshape(var_control_power_array, (len(nodes), time_qtd))

    p_total_array_pu = base_profiles_array + var_power_array + var_control_power_array
    p_total_array_pu = np.dot(power_flow_matrix, p_total_array_pu) * -1.0
    s_array_pu = p_total_array_pu / 0.9

    def current_constraint(model, b, t):

        branch_type = branch_dict[b][2]
        branch_voltage_kv = branch_dict[b][3]

        if branch_type == 'line':
            branch_i_max_ka = branch_dict[b][4]
            imax_a = branch_i_max_ka * 1e3
            s_max_va = np.sqrt(3.0) * imax_a * branch_voltage_kv * 1e3
            s_max_pu = s_max_va / 1e6
        else:
            branch_s_max_mva = branch_dict[b][4]
            s_max_va = branch_s_max_mva * 1e6
            s_max_pu = s_max_va / 1e6

        s_pu = s_array_pu[b, t]

        return s_pu <= s_max_pu

    model.constraint_current_limits = pyo.Constraint(model.set_power_flow, rule=current_constraint)

    #  somente os nós com storage podem ter seu schedule alterado    
    model.constraint_nodes_with_storage = pyo.ConstraintList()
    for p in model.set_power:
        if p[0] not in nodes_with_storage:
            model.constraint_nodes_with_storage.add(model.var_power[p] == model.param_power[p])

    model.constraint_nodes_with_control_storage = pyo.ConstraintList()
    for p in model.set_power:
        if p[0] not in control_nodes_with_storage:
            model.constraint_nodes_with_control_storage.add(
                model.var_control_power[p] == model.param_control_power[p])

    # restrição de potência máxima do  dispositivo de armazenamento
    def constraint_max_power_control_storage(model, n, t):
        CONTROL_STORAGE_MAX_POWER_FLOW = config_dict[n]['max_energy_flow'] / 1e3
        return (-CONTROL_STORAGE_MAX_POWER_FLOW,
                model.var_control_power[n, t],
                CONTROL_STORAGE_MAX_POWER_FLOW)
    model.constraint_max_power_control_storage = pyo.Constraint(model.set_storage_power,
                                                        rule=constraint_max_power_control_storage)

    # restrição de potência máxima do  dispositivo de armazenamento
    def constraint_max_power_prosumer_storage(model, n, t):
        # TODO: Tornar esta configuração genérica
        CONTROL_STORAGE_MAX_POWER_FLOW = config_prosumer_dict[n]['max_energy_flow'] / 1e3
        return (-CONTROL_STORAGE_MAX_POWER_FLOW,
                model.var_power[n, t],
                CONTROL_STORAGE_MAX_POWER_FLOW)
    model.constraint_max_power_prosumer_storage = pyo.Constraint(model.set_prosumer_storage_power,
                                                        rule=constraint_max_power_prosumer_storage)

    # objective function
    def obj_rule(model):
        a = list()
        for n in model.set_node:
            b = list()
            for t in model.set_time:
                b.append(model.p1 * (model.var_power[n, t] - model.param_power[n, t])**2 +
                         model.p2 * (model.param_control_power[n, t] - model.var_control_power[n, t])**2 -
                         #  model.param_lagrangian[n, t] * (model.var_power[n, t] - model.var_control_power[n, t]))
                         model.param_lagrangian[n, t] * model.var_power[n, t])
                a.append(sum(b))
        return sum(a)
    model.obj = pyo.Objective(rule=obj_rule)

    retry = False
    aux = 0
    while True:
        aux += 1
        if aux > 6:
            print("===============\n>>> DSO WAS NOT ABLE TO FIND A SOLUTION\n===============")
            break

        if retry:
            model.p1 = model.p1.value + 0.1
            model.p2 = model.p2.value - 0.1

        print('preparing to solve the model in cplex solver...')
        opt = SolverFactory('cplex')
        results = opt.solve(model)

        if (results.solver.status == SolverStatus.ok) \
                and (results.solver.termination_condition == TerminationCondition.optimal):
            print("===============\n>>> The solution finded is feasible and optimal\n===============")
            print(results.solver.termination_condition)
            retry = False
        
        # elif results.solver.termination_condition == TerminationCondition.infeasible:
        else:
            print("===============\n>>> Is not possible to solve the problem\n===============")
            print(results.solver.termination_condition)
            retry = True
            continue
        break

    return model


def solve_dso_operation(base_profiles,
                        control_storage_profiles,
                        control_bess_storage_nodes,
                        v0_pu_array,
                        jac_inv_21_array,
                        power_flow_matrix,
                        branch_dict,
                        config_dict):
    # asserttion analysis
    assert type(base_profiles) is dict, 'The type of base_profiles is not dict'
    for i, j in base_profiles.items():
        assert type(i) is str, 'An key element of base_profiles is not str'
        assert type(j) is np.ndarray, 'An value element of base_profiles is not ndarray'

    assert type(control_storage_profiles) is dict, 'The type of control_storage_profiles is not dict'
    for i, j in control_storage_profiles.items():
        assert type(i) is str, 'An key element of control_storage_profiles is not str'
        assert type(j) is np.ndarray, 'An value element of control_storage_profiles is not ndarray'

    assert type(control_bess_storage_nodes) is dict, 'The type of control_bess_storage_nodes is not dict'
    for i, j in control_bess_storage_nodes.items():
        assert type(i) is str, 'An key element of control_bess_storage_nodes is not str'
        assert type(j) is list, 'An value element of control_bess_storage_nodes is not list'

    assert type(v0_pu_array) is list, 'The type of v0_pu_array is not list'
    for i in v0_pu_array:
        assert type(i) is pd.core.series.Series, 'An key element of v0_pu_array is not pandas Series'

    assert type(jac_inv_21_array) is list, 'The type of jac_inv_21_array is not list'
    for i in jac_inv_21_array:
        assert type(i) is np.ndarray, 'An key element of jac_inv_21_array is not ndarray'

    assert type(power_flow_matrix) is np.ndarray, 'The type of power_flow_matrix is not ndarray'

    assert type(branch_dict) is dict, 'The type of branch_dict is not dict'
    for i, j in branch_dict.items():
        assert type(i) is int, 'An key element of branch_dict is not int'
        assert type(j) is tuple, 'An value element of branch_dict is not tuple'

    assert type(config_dict) is dict, 'The type of config_dict is not dict'
    for i, j in config_dict.items():
        assert type(i) is int, 'An key element of config_dict is not int'
        assert type(j) is dict, 'An value element of config_dict is not dict'

    # verify if all the detailed_load values have the same lenght
    aux1 = [len(v) for k, v in control_storage_profiles.items()]
    if aux1[1:] == aux1[:-1]:
        time_qtd = aux1[0]
    else:
        raise(Exception('The length of data in detailed_load is not the same!'))

    # definição do modelo de otimização
    model = pyo.ConcreteModel()

    nodes = [int(i) for i in control_storage_profiles.keys()]
    nodes.sort()
    control_nodes_with_storage = list(itertools.chain.from_iterable(control_bess_storage_nodes.values()))
    branchs = [int(i) for i in branch_dict.keys()]

    # cria uma array b(linhas)xt(colunas) em que 'b' é o numero de ramos da rede
    # e 't' o numero de intervalos analisados, para facilitar no calculo das
    # das restrições de tensão e de corrente
    aux = dict(base_profiles)
    try:
        aux.pop('0')
    except KeyError as e:
        pass
    base_profiles_array = np.array([i for i in aux.values()]) / 1.0e3

    time_index = range(time_qtd)

    # inicializa os Sets que serão utilizados pelo modelo
    model.set_node = pyo.Set(initialize=nodes)
    model.set_storage_node = pyo.Set(initialize=control_nodes_with_storage)
    model.set_branch = pyo.Set(initialize=branchs)
    model.set_time = pyo.Set(initialize=time_index)
    model.set_power = pyo.Set(initialize=model.set_node * model.set_time)
    model.set_storage_power = pyo.Set(initialize=model.set_storage_node * model.set_time)
    model.set_power_flow = pyo.Set(initialize=model.set_branch * model.set_time)

    # define a variavel var_control_power e indexa os seus indices com os indices de cada nó
    # para cada instante de tempo analisado
    model.var_control_power = pyo.Var(model.set_power, within=pyo.Reals)
    
    # inicializa o parametro param_power com os valores
    # de potencia ativa, em todos os nós e para cada instante de tempo analisado
    init_power = dict()
    for node in nodes:
        for t, value in enumerate(control_storage_profiles[str(node)]):
            init_power[node, t] = value / 1.0e3

    model.param_power = pyo.Param(model.set_power, initialize=init_power)


    # definição da restrição de tensão para todos os nós em cada instante de tempo
    model.param_min_voltage = pyo.Param(initialize=0.95)
    model.param_max_voltage = pyo.Param(initialize=1.03)

    # inicialização do parametro de tensao inicial
    init_voltage = dict()
    for t, values in enumerate(v0_pu_array):
        for node, value in enumerate(values):
            if node != 0:
                init_voltage[node, t] = value
    model.param_init_voltage = pyo.Param(model.set_power, initialize=init_voltage)

    # #########################################################
    # declaração das restrições do modelo de otimização
    # #########################################################

    # print('Calculating the voltages mismatches...')
    voltage_delta_dict = dict()
    for t in model.set_time:

        control_power = np.array(list(model.var_control_power[:, t]))
        control_power = np.reshape(control_power, (len(nodes), 1))

        voltage_delta_array = np.dot(-jac_inv_21_array[t], control_power)
        voltage_delta_dict[t] = voltage_delta_array

    def voltage_constraint(model, n, t):
        # print('>>> setting the constraint for index: {} - {}'.format(n, t))
        return (model.param_min_voltage,
                model.param_init_voltage[n, t] + voltage_delta_dict[t][n-1, 0],
                model.param_max_voltage)

    model.constraint_voltage_limits = pyo.Constraint(model.set_power, rule=voltage_constraint)

    var_control_power_array = np.array(list(model.var_control_power.values()))
    var_control_power_array = np.reshape(var_control_power_array, (len(nodes), time_qtd))

    p_total_array_pu = base_profiles_array + var_control_power_array
    p_total_array_pu = np.dot(power_flow_matrix, p_total_array_pu) * -1.0
    s_array_pu = p_total_array_pu / 0.9

    def current_constraint(model, b, t):

        branch_type = branch_dict[b][2]
        branch_voltage_kv = branch_dict[b][3]

        if branch_type == 'line':
            branch_i_max_ka = branch_dict[b][4]
            imax_a = branch_i_max_ka * 1e3
            s_max_va = np.sqrt(3.0) * imax_a * branch_voltage_kv * 1e3
            s_max_pu = s_max_va / 1e6
        else:
            branch_s_max_mva = branch_dict[b][4]
            s_max_va = branch_s_max_mva * 1e6
            s_max_pu = s_max_va / 1e6

        s_pu = s_array_pu[b, t]

        return s_pu <= s_max_pu

    model.constraint_current_limits = pyo.Constraint(model.set_power_flow, rule=current_constraint)

    #  somente os nós com storage podem ter seu schedule alterado
    model.constraint_nodes_with_control_storage = pyo.ConstraintList()
    for p in model.set_power:
        if p[0] not in control_nodes_with_storage:
                model.constraint_nodes_with_control_storage.add(model.var_control_power[p] == model.param_power[p])

    # restrição de potência máxima do  dispositivo de armazenamento
    def constraint_max_power_storage(model, n, t):
        CONTROL_STORAGE_MAX_POWER_FLOW = config_dict[n]['max_energy_flow'] / 1e3
        return (-CONTROL_STORAGE_MAX_POWER_FLOW,
                model.var_control_power[n, t],
                CONTROL_STORAGE_MAX_POWER_FLOW)
    model.constraint_max_power_storage = pyo.Constraint(model.set_storage_power,
                                                        rule=constraint_max_power_storage)

    # objective function
    def obj_rule(model):
        a = list()
        for n in model.set_node:
            b = list()
            for t in model.set_time:
                b.append((model.param_power[n, t] - model.var_control_power[n, t])**2)
                a.append(sum(b))
        return sum(a)

    print('preparing to solve the model in cplex solver...')
    model.obj = pyo.Objective(rule=obj_rule)
    opt = SolverFactory('cplex')
    results = opt.solve(model)

    if (results.solver.status == SolverStatus.ok) \
            and (results.solver.termination_condition == TerminationCondition.optimal):
        print("===============\n>>> The solution finded is feasible and optimal\n===============")
        return model
    elif results.solver.termination_condition == TerminationCondition.infeasible:
        print("===============\n>>> The solution finded is infeasible\n===============")
    else:
        print(str(results.solver))


def create_grid_in_pandapower(detailed_load):
    net = pp.create_empty_network()

    # creating buses
    buses = dict()
    buses_ = dict()
    for n in GRID_DATA['nodes']:
        buses_[n['name']] = n
        if n['voltage_level'] == 'medium voltage':
            buses[n['name']] = pp.create_bus(net, vn_kv=13.8, name=str(n['name']))
        elif n['voltage_level'] == 'low voltage':
            buses[n['name']] = pp.create_bus(net, vn_kv=0.38, name=str(n['name']))

    # creating the external grid
    pp.create_ext_grid(net, bus=buses[0], vm_pu=1.0, name='Ext. Medium Voltage Grid')

    # creating lines and transformers
    branchs = dict()
    for l in GRID_DATA['links']:
        if l['type'] == 'line':
            if buses_[l['target']]['voltage_level'] == 'medium voltage':
                branchs[l['name']] = pp.create_line(net,
                                                    from_bus=buses[l['source']],
                                                    to_bus=buses[l['target']],
                                                    length_km=l['length'] * 1.60934,  # conversao de milhas para km
                                                    std_type='34-AL1/6-ST1A 10.0',
                                                    name=l['name'])
            elif buses_[l['target']]['voltage_level'] == 'low voltage':
                branchs[l['name']] = pp.create_line(net,
                                                    from_bus=buses[l['source']],
                                                    to_bus=buses[l['target']],
                                                    length_km=l['length'] * 1.60934,
                                                    std_type='15-AL1/3-ST1A 0.4',
                                                    name=l['name'])

        elif l['type'] == 'transformer':
            # branchs[l['name']] = pp.create_transformer(net,
            #                                            hv_bus=buses[l['source']],
            #                                            lv_bus=buses[l['target']],
            #                                            std_type='0.25 MVA 10/0.4 kV',
            #                                            name=l['name'])

            branchs[l['name']] = pp.create_transformer_from_parameters(net,
                                                                       hv_bus=buses[l['source']],
                                                                       lv_bus=buses[l['target']],
                                                                       sn_mva=0.250,
                                                                       vn_hv_kv=13.8,
                                                                       vn_lv_kv=0.38,
                                                                       vkr_percent=1.2,  # real part of relative short-circuit voltage
                                                                       vk_percent=4.0,   # relative short-circuit voltage
                                                                       pfe_kw=0.6,       # iron losses in kW
                                                                       i0_percent=0.24,  # open loop losses in percent of rated current
                                                                       shift_degree=-30)

    return net


def run_powerflow_in_pandapower(detailed_load, net, save=False, file_name='power_flow_data'):

    # verify if all the detailed_load values have the same lenght
    aux1 = [len(v) for k, v in detailed_load.items()]
    if aux1[1:] == aux1[:-1]:
        time_qtd = aux1[0]
    else:
        raise(Exception('The length of data in detailed_load is not the same!'))

    jac_inv_21_list = list()
    vm_pu_list = list()

    if save:
        store_bus = pd.HDFStore('{}-bus.hdf5'.format(file_name), 'w')
        store_branch = pd.HDFStore('{}-branch.hdf5'.format(file_name), 'w')
    else:
        store_bus = None
        store_branch = None

    for t in tqdm.tqdm(range(time_qtd), desc='Running the power flow for each t time periods'):
        net.load.drop(net.load.index, inplace=True)
        for node in GRID_DATA['nodes']:
            if node['name'] != 0:
                p_load = detailed_load[str(node['name'])][t] / 1e3
                s_load = p_load / 0.9
                q_load = s_load * np.sin(np.arccos(0.9))
                pp.create_load(net, bus=node['name'], p_mw=p_load, q_mvar=q_load, name='Load_{}'.format(node['name']))
        pp.runpp(net)

        # v0_pu = net.res_bus['vm_pu']
        vm_pu = net.res_bus.vm_pu
        vm_pu_list.append(vm_pu)

        jac = net['_ppc']['internal']['J'].toarray()
        jac_inv = inv(jac)
        jac_inv_21 = jac_inv[len(GRID_DATA['nodes']) - 1:, :len(GRID_DATA['nodes']) - 1]
        jac_inv_21_list.append(jac_inv_21)

        # ---------------------------------------------------
        # código para armazenamento dos valores encontrados
        # no fluxo de carga no arquivo power_flow_data.hdf5
        # ---------------------------------------------------
        if save:
            data_bus = net.res_bus
            data_line = net.res_line
            store_bus.append('t{}'.format(t), data_bus, data_columns=['vm_pu', 'va_degree', 'p_mw', 'q_mvar'])
            store_branch.append('t{}'.format(t), data_line, data_columns=['i_ka', 'loading_percent'])
    if save:
        store_bus.close()
        store_branch.close()

    return vm_pu_list, jac_inv_21_list


def create_branch_dict(net):
    branch_dict = dict()
    aux = 0
    for n in tqdm.tqdm(net.bus.index, desc='Building the incidence matrix'):
        elements_dict = pp.get_connected_elements_dict(net, n)
        buses = sorted(elements_dict.get('bus'))
        lines = elements_dict.get('line')
        trafos = elements_dict.get('trafo')
        for b in buses:
            if n < b:
                if lines:
                    for l in lines:
                        elements_dict_ = pp.get_connected_elements_dict(net, b)
                        lines_ = elements_dict_.get('line')
                        if lines_:
                            if l in lines_:
                                branch_dict[aux] = (n, b, 'line', net.bus.vn_kv[b], 0.5 * net.line.max_i_ka[l])
                                aux += 1
                if trafos:
                    for t in trafos:
                        elements_dict_ = pp.get_connected_elements_dict(net, b)
                        trafos_ = elements_dict_.get('trafo')
                        if trafos_:
                            if t in trafos_:
                                branch_dict[aux] = (n, b, 'trafo', net.bus.vn_kv[b], net.trafo.sn_mva[t])
                                aux += 1
    return branch_dict


def create_power_flow_matrix(branch_dict, net):
    n_branch = len(net.line) + len(net.trafo)
    n_bus = len(net.bus)
    adj_matrix = np.zeros((n_branch, n_bus))
    for i in range(n_branch):
        for j in range(n_bus):
            if j in branch_dict[i][0:2]:
                if j == branch_dict[i][0]:
                    adj_matrix[i, j] = 1.0
                else:
                    adj_matrix[i, j] = -1.0
            else:
                adj_matrix[i, j] = 0.0

    adj_matrix = np.delete(adj_matrix, 0, 1)
    aux = np.linalg.inv(np.dot(adj_matrix, adj_matrix.transpose()))
    power_flow_matrix = np.dot(aux, adj_matrix)
    return power_flow_matrix


def print_info(model_dso,
                    base_profiles,
                    v0_pu_array,
                    jac_inv_21_list,
                    power_flow_matrix,
                    branch_dict,
                    mv_nodes_qtd,
                    node_qtd,
                    branch_qtd,
                    time_qtd):
    #  quais informações seriam importantes obter:
    #  tensões na rede (min, max), onde e quando elas ocorrem
    #  fluxos de potencia na rede, quando e onde eles ocorrem
    #  valor de preço spot e
    #  diferença do valor de convergencia

    param_power = np.reshape(np.array([i for i in model_dso.param_power.values()]),
                            (node_qtd, time_qtd))
    var_power = np.reshape(np.array([pyo.value(i) for i in model_dso.var_power.values()]), 
                          (node_qtd, time_qtd))
    var_control_power = np.reshape(np.array([pyo.value(i) for i in model_dso.var_control_power.values()]),
                          (node_qtd, time_qtd))
    param_lagrangian = np.reshape(np.array([i for i in model_dso.param_lagrangian.values()]),
                            (node_qtd, time_qtd))


    voltage = list()
    for t, values in enumerate(v0_pu_array):
        aux = list()
        for node, value in enumerate(values):
            if node != 0:
                aux.append(value)
        voltage.append(aux)
    voltage = np.array(voltage).transpose()

    voltage_delta = list()
    for t in range(time_qtd):
        aux = np.dot(-jac_inv_21_list[t], var_power[:, t] + var_control_power[:, t])
        voltage_delta.append(aux)
    voltage_delta = np.array(voltage_delta).transpose()

    voltage_pu = voltage + voltage_delta

    aux = dict(base_profiles)
    aux.pop('0')
    base_profiles_array = np.array([i for i in aux.values()])

    p_total_array_kw = base_profiles_array + var_power + var_control_power
    p_total_array_w = np.dot(power_flow_matrix, p_total_array_kw) * -1.0e3
    s_array_va = p_total_array_w / 0.9
    s_array_pu = s_array_va / 1e6

    min_voltage = np.min(voltage_pu)
    min_voltage_index = np.where(voltage_pu == np.min(voltage_pu))
    print('Min. bus volatge value: {:5.4f}'.format(min_voltage))
    print('Min. bus volatge: {} time: {}'.format(min_voltage_index[0][0] + 1, min_voltage_index[1][0]))

    max_voltage = np.max(voltage_pu)
    max_voltage_index = np.where(voltage_pu == np.max(voltage_pu))
    print('Max. bus volatge value: {:5.4f}'.format(max_voltage))
    print('Max. bus volatge: {} time: {}'.format(max_voltage_index[0][0] + 1, max_voltage_index[1][0]))

    max_power = np.max(s_array_va[mv_nodes_qtd:, :])
    max_power_index = np.where(s_array_va == max_power)
    print('Max. lv branch power value: {:5.4f}'.format(max_power))
    print('Max. lv branch power branch: {} time: {}'.format(max_power_index[0][0] + 1, max_power_index[1][0]))

    min_power = np.min(s_array_va[mv_nodes_qtd:, :])
    min_power_index = np.where(s_array_va == min_power)
    print('Min. lv branch power value: {:5.4f}'.format(min_power))
    print('Min. lv branch power branch: {} time: {}'.format(min_power_index[0][0] + 1, min_power_index[1][0]))

    max_lagrang = np.max(param_lagrangian)
    max_lagrang_index = np.where(param_lagrangian == np.max(param_lagrangian))
    print('Max. lagrangian value: {}'.format(max_lagrang  * 1e3))
    print('Max. lagrangian bus: {} time: {}'.format(max_lagrang_index[0][0] + 1, max_lagrang_index[1][0]))
    
    min_lagrang = np.min(param_lagrangian)
    min_lagrang_index = np.where(param_lagrangian == np.min(param_lagrangian))
    print('Min. lagrangian value: {}'.format(min_lagrang  * 1e3))
    print('Min. lagrangian bus: {} time: {}'.format(min_lagrang_index[0][0] + 1, min_lagrang_index[1][0]))


def analyse_results(model_bess, model_dso, net):
    
    total_storage_detailed_load = dict()
    prosumer_storage_detailed_load = dict()
    bess_storage_detailed_load = dict()
    old_prosumer_storage_detailed_load = dict()

    for n in model_dso.set_node:
        aux1 = list()
        aux2 = list()
        aux3 = list()
        aux4 = list()
        for t in model_dso.set_time:
            aux1.append(model_dso.var_power[n, t].value * 1e3 + 
                        model_dso.var_control_power[n, t].value * 1e3)
            aux2.append(model_dso.var_power[n, t].value * 1e3)
            aux3.append(model_dso.var_control_power[n, t].value * 1e3)
            aux4.append(model_dso.param_power[n, t] * 1e3)

        total_storage_detailed_load[n] = np.array(aux1)
        prosumer_storage_detailed_load[n] = np.array(aux2)
        bess_storage_detailed_load[n] = np.array(aux3)
        old_prosumer_storage_detailed_load[n] = np.array(aux4)
    
    # executa fluxo de carga com novo schedule de carga
    new_detailed_load = dict()
    for node in detailed_load.keys():
        if node == '0':
            new_detailed_load[node] = detailed_load[node]
        else:
            new_detailed_load[node] = detailed_load[node] + total_storage_detailed_load[int(node)]

    v0_pu_list, jac_inv_21_list = run_powerflow_in_pandapower(new_detailed_load,
                                                              net,
                                                              save=True,
                                                              file_name='new_power_flow_data')
    
    # from plot_results import plot_schedule_results

    # plt.figure(1)
    # plot_schedule_results(hdf5_file='power_flow_data',
    #                      medium_voltage_nodes_qtd=mv_nodes_qtd)
    # plt.figure(2)
    # plot_schedule_results(hdf5_file='new_power_flow_data',
    #                      medium_voltage_nodes_qtd=mv_nodes_qtd)

    return (total_storage_detailed_load,
            prosumer_storage_detailed_load,
            bess_storage_detailed_load,
            old_prosumer_storage_detailed_load,
            new_detailed_load)


def calc_grid_restrictions(net,
                           total_detailed_load_kw,
                           power_flow_matrix,
                           branch_dict):
    # --------------------
    # preparação dos dados
    # --------------------
    nodes = [int(i) for i in total_detailed_load_kw.keys()]
    branchs = [int(i) for i in branch_dict.keys()]

    aux1 = [len(v) for k, v in total_detailed_load_kw.items()]
    if aux1[1:] == aux1[:-1]:
        time_qtd = aux1[0]
    else:
        raise(Exception('The length of data in detailed_load is not the same!'))

    time = range(time_qtd)

    v0_pu_list, jac_inv_21_list = run_powerflow_in_pandapower(total_detailed_load_kw,
                                                              net,
                                                              save=False)

    v0_pu = v0_pu_list[0]
    jac_inv_21 = jac_inv_21_list[0]

    # calculo da restrição dos níveis de tensão
    # -----------------------------------------
    max_voltage_pu_value = 1.05
    min_voltage_pu_value = 0.95
    max_voltage_restriction = v0_pu[v0_pu > max_voltage_pu_value]
    min_voltage_restriction = v0_pu[v0_pu < min_voltage_pu_value]
    if max_voltage_restriction.any():
        print('\nthe grid has a max. voltage restriction')
    else:
        pass

    if min_voltage_restriction.any():
        print('\nThe grid has a min. voltage restriction')
    else:
        pass

    total_detailed_load_array_kw = np.array([i for i in total_detailed_load_kw.values()])
    total_detailed_load_array_kw = np.reshape(total_detailed_load_array_kw, (len(nodes), time_qtd))

    p_total_array_pu = (total_detailed_load_array_kw) / 1e3
    p_total_array_pu = np.dot(power_flow_matrix, p_total_array_pu) * -1.0
    s_array_pu = p_total_array_pu / 0.9

    def current_constraint(b, t):
        branch_type = branch_dict[b][2]
        branch_voltage_kv = branch_dict[b][3]

        if branch_type == 'line':
            branch_i_max_ka = branch_dict[b][4]
            imax_a = branch_i_max_ka * 1e3
            s_max_va = np.sqrt(3.0) * imax_a * branch_voltage_kv * 1e3
            s_max_pu = s_max_va / 1e6
        else:
            branch_s_max_mva = branch_dict[b][4]
            s_max_va = branch_s_max_mva * 1e6
            s_max_pu = s_max_va / 1e6

        s_pu = s_array_pu[b, t]

        if s_pu <= s_max_pu:
            return None
        else:
            return s_pu/s_max_pu
    data = dict()
    for b in branchs:
        for t in time:
            rate = current_constraint(b, t)
            if rate:
                data[b] = rate
                print('Overcurrent in branch: {} in time: {}'.format(b, t))
    max_current_restriction = pd.Series(list(data.values()), index=data.keys())

    return max_current_restriction, max_voltage_restriction, min_voltage_restriction


if __name__ == '__main__':

    # #################################################
    # Load initial data parameters
    # #################################################
    
    print('>> Loading data...')
    mv_nodes_qtd = 7
    time_qtd = 96
    tx_bess_prosumers = 0.6
    tx_bess_dso = 0.4
    (detailed_load, storage_detailed_load,
     bess_storage_nodes, control_bess_storage_nodes,
     config_bess_prosumer_dict, config_bess_dso_dict) = load_data(tx_bess_prosumers,
                                                                  tx_bess_dso)
    
    # #################################################
    # adicao de carga em um no escolhido aleat. 
    # entre os nos do sistema
    # #################################################
    # aux = list(itertools.chain.from_iterable(bess_storage_nodes.values()))
    # test_node = random.sample(aux, 1)[0]
    # print('Test node: {}'.format(test_node))
    # storage_detailed_load[str(test_node)] = storage_detailed_load[str(test_node)] * 5.0
    # aux_config = config_bess_prosumer_dict[test_node]
    # aux_config['STORAGE_RATE'] = 5.0 * aux_config['STORAGE_RATE']
    # aux_config['STORAGE_SIZE'] = 5.0 * aux_config['STORAGE_SIZE']
    # aux_config['MAX_ENERGY_FLOW'] = aux_config['STORAGE_RATE'] * aux_config['STORAGE_SIZE']
    # aux_config['MAX_SOC'] = aux_config['STORAGE_SIZE']
    # aux_config['MIN_SOC'] = 0.1 * aux_config['STORAGE_SIZE']

    # config_bess_prosumer_dict[test_node] = aux_config
    

    # #################################################
    # Initial parameters definitions
    # #################################################

    # reduz a quantidade de dados nas variaveis detailed_load e storage_detailed_load
    # para o valor definido em time_qtd
    detailed_load = {k: v[:time_qtd] for k, v in detailed_load.items()}
    storage_detailed_load = {k: v[:time_qtd] for k, v in storage_detailed_load.items()}
    # storage_detailed_load = {k: np.zeros(time_qtd) for k, v in storage_detailed_load.items()}
    control_storage_detailed_load = {k: np.zeros(time_qtd) for k, v in storage_detailed_load.items()}
    
    # retira o nó '0' dos nós da rede
    # isso é feito porque o Jacobiano não contem o nó 0, a referencia do sistema
    storage_detailed_load.pop('0')

    # montagem do dicionário contendo od multiplicadores de lagrange iniciais
    lagrangian_multiplier = {int(n): np.zeros(time_qtd) for n in storage_detailed_load.keys()}

    # ################################################
    # Get the jacobian matrix and the initial
    # voltage buses
    # #################################################
    net = create_grid_in_pandapower(detailed_load)
    v0_pu_list, jac_inv_21_list = run_powerflow_in_pandapower(detailed_load, net, save=True)

    # ################################################
    # Montagem da matriz de incidencia de barra
    # #################################################
    branch_dict = create_branch_dict(net)
    power_flow_matrix = create_power_flow_matrix(branch_dict, net)

    # ################################################
    # Montagem do arquivo de configuração
    # para otimização
    # #################################################

    # ######################<<PROCESSO DE DECOMPOSIÇÃO em ML - INICIO>>############

    # gera informações necessárias para simular as funcionalidades do BESS
    bess_dict = dict()
    for t in GRID_DATA['transformers']:
        bess_dict[str(t['source'])] = t['nodes']

    new_detailed_load_bess = dict()
    new_detailed_load_dso = dict()
    # laço principal para analise de convergencia do processo DSO-BESS
    aux = 1
    while aux <= 60:
        print('---------------------------------')
        print('>> Iteracao n. {}'.format(aux))
        # BESS OPTIMIZATION
        for b_name, b_nodes in bess_dict.items():
            model_bess = solve_bess_reschedule(b_nodes,
                                               storage_detailed_load,
                                               lagrangian_multiplier,
                                               config_bess_prosumer_dict)
            for n in model_bess.set_node:
                laux = list()
                for t in model_bess.set_time:
                    laux.append(model_bess.var_power[n, t].value)
                new_detailed_load_bess[str(n)] = np.array(laux)

        # DSO OPTIMIZATION
        model_dso = solve_dso_reschedule(detailed_load,
                                         storage_detailed_load,
                                         control_storage_detailed_load,
                                         bess_storage_nodes,
                                         control_bess_storage_nodes,
                                         v0_pu_list,
                                         jac_inv_21_list,
                                         lagrangian_multiplier,
                                         power_flow_matrix,
                                         branch_dict,
                                         config_bess_dso_dict)

        for n in model_dso.set_node:
            laux = list()
            for t in model_dso.set_time:
                laux.append(model_dso.var_power[n, t].value)
            new_detailed_load_dso[str(n)] = np.array(laux)

        print_info(model_dso,
                   detailed_load,
                   v0_pu_list,
                   jac_inv_21_list,
                   power_flow_matrix,
                   branch_dict,
                   mv_nodes_qtd,
                   len(storage_detailed_load),
                   len(storage_detailed_load),
                   time_qtd)
        
        # ATUALIZAZACAO DOS MULTIPLICADORES DE LAGRANGE
        # m = 1.0
        # alpha = (1 + m) / (aux + m)
        alpha = 0.5

        lag_mult_old = pd.DataFrame(lagrangian_multiplier)
        for n in new_detailed_load_bess.keys():
            lagrangian_multiplier[int(n)] += alpha * (new_detailed_load_bess[n] - new_detailed_load_dso[n])

        lag_mult_new = pd.DataFrame(lagrangian_multiplier)

        diff = lag_mult_old - lag_mult_new
        print(abs(diff).max().max())
        if (abs(diff) < 1e-3/1.0e3).all(axis=None):
            break
        aux += 1

    ######################<<PROCESSO DE DECOMPOSIÇÃO em ML - FIM>>############


    # #################################################
    # Plota alguns dos resultados obtidos
    # #################################################
    (total_storage_detailed_load,
     prosumer_storage_detailed_load,
     bess_storage_detailed_load,
     old_prosumer_storage_detailed_load,
     new_detailed_load) = analyse_results(model_bess, model_dso, net)

    # #################################################
    # Simulação da fase de operação
    # #################################################
    t = 9
    base_profiles = {i: np.array([j[t]]) for i, j in detailed_load.items()}
    # base_profiles.pop('0')
    no_control_storage_detailed_load = {str(i): np.array([j[t]])
                                        for i, j in prosumer_storage_detailed_load.items()}

    control_storage_detailed_load = {str(i): np.array([j[t]])
                                     for i, j in bess_storage_detailed_load.items()}

    total_detailed_load_kw = {str(i): [base_profiles[i] +
                              no_control_storage_detailed_load[i] +
                              control_storage_detailed_load[i]]
                              for i in no_control_storage_detailed_load.keys()}

    (max_current_restriction,
    max_voltage_restriction,
    min_voltage_restriction) = calc_grid_restrictions(net,
                                                      total_detailed_load_kw,
                                                      power_flow_matrix,
                                                      branch_dict)
    operation_model = None
    if max_current_restriction.any() or \
       max_voltage_restriction.any() or \
       min_voltage_restriction.any():

        total_detailed_load_kw = {str(i): np.array(base_profiles[i] +
                                  no_control_storage_detailed_load[i])
                                  for i in no_control_storage_detailed_load.keys()}

        v0_pu_list, jac_inv_21_list = run_powerflow_in_pandapower(total_detailed_load_kw,
                                                                  net,
                                                                  save=False)

        operation_model = solve_dso_operation(total_detailed_load_kw,
                                              control_storage_detailed_load,
                                              control_bess_storage_nodes,
                                              v0_pu_list,
                                              jac_inv_21_list,
                                              power_flow_matrix,
                                              branch_dict,
                                              config_bess_dso_dict)
    
    if not operation_model:
        # ######################<<PROCESSO DE DECOMPOSIÇÃO em ML - INICIO>>############

        time_qtd = 1

        storage_detailed_load = no_control_storage_detailed_load
        lagrangian_multiplier = {int(n): np.zeros(time_qtd) for n in storage_detailed_load.keys()}

        detailed_load = base_profiles
        storage_detailed_load = no_control_storage_detailed_load
        control_storage_detailed_load = control_storage_detailed_load

        v0_pu_list, jac_inv_21_list = run_powerflow_in_pandapower(detailed_load,
                                                                  net,
                                                                  save=False)

        # gera informações necessárias para simular as funcionalidades do BESS
        bess_dict = dict()
        for t in GRID_DATA['transformers']:
            bess_dict[str(t['source'])] = t['nodes']

        new_detailed_load_bess = dict()
        new_detailed_load_dso = dict()
        # laço principal para analise de convergencia do processo DSO-BESS
        aux = 1
        while aux <= 60:
            print('---------------------------------')
            print('>> Iteracao n. {}'.format(aux))
            # BESS OPTIMIZATION
            for b_name, b_nodes in bess_dict.items():
                model_bess = solve_bess_reschedule(b_nodes,
                                                   storage_detailed_load,
                                                   lagrangian_multiplier,
                                                   config_bess_prosumer_dict)
                for n in model_bess.set_node:
                    laux = list()
                    for t in model_bess.set_time:
                        laux.append(model_bess.var_power[n, t].value)
                    new_detailed_load_bess[str(n)] = np.array(laux)

            # DSO OPTIMIZATION
            model_dso = solve_dso_reschedule(detailed_load,
                                             storage_detailed_load,
                                             control_storage_detailed_load,
                                             bess_storage_nodes,
                                             control_bess_storage_nodes,
                                             v0_pu_list,
                                             jac_inv_21_list,
                                             lagrangian_multiplier,
                                             power_flow_matrix,
                                             branch_dict,
                                             config_bess_dso_dict)

            for n in model_dso.set_node:
                laux = list()
                for t in model_dso.set_time:
                    laux.append(model_dso.var_power[n, t].value)
                new_detailed_load_dso[str(n)] = np.array(laux)

            print_info(model_dso,
                       detailed_load,
                       v0_pu_list,
                       jac_inv_21_list,
                       power_flow_matrix,
                       branch_dict,
                       mv_nodes_qtd,
                       len(storage_detailed_load),
                       len(storage_detailed_load),
                       time_qtd)
            
            # ATUALIZAZACAO DOS MULTIPLICADORES DE LAGRANGE
            # m = 1.0
            # alpha = (1 + m) / (aux + m)
            alpha = 0.5

            lag_mult_old = pd.DataFrame(lagrangian_multiplier)
            for n in new_detailed_load_bess.keys():
                lagrangian_multiplier[int(n)] += alpha * (new_detailed_load_bess[n] - new_detailed_load_dso[n])

            lag_mult_new = pd.DataFrame(lagrangian_multiplier)

            diff = lag_mult_old - lag_mult_new
            print(abs(diff).max().max())
            if (abs(diff) < 1e-3/1.0e3).all(axis=None):
                break
            aux += 1

        ######################<<PROCESSO DE DECOMPOSIÇÃO em ML - FIM>>############
