from pade.misc.common import PadeSession
from pade.acl.aid import AID
from device_agent import DeviceAgent

def config_agents():

    agents = list()

    device_agent = DeviceAgent(AID(name='device@localhost:1234'))
    agents.append(device_agent)

    s = PadeSession()
    s.add_all_agents(agents)
    s.register_user(username='market_user', email='market@pade.com', password='12345')

    return s

if __name__ == '__main__':

    s = config_agents()
    s.start_loop()
