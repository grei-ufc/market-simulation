import mosaik
import json
import random

# ---------------------------------------
# define inicio e tempo de execução 
# da simulação
# ---------------------------------------

QTD_HOURS = 1

START = '12/03/2018 - 00:00:00'
END = int(QTD_HOURS * 60 * 60)


def load_low_voltage_prosumers(file):
    # logica para criacao de prosumers somente na baixa tensao

    data = json.load(open(file, 'r'))

    prosumers_id = list()
    for i in data['nodes']:
        if i['voltage_level'] == 'low voltage':
            prosumers_id.append(i['name'])

    return prosumers_id


def create_scenario(world, config_dict, device_agent_sim_names):
    
    # =======================================
    # inicializa a classe que representa os 
    # comportamentos da unidade prosumidora 
    # com seus respectivos dispositivos de 
    # geração ou de consumo
    # =======================================
    prosumer_sim = world.start('ProsumerSim',
                               eid_prefix='Prosumer_',
                               start=START,
                               step_size=1 * 60)
    
    # =======================================
    # inicializa as classes que irão representar
    # cada um dos agentes dispositivos via 
    # comunicação com a plataforma PADE
    # =======================================
    device_agent_sim_list = list()
    for i in device_agent_sim_names:
        device_agent_sim = world.start(i,
                                       eid_prefix='Device_Agent',
                                       start=START,
                                       step_size=5 * 60)
        device_agent_sim_list.append(device_agent_sim)


    # =======================================
    # Cria as instâncias de cada um dos 
    # simuladores acoplados ao ambiente de
    # simulação 
    # =======================================

    prosumers = prosumer_sim.Prosumer.create(len(config_dict),
                                             config_dict=config_dict)

    device_agents = [i.DeviceAgent.create(1) for i in device_agent_sim_list]

    # ---------------------------------------
    # connect the prosumers model to a device 
    # agent.
    # ---------------------------------------

    for prosumer, device_agent in zip(prosumers, device_agents):
        # world.connect(customer, market, 'order', async_requests=True)
        world.connect(prosumer, device_agent[0], 'demand', async_requests=True)


if __name__ == '__main__':
    
    # Carrega o dicionário que contem as configurações
    # de cada um dos prosumidores da rede
    config_file = json.load(open('config.json'))
    configs_list = list()
    config_dict = {str(i): {} for i in config_file['nodes']}
    for i, j in config_file['devices'].items():
        for k, w in j['powers'].items():
            config_dict[k][i] = {'value': w}

    prosumers_id = load_low_voltage_prosumers('force.json')

    sim_config = dict()
    sim_config['ProsumerSim'] = {'python': 'prosumer_sim_with_mosaik_api:ProsumerSim'}

    port = 1234
    device_agent_sim_names = list()
    for i in prosumers_id:    
        name = 'DeviceAgentSim' + str(i)
        device_agent_sim_names.append(name)
        sim_config[name] = {'connect': 'localhost:' + str(port)}
        port += 1

    world = mosaik.World(sim_config)
    create_scenario(world, config_dict, device_agent_sim_names)

    world.run(until=END)
