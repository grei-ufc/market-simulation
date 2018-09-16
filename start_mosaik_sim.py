import mosaik
import json
import random


SIM_CONFIG = {
    'ProsumerSim': {'python': 'prosumer_sim_with_mosaik_api:ProsumerSim'},
    'DeviceAgentSim': {'connect': 'localhost:1234'}
}

# ---------------------------------------
# define inicio e tempo de execução 
# da simulação
# ---------------------------------------

QTD_HOURS = 1

START = '12/03/2018 - 00:00:00'
END = int(QTD_HOURS * 60 * 60)

world = mosaik.World(SIM_CONFIG)

prosumer_sim = world.start('ProsumerSim',
                           eid_prefix='Prosumer_',
                           start=START,
                           step_size=1 * 60)
device_agent_sim = world.start('DeviceAgentSim',
                               eid_prefix='Device_Agent',
                               start=START,
                               step_size=5 * 60)


# =======================================
# Cria as instâncias de cada um dos 
# simuladores acoplados ao ambiente de
# simulação 
# =======================================

# logica para criacao de prosumers somente na baixa tensao

data = json.load(open('force.json', 'r'))

# define o grau de penetração de DER na rede
der_penetration = 0.5

# definie a quantidade de consumidores que posssuem DER
prosumers_number = int(der_penetration * len(data['nodes']))

# amostra randomicamente os consumidores que possuem DER, deacordo com
# a quantidade especificada na variável prosumers_number
# TODO:
# existe uma pendência neste tópico, pois só pode haver prosumidor na baixa tensão
# e caso um dos nós escolhidos seja da média então este nó será excluído e o grau de
# de penetração de gd definido não será atendido. 
prosumers_with_der =  random.sample(range(len(data['nodes'])), prosumers_number)

prosumers_id = list()
for i in data['nodes']:
    if i['voltage_level'] == 'low voltage':
        if i['name'] in prosumers_with_der:
            prosumers_id.append((i['name'], True))
        else:
            prosumers_id.append((i['name'], False))

prosumers = prosumer_sim.Prosumer.create(len(prosumers_id), prosumers_id=prosumers_id)

device_agents = device_agent_sim.DeviceAgent.create(len(prosumers_id))

# ---------------------------------------
# connect the prosumers model to a device 
# agent.
# ---------------------------------------

for prosumer, device_agent in zip(prosumers, device_agents):
    # world.connect(customer, market, 'order', async_requests=True)
    world.connect(prosumer, device_agent, 'power_forecast', async_requests=True)

world.run(until=END)