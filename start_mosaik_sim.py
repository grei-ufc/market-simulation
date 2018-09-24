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

    return prosumers_id


def create_scenario(world, prosumers_id, device_agent_sim_names):
    prosumer_sim = world.start('ProsumerSim',
                               eid_prefix='Prosumer_',
                               start=START,
                               step_size=1 * 60)
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

    prosumers = prosumer_sim.Prosumer.create(len(prosumers_id), prosumers_id=prosumers_id)

    device_agents = [i.DeviceAgent.create(1) for i in device_agent_sim_list]

    # ---------------------------------------
    # connect the prosumers model to a device 
    # agent.
    # ---------------------------------------

    for prosumer, device_agent in zip(prosumers, device_agents):
        # world.connect(customer, market, 'order', async_requests=True)
        world.connect(prosumer, device_agent[0], 'power_forecast', async_requests=True)


if __name__ == '__main__':
    
    prosumers_id = load_low_voltage_prosumers('force.json')

    sim_config = dict()
    sim_config['ProsumerSim'] = {'python': 'prosumer_sim_with_mosaik_api:ProsumerSim'}

    port = 1234
    device_agent_sim_names = list()
    for i, j in enumerate(prosumers_id):    
        name = 'DeviceAgentSim' + str(i)
        device_agent_sim_names.append(name)
        sim_config[name] = {'connect': 'localhost:' + str(port)}
        port += 1

    world = mosaik.World(sim_config)
    create_scenario(world, prosumers_id, device_agent_sim_names)

    world.run(until=END)
