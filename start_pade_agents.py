from pade.acl.aid import AID
from prosumer_agent import ProsumerAgent
from bess_agent import BESSAgent
from dso_agent import DSOAgent
from market_agent import MarketAgent
from solver_agent import SolverAgent
from pade.misc.utility import start_loop
from start_mosaik_sim import load_low_voltage_prosumers, load_medium_voltage_nodes
from create_links import create_adj_array

import numpy as np

import json
import sys
import os
import random
import pprint


MODE = 'simulation'

if __name__ == '__main__':

    # remove o arquivo de estatisticas de comunicação entre os agentes
    try:
        os.remove('communication.hdf5')
    except FileNotFoundError as e:
        print('The file communication.hdf5 is not present in this directory.')

    try:
        os.remove('new_power_flow_data-branch.hdf5')
    except FileNotFoundError as e:
        print('The file new_power_flow_data-branch.hdf5 is not present in this directory.')

    try:
        os.remove('new_power_flow_data-bus.hdf5')
    except FileNotFoundError as e:
        print('The file new_power_flow_data-bus.hdf5 is not present in this directory.')

    try:
        os.remove('power_flow_data-branch.hdf5')
    except FileNotFoundError as e:
        print('The file power_flow_data-branch.hdf5 is not present in this directory.')

    try:
        os.remove('power_flow_data-bus.hdf5')
    except FileNotFoundError as e:
        print('The file power_flow_data-bus.hdf5 is not present in this directory.')

    try:
        os.remove('messages_data.hdf5')
    except FileNotFoundError as e:
        print('The file messages_data.hdf5 is not present in this directory.')

    try:
        os.remove('transactions_data.hdf5')
    except FileNotFoundError as e:
        print('The file transactions_data.hdf5 is not present in this directory.')

    try:
        os.remove('schedules_data.hdf5')
    except FileNotFoundError as e:
        print('The file schedules_data.hdf5 is not present in this directory.')

    # ------------------------------------------------------
    # CARREGA DADOS DE INICIALIZAÇÃO
    # ------------------------------------------------------
    prosumers_ids = load_low_voltage_prosumers('force.json')
    bess_ids = load_medium_voltage_nodes('force.json')
    id_ = 1
    x, y = 20, 20
    coords = list()
    coords_dict = {i: [] for i in bess_ids}

    # identifica qual o id do no de media tensao a que o prosumer esta conectado

    with open('force.json') as f:
        grid_data = json.load(f)

    prosumer_nodes = {str(i['name']): i['medium_voltage_conn_node'] for i in grid_data['nodes'] if i['name'] in prosumers_ids}

    with open('config.json') as f:
        config_file = json.load(f)

    with open('topology.json', 'r') as f:
        topology = json.load(f)

    config_dict = {str(i): {} for i in config_file['nodes_lv']}
    for device, confs in config_file['devices'].items():
        for node, param in confs['params'].items():
            config_dict[node][device] = param

    all_bess_storage_config = config_file['devices']['dso_storage_device']['params']
    all_prosumer_storage_config = config_file['devices']['storage_device']['params']

    # ------------------------------------------------------
    # INICIALIZA OS AGENTES PROSUMERS
    # ------------------------------------------------------
    agents = list()
    port = int(sys.argv[1]) 
    for p_id, p_params in config_dict.items():
        x += random.randint(10, 25)
        y += random.randint(10, 25)

        name = 'prosumer{}@10.0.0.{}:{}'.format(p_id, id_, port)

        prosumer_agent = ProsumerAgent(aid=AID(name=name),
                                       node_id=p_id,
                                       bess_id=prosumer_nodes[p_id],
                                       params=p_params,
                                       mode=MODE)

        agent_data = {'id': int(p_id),
                      'name': name,
                      'network': 'subnetwork-1',
                      'coordinates': [x, y]}
        topology['agents'].append(agent_data)
        coords.append([int(p_id), x, y])
        coords_dict[prosumer_nodes[p_id]].append((x, y))

        agents.append((id_, prosumer_agent))
        port += 1
        id_ += 1

    # ------------------------------------------------------
    # INICIALIZA OS AGENTES BESS
    # ------------------------------------------------------
    x = 10
    y = 10
    coords.append([0, x, y])

    x = 20
    y = 20
    coords.append([1, x, y])

    transformers = grid_data['transformers']

    for b_id, trafo in zip(bess_ids, transformers):
        x = np.mean([i[0] for i in coords_dict[b_id]])
        y = np.mean([i[1] for i in coords_dict[b_id]])

        name = 'bess{}@10.0.0.{}:{}'.format(str(b_id), id_, port)

        bess_storage_config = {str(i): all_bess_storage_config[str(i)] for i in trafo['bess_nodes']}
        # prosumer_storage_config = {str(i): all_prosumer_storage_config[str(i)] for i in trafo['prosumer_bess_nodes']}

        bess_agent = BESSAgent(AID(name=name),
                               # prosumer_storage_config,
                               bess_storage_config,
                               transformer=trafo,
                               mode=MODE)

        agent_data = {'id': b_id,
                      'name': name,
                      'network': 'subnetwork-1',
                      'coordinates': [x, y]}
        topology['agents'].append(agent_data)
        coords.append([int(b_id), x, y])

        agents.append((id_, bess_agent))
        port += 1
        id_ += 1

    # ------------------------------------------------------
    # INICIALIZA O AGENTE DSO
    # ------------------------------------------------------
    name = 'dso@10.0.0.{}:{}'.format(id_, port)
    dso_agent = DSOAgent(AID(name=name),
                         bess_list=bess_ids,
                         mode=MODE)

    agent_data = {'id': int(p_id) + 1,
                  'name': name,
                  'network': 'subnetwork-1',
                  'coordinates': [0, 0]}
    topology['agents'].append(agent_data)
    coords.append([int(p_id) + 1, 0, 0])

    agents.append((id_, dso_agent))
    dso_id = id_
    port += 1
    id_ += 1

    # ------------------------------------------------------
    # INICIALIZA O AGENTE MARKET AGENT
    # ------------------------------------------------------
    name = 'market@10.0.0.{}:{}'.format(id_, port)
    market_agent = MarketAgent(AID(name=name),
                               bess_list=bess_ids,
                               mode=MODE)

    agent_data = {'id': int(p_id) + 2,
                  'name': name,
                  'network': 'subnetwork-1',
                  'coordinates': [0, 0]}
    topology['agents'].append(agent_data)
    coords.append([int(p_id) + 2, 0, 0])

    agents.append((id_, market_agent))
    market_id = id_
    port += 1
    id_ += 1

    # ------------------------------------------------------
    # INICIALIZA O AGENTE SOLVER
    # ------------------------------------------------------
    name = 'solver@10.0.0.{}:{}'.format(id_, port)
    solver_agent = SolverAgent(AID(name=name), mode=MODE)
    agents.append((id_, solver_agent))
    solver_id = id_
    port += 1
    id_ += 1


    # ------------------------------------------------------
    # configuração dos links físicos de comunicação
    # escrita da matriz de adjacencias
    # ------------------------------------------------------
    adj_array, aux1 = create_adj_array(topology, grid_data)

    topology['physical-links'] = aux1

    pprint.pprint(topology['physical-links'])

    # ------------------------------------------------------
    # configuração dos links lógicos de comunicação
    # ------------------------------------------------------
    aux1 = 1
    aux2 = list()
    for i, agent in enumerate(topology['agents']):
        for j, agent_ in enumerate(topology['agents']):
            if i < j:
                data = {'link-id': aux1,
                        'source-id': agent['id'],
                        'target-id': agent_['id']}
                aux2.append(data)
                aux1 += 1
    topology['logical-links'] = aux2

    with open('topology.json', 'w') as f:
        json.dump(topology, f)

    np.savetxt('adj_array.txt', adj_array, delimiter=' ', fmt='%d')

    # ------------------------------------------------------
    # create the bus xy coordinates file
    # ------------------------------------------------------
    coords = np.array(coords)
    np.savetxt('bus_xy.txt', coords, delimiter=',', fmt='%d')

    start_loop([i[1] for i in agents])
