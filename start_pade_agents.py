from pade.misc.common import PadeSession
from pade.acl.aid import AID
from device_agent import DeviceAgent
from concentrator_agent import ConcentratorAgent

def config_agents():

    agents = list()

    device_agent = DeviceAgent(AID(name='device@localhost:1234'))
    concentrator_agent = ConcentratorAgent(AID(name='concentrator@localhost:1235'))
    agents.append(device_agent)
    agents.append(concentrator_agent)

    s = PadeSession()
    s.add_all_agents(agents)
    s.register_user(username='market_user', email='market@pade.com', password='12345')

    return s

if __name__ == '__main__':

    s = config_agents()
    s.start_loop()
