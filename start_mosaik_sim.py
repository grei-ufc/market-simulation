import mosaik
import json
import random

# ---------------------------------------
# define inicio e tempo de execução
# da simulação
# ---------------------------------------

QTD_HOURS = 2 * 24 # Um mês de simulação

START = '25/01/2019 - 10:00:00'
END = int(QTD_HOURS * 60 * 60)

def load_low_voltage_prosumers(file):
    # logica para criacao de prosumers somente na baixa tensao

    data = json.load(open(file, 'r'))

    prosumers_id = list()
    for i in data['nodes']:
        if i['voltage_level'] == 'low voltage':
            prosumers_id.append(i['name'])

    return prosumers_id


def create_scenario(world, config_dict, prosumer_agent_sim_names):

    # =======================================
    # inicializa a classe que representa os
    # comportamentos da unidade prosumidora
    # com seus respectivos dispositivos de
    # geração ou de consumo
    # =======================================
    prosumer_sim = world.start('ProsumerSim0',
                               eid_prefix='Prosumer_',
                               start=START,
                               step_size=5 * 60)  # o step de tempo é dado em segundos

    # =======================================
    # inicializa a classe que representa o
    # o simulador que irá executar análises
    # de fluxo de carga: MyGrid
    # =======================================
    mygrid_sim = world.start('MyGridSim0',
                             eid_prefix='MyGrid_',
                             start=START,
                             step_size=15 * 60,  # o step de tempo é dado em segundos
                             debug=True)

    # =======================================
    # inicializa as classes que irão representar
    # cada um dos agentes dispositivos via
    # comunicação com a plataforma PADE
    # =======================================
    prosumer_agent_sim_list = list()
    for i, name in prosumer_agent_sim_names.items():
        prosumer_agent_sim = world.start(name,
                                       eid_prefix='ProsumerAgent_',
                                       prosumer_ref=i,
                                       start=START,
                                       step_size=15 * 60) # o step de tempo é dado em segundos
        prosumer_agent_sim_list.append(prosumer_agent_sim)

    # =======================================
    # inicializa a classe que representa o
    # agregator agent via comunicação com
    # a plataforma PADE
    # =======================================
    concentrator_agent_sim = world.start('ConcentratorAgentSim0',
                                         eid_prefix='ConcentratorAgent_',
                                         start=START,
                                         step_size=15 * 60) # o step de tempo é dado em segundos

    # =======================================
    # inicializa a classe que representa o
    # utility agent via comunicação com
    # a plataforma PADE
    # =======================================
    utility_agent_sim = world.start('UtilityAgentSim0',
                                    eid_prefix='UtilityAgent_',
                                    start=START,
                                    step_size=15 * 60) # o step de tempo é dado em segundos

    # =======================================
    # Cria as instâncias de cada um dos
    # simuladores acoplados ao ambiente de
    # simulação
    # =======================================

    prosumers = prosumer_sim.Prosumer.create(len(config_dict),
                                             config_dict=config_dict)

    prosumer_agents = [i.ProsumerAgent.create(1) for i in prosumer_agent_sim_list]

    concetrator_agent = concentrator_agent_sim.ConcentratorAgent.create(1)

    utility_agent = utility_agent_sim.UtilityAgent.create(1)

    _mygrid = mygrid_sim.Grid(gridfile=open('force.json', 'r'))

    # ---------------------------------------
    # connect the prosumers model to a device
    # agent.
    # ---------------------------------------

    for prosumer, prosumer_agent in zip(prosumers, prosumer_agents):
        # world.connect(customer, market, 'order', async_requests=True)
        world.connect(prosumer, prosumer_agent[0], 'device_status', async_requests=True)

    # connects the concentrator agent to devices agents 
    for prosumer_agent in prosumer_agents:
        world.connect(prosumer_agent[0], concetrator_agent[0], 'device_status')

    # connects concentrator agent to utility agents
    world.connect(concetrator_agent[0], utility_agent[0], 'clear_price')

    # connects prosumers to mygrid simulator
    mosaik.util.connect_many_to_one(world, prosumers, _mygrid, 'device_status')

if __name__ == '__main__':

    # =================================================
    # Carrega o dicionário que contem as configurações
    # de cada um dos prosumidores da rede
    # =================================================
    config_file = json.load(open('config.json'))
    configs_list = list()
    config_dict = {str(i): {} for i in config_file['nodes']}
    for i, j in config_file['devices'].items():
        for k, w in j['powers'].items():
            config_dict[k][i] = {'value': w}

    # =================================================
    # configura os simuladores conectados ao mosaik
    # =================================================

    sim_config = dict()

    # -------------------------------------------------
    # configura o simulador de devices
    sim_config['ProsumerSim0'] = {'python': 'prosumer_sim_with_mosaik_api:ProsumerSim'}

    # -------------------------------------------------
    # configura os simuladores de device agents
    prosumers_id = load_low_voltage_prosumers('force.json')
    port = 1234
    prosumer_agent_sim_names = dict()
    for i in prosumers_id:
        name = 'ProsumerAgentSim{}'.format(i)
        prosumer_agent_sim_names[i] = name
        sim_config[name] = {'connect': 'localhost:' + str(port)}
        port += 1

    # -------------------------------------------------
    # configura o simulador do fluxo de carga
    sim_config['MyGridSim0'] = {'python': 'mygrid_sim_with_mosaik_api:MyGrid'}

    # -------------------------------------------------
    # configura o simulador do concentrator agent
    sim_config['ConcentratorAgentSim0'] = {'connect': 'localhost:' + str(port)}

    port += 1

    # -------------------------------------------------
    # configura o simulador do utility agent
    sim_config['UtilityAgentSim0'] = {'connect': 'localhost:' + str(port)}

    world = mosaik.World(sim_config)
    create_scenario(world, config_dict, prosumer_agent_sim_names)

    world.run(until=END)
