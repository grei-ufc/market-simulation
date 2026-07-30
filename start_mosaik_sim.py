import mosaik
import json
import os
import shutil
# ---------------------------------------
# define inicio e tempo de execução
# da simulação
# ---------------------------------------

QTD_HOURS = 1 * 23


START = '01/10/2019 - 00:00:00'
END = int(QTD_HOURS * 60 * 60)


def clear_data_folder_content(folder='data'):
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (file_path, e))


def load_low_voltage_prosumers(file):
    """retorna uma lista com os nós da baixa tensao

    :param file: force.json
    :return: list: lista dos nós de baixa tensão
    """

    with open(file, 'r') as f:
        data = json.load(f)

    prosumers_id = list()
    for i in data['nodes']:
        if i['voltage_level'] == 'low voltage':
            prosumers_id.append(i['name'])

    return prosumers_id

def load_bess_connections(file):

    with open(file, 'r') as f:
        data = json.load(f)

    bess_dist = dict()
    for t in data['transformers']:
        bess_dist[str(t['source'])] = t['bess_nodes']

    return bess_dist

def load_medium_voltage_nodes(file):
    """retorna lista com os nós da média tensão

    :param file: force.json
    :return: list: lista dos nós de média tensão
    """

    with open(file, 'r') as f:
        data = json.load(f)

    nodes_id = list()
    for i in data['nodes']:
        if i['voltage_level'] == 'medium voltage' and i['name'] not in [0, 1]:
            nodes_id.append(i['name'])

    return nodes_id


def generate_grid_dict(file):
    """
    retorna diconario em que as chaves são os nós de média tensão
    e os valores uma lista com os nós de baixa tensão associados
    :param file: force.json
    :return: dicionarios com os nós de média tensão e com os seus
    respectivos nós
    """

    with open(file, 'r') as f:
        data = json.load(f)

    grid_dict = {i['source']: i['nodes'] for i in data['transformers']}

    return grid_dict


def create_scenario(world,
                    config_dict,
                    prosumer_agent_sim_names,
                    bess_agent_sim_names,
                    grid_dict,
                    bess_dist):

    # ---------------------------------------
    # Inicializa a classe que representa os
    # comportamentos da unidade prosumidora
    # com seus respectivos dispositivos de
    # geração ou de consumo
    # ---------------------------------------
    prosumer_sim = world.start('ProsumerSim0',
                               eid_prefix='Prosumer_',
                               start=START,
                               step_size=15 * 60)  # step de tempo em seg.

    # ---------------------------------------
    # Inicializa a classe que representa os
    # comportamentos da unidade BESS
    # com seus respectivos dispositivos de
    # armazenamento
    # ---------------------------------------
    bess_sim = world.start('BESSSim0',
                           eid_prefix='BESS_',
                           start=START,
                           step_size=15 * 60)  # step de tempo em seg.

    # ---------------------------------------
    # Inicializa a classe que representa o
    # o simulador que irá executar análises
    # de fluxo de carga: MyGrid
    # ---------------------------------------
    mygrid_sim = world.start('MyGridSim0',
                             eid_prefix='MyGrid_',
                             start=START,
                             step_size=15 * 60,  # step de tempo em seg.
                             debug=True)

    # ---------------------------------------
    # Inicializa as classes que irão representar
    # cada um dos agentes dispositivos via
    # comunicação com a plataforma PADE
    # ---------------------------------------
    prosumer_agent_sim_list = list()
    for i, name in prosumer_agent_sim_names.items():
        prosumer_agent_sim = world.start(name,
                                         eid_prefix='ProsumerAgent_',
                                         prosumer_ref=i,
                                         start=START,
                                         step_size=1 * 60)  # step de tempo em seg.
        prosumer_agent_sim_list.append(prosumer_agent_sim)

    # ---------------------------------------
    # Inicializa as classes que representam
    # cada um dos agentes BESS via comunicação
    # com a plataforma PADE
    # ---------------------------------------
    bess_agent_sim_list = list()
    for i, name in bess_agent_sim_names.items():
        bess_agent_sim = world.start(name,
                                     eid_prefix='BESSAgent_',
                                     bess_ref=i,
                                     start=START,
                                     step_size=1 * 60) # step de tempo em seg.
        bess_agent_sim_list.append(bess_agent_sim)

    # ---------------------------------------
    # Inicializa a classe que representa o
    # dso agent via comunicação com
    # a plataforma PADE
    # ---------------------------------------
    dso_agent_sim = world.start('DSOAgentSim0',
                                eid_prefix='DSOAgent_',
                                start=START,
                                step_size=1 * 60)  # step de tempo em seg.

    market_agent_sim = world.start('MarketAgentSim0',
                                   eid_prefix='MarketAgent_',
                                   start=START,
                                   step_size=1 * 60)
    # ---------------------------------------
    # Inicializa a classe que representa o
    # simulador com o banco de dados hdf5
    # ---------------------------------------
    hdf5_sim = world.start('HDF5', step_size=15 * 60, duration=END)

    # ---------------------------------------
    # Cria as instâncias de cada um dos
    # simuladores acoplados ao ambiente de
    # simulação
    # ---------------------------------------

    prosumers = prosumer_sim.Prosumer.create(len(config_dict),
                                             config_dict=config_dict)

    bess = bess_sim.BESS.create(len(grid_dict),
                                grid_dict=grid_dict,
                                bess_dist=bess_dist)

    prosumer_agents = [i.ProsumerAgent.create(1) for i in prosumer_agent_sim_list]

    bess_agents = [i.BESSAgent.create(1) for i in bess_agent_sim_list]

    dso_agent = dso_agent_sim.DSOAgent.create(1)

    market_agent = market_agent_sim.MarketAgent.create(1)

    with open('force.json', 'r') as f:
        _mygrid = mygrid_sim.Grid(gridfile=f).children

    db = hdf5_sim.Database(filename='data.hdf5')

    # ---------------------------------------
    # Cria as conexões entre as instancias de
    # simuladores mosaik
    # ---------------------------------------

    connections = dict()

    # #######################################
    # CONEXÕES DE AGENTES COM SEUS MODELOS
    # #######################################

    # connect the prosumers models to prosumers agents.
    for prosumer, prosumer_agent in zip(prosumers, prosumer_agents):
        # world.connect(prosumer, prosumer_agent[0], 'demand')
        for device in prosumer.children:
            world.connect(device, prosumer_agent[0], 'p_out', async_requests=True)
            print('>>> INFO: {} connected with {}.'.format(device.full_id, prosumer_agent[0].full_id))
            connections.setdefault(device.full_id, []).append(prosumer_agent[0].full_id)

    # connect the bess models to bess agents.
    for bess_, bess_agent in zip(bess, bess_agents):
        # world.connect(bess_, bess_agent[0], 'demand')
        world.connect(bess_, bess_agent[0], 'demand', async_requests=True)
        print('>>> INFO: {} connected with {}.'.format(bess_.full_id, bess_agent[0].full_id))
        connections.setdefault(bess_.full_id, []).append(bess_agent[0].full_id)

    # connects bess agent to dso agent
    for bess_agent in bess_agents:
        world.connect(bess_agent[0], dso_agent[0], ('demand', 'dso_param'), async_requests=True)
        print('>>> INFO: {} connected with {}.'.format(bess_agent[0].full_id, dso_agent[0].full_id))
        connections.setdefault(bess_agent[0].full_id, []).append(dso_agent[0].full_id)

    # connects bess agent to market agent
    for bess_agent in bess_agents:
        world.connect(bess_agent[0], market_agent[0], async_requests=True)
        print('>>> INFO: {} connected with {}.'.format(bess_agent[0].full_id, market_agent[0].full_id))
        connections.setdefault(bess_agent[0].full_id, []).append(market_agent[0].full_id)

    # #######################################
    # CONEXÕES DE AGENTES COM SIMULADOR DE
    # FLUXO DE CARGA
    # #######################################

    # connects prosumers simulator to mygrid simulator
    nodes = [e for e in _mygrid if e.type == 'PQBus']
    nodes = {str(n.eid): n for n in nodes}
    # prosumer_data = world.get_data(prosumers, 'node_id')
    for prosumer, node_id in zip(prosumers, config_dict.keys()):
        # node_id = prosumer_data[prosumer]['node_id']
        world.connect(prosumer, nodes[node_id], ('p_out', 'ppa'), ('p_out', 'ppb'), ('p_out', 'ppc'))
        print('>>> INFO: {} connected with {}.'.format(prosumer.full_id, nodes[node_id].full_id))
        connections.setdefault(prosumer.full_id, []).append(nodes[node_id].full_id)

    # connects bess simulator to mygrid simulator
    nodes = [e for e in _mygrid if e.type in ('RefBus', 'PQBus')]
    nodes = {str(n.eid): n for n in nodes}
    for bess_ in bess:
        bess_nodes = bess_dist[bess_.eid.split('_')[1]]
        for device, node in zip(bess_.children, bess_nodes):
            world.connect(device, nodes[str(node)], ('p_out', 'ppa'), ('p_out', 'ppb'), ('p_out', 'ppc'))
            print('>>> INFO: {} connected with {}.'.format(device.full_id, nodes[str(node)].full_id))
            connections.setdefault(device.full_id, []).append(nodes[str(node)].full_id)

    # for bess_, node_id in zip(bess, grid_dict.keys()):
    #     world.connect(bess_, nodes[str(node_id)], ('p_out', 'ppa'), ('p_out', 'ppb'), ('p_out', 'ppc'))
    #     print('>>> INFO: {} connected with {}.'.format(bess_.full_id, nodes[str(node_id)].full_id))
    #     connections.setdefault(bess_.full_id, []).append(nodes[str(node_id)].full_id)

    # connects mygrid nodes simulator to prosumer agents simulator
    nodes = [e for e in _mygrid if e.type in ('RefBus', 'PQBus')]
    nodes = {str(n.eid): n for n in nodes}
    for node_id, prosumer_agent in zip(config_dict.keys(), prosumer_agents):
        world.connect(nodes[str(node_id)], prosumer_agent[0], 'vpa', 'vpb', 'vpc')
        print('>>> INFO: {} connected with {}.'.format(nodes[str(node_id)].full_id, prosumer_agent[0].full_id))
        connections.setdefault(nodes[str(node_id)].full_id, []).append(prosumer_agent[0].full_id)

    # #######################################
    # CONEXÕES DE AGENTES COM BANCO DE DADOS
    # #######################################

    # connects prosumers instances to mosaik-hdf5 database
    mosaik.util.connect_many_to_one(world, prosumers, db, 'p_out')

    # connects mygrid_nodes instances to mosaik-hdf5 database
    nodes = [e for e in _mygrid if e.type in ('RefBus, PQBus')]
    mosaik.util.connect_many_to_one(world, nodes, db, 'ppa', 'ppb', 'ppc', 'vpa', 'vpb', 'vpc')

    for pa in prosumer_agents:
        world.connect(pa[0], db, 'demand_diff')

    with open('connections.json', 'w') as f:
        json.dump(connections, f)

if __name__ == '__main__':

    clear_data_folder_content()

    # =================================================
    # carrega dados necessarios à configuração 
    # dos simuladores conectados ao mosaik
    # =================================================
    prosumers_id = load_low_voltage_prosumers('force.json')
    bess_id = load_medium_voltage_nodes('force.json')
    grid_dict = generate_grid_dict('force.json')
    bess_dist = load_bess_connections('force.json')

    # -------------------------------------------------
    # Cria dicionário com configurações para cada um
    # dos prosumidores da rede
    
    with open('config.json') as f:
        config_file = json.load(f)
    
    configs_list = list()
    config_dict = {str(i): {} for i in config_file['nodes_lv']}
    for device, confs in config_file['devices'].items():
        for node, param in confs['params'].items():
            config_dict[node][device] = param

    # =================================================
    # cria o dicionário com configurações  dos simuladores
    # conectados ao mosaik
    # =================================================

    sim_config = dict()

    # -------------------------------------------------
    # configura o simulador de prosumers
    sim_config['ProsumerSim0'] = {'python': 'prosumer_sim_with_mosaik_api:ProsumerSim'}

    # -------------------------------------------------
    # configura o simulador de bess
    sim_config['BESSSim0'] = {'python': 'bess_sim_with_mosaik_api:BESSSim'}

    # -------------------------------------------------
    # configura o simulador do fluxo de carga
    sim_config['MyGridSim0'] = {'python': 'mosaik_mygrid.mosaik:MyGrid'}

    port = 1234  # numero de porta inicial para lançar os agentes

    # -------------------------------------------------
    # configura os simuladores de device agents
    prosumer_agent_sim_names = dict()
    for i in prosumers_id:
        name = 'ProsumerAgentSim{}'.format(i)
        prosumer_agent_sim_names[i] = name
        sim_config[name] = {'connect': 'localhost:' + str(port)}
        port += 1

    # -------------------------------------------------
    # configura os simuladores de bess agents

    bess_agent_sim_names = dict()
    for i in bess_id:
        name = 'BESSAgentSim{}'.format(i)
        bess_agent_sim_names[i] = name
        sim_config[name] = {'connect': 'localhost:' + str(port)}
        port += 1

    # -------------------------------------------------
    # configura o simulador do dso agent
    sim_config['DSOAgentSim0'] = {'connect': 'localhost:' + str(port)}

    port += 1

    # -------------------------------------------------
    # configura o simulador do market agent
    sim_config['MarketAgentSim0'] = {'connect': 'localhost:' + str(port)}

    # -------------------------------------------------
    # configura o simulador mosaik-hdf5
    sim_config['HDF5'] = {'python': 'mosaik_hdf5:MosaikHdf5'}

    print('---------------\nMosaik config dictionary\n---------------')
    print(sim_config)

    # =================================================
    # configura os simuladores conectados ao mosaik
    # =================================================

    world = mosaik.World(sim_config)
    create_scenario(world,
                    config_dict,
                    prosumer_agent_sim_names,
                    bess_agent_sim_names,
                    grid_dict,
                    bess_dist)

    # =================================================
    # Inicia a simulação mosaik
    # =================================================


    world.run(until=END)
