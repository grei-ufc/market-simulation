from pade.acl.aid import AID
from prosumer_agent import ProsumerAgent
from concentrator_agent import ConcentratorAgent
from utility_agent import UtilityAgent
from pade.misc.utility import start_loop

from start_mosaik_sim import load_low_voltage_prosumers

import sys
    

if __name__ == '__main__':

    prosumers_id = load_low_voltage_prosumers('force.json')

    agents = list()
    port = int(sys.argv[1]) 
    for p_id in prosumers_id:
        name = 'prosumer' + str(p_id)
        device_agent = ProsumerAgent(aid = AID(name=name + '@localhost:' + str(port)),
                                   node_id = p_id)
        port += 1
        agents.append(device_agent)

    concentrator_agent = ConcentratorAgent(AID(name='concentrator@localhost:' + str(port)))
    agents.append(concentrator_agent)

    port += 1

    utility_agent = UtilityAgent(AID(name='utility@localhost:' + str(port)))
    agents.append(utility_agent)

    start_loop(agents)
