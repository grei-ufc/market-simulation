from pade.misc.common import PadeSession
from pade.acl.aid import AID
from device_agent import DeviceAgent
from concentrator_agent import ConcentratorAgent

from start_mosaik_sim import load_low_voltage_prosumers

def config_agents():

    prosumers_id = load_low_voltage_prosumers('force.json')

    agents = list()
    port = 1234
    for i in prosumers_id:
        name = 'device' + str(i[0])
        device_agent = DeviceAgent(AID(name=name + '@localhost:' + str(port)))
        port += 1
        agents.append(device_agent)

    concentrator_agent = ConcentratorAgent(AID(name='concentrator@localhost:' + str(port)))
    agents.append(concentrator_agent)

    s = PadeSession()
    s.add_all_agents(agents)
    s.register_user(username='market_user', email='market@pade.com', password='12345')

    return s

if __name__ == '__main__':

    s = config_agents()
    s.start_loop()
