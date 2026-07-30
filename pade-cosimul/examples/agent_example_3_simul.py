
from pade.misc.utility import display_message, start_loop
from pade.core.agent import Agent
from pade.acl.messages import ACLMessage
from pade.acl.aid import AID
from pade.behaviours.protocols import FipaRequestProtocol
from pade.behaviours.protocols import TimedBehaviour

from datetime import datetime
import json
import random
from sys import argv

class CompRequest(FipaRequestProtocol):
    """FIPA Request Behaviour of the Time agent.
    """
    def __init__(self, agent):
        super(CompRequest, self).__init__(agent=agent,
                                          message=None,
                                          is_initiator=False)

    def handle_request(self, message):
        super(CompRequest, self).handle_request(message)
        display_message(self.agent.aid.localname, 'request message received')
        now = datetime.now()
        reply = message.create_reply()
        reply.set_performative(ACLMessage.INFORM)
        reply.set_content(now.strftime('%d/%m/%Y - %H:%M:%S'))
        self.agent.send(reply)


class CompRequest2(FipaRequestProtocol):
    """FIPA Request Behaviour of the Clock agent.
    """
    def __init__(self, agent, message):
        super(CompRequest2, self).__init__(agent=agent,
                                           message=message,
                                           is_initiator=True)

    def handle_inform(self, message):
        display_message(self.agent.aid.localname, message.content)


class ComportTemporal(TimedBehaviour):
    """Timed Behaviour of the Clock agent"""
    def __init__(self, agent, time, message):
        super(ComportTemporal, self).__init__(agent, time)
        self.message = message

    def on_time(self):
        super(ComportTemporal, self).on_time()
        self.agent.send(self.message)


class TimeAgent(Agent):
    """Class that defines the Time agent."""
    def __init__(self, aid):
        super(TimeAgent, self).__init__(aid=aid, mode='simulation', debug=False)

        self.comport_request = CompRequest(self)

        self.behaviours.append(self.comport_request)


class ClockAgent(Agent):
    """Class thet defines the Clock agent."""
    def __init__(self, aid, time_agent_name):
        super(ClockAgent, self).__init__(aid=aid, mode='simulation')

        # message that requests time of Time agent.
        message = ACLMessage(ACLMessage.REQUEST)
        message.set_protocol(ACLMessage.FIPA_REQUEST_PROTOCOL)
        message.add_receiver(AID(name=time_agent_name))
        message.set_content('time')

        self.comport_request = CompRequest2(self, message)
        self.comport_temp = ComportTemporal(self, 15.0, message)

        self.behaviours.append(self.comport_request)
        self.behaviours.append(self.comport_temp)


if __name__ == '__main__':

    # definição dos parâmetros de configuração necessários
    # para inicialização dos agentes 
    agents = list()
    clock_agents_list_1 = list()
    clock_agents_list_2 = list()
    port = int(argv[1])
    mode = argv[2]
    instance = int(argv[3])
    ID = argv[4]
    id_ = 1
    # instanciamento dos agentes

    time_agent_name_1 = 'agent_time_{}@10.0.0.1:{}'.format(port, port)
    time_agent_1 = TimeAgent(AID(name=time_agent_name_1))
    agents.append((id_, time_agent_1))
    id_ += 1
    port += 1
    
    time_agent_name_2 = 'agent_time_{}@10.0.0.2:{}'.format(port, port)
    time_agent_2 = TimeAgent(AID(name=time_agent_name_2))
    agents.append((id_, time_agent_2))
    id_ += 1
    port += 1
    
    for i in range(10, 30):
        clock_agent_name = 'agent_clock_{}@10.0.0.{}:{}'.format(port,
                                                                i,
                                                                port)
        clock_agent = ClockAgent(AID(name=clock_agent_name), time_agent_name_1)
        agents.append((id_, clock_agent))
        clock_agents_list_1.append((id_, clock_agent))
        id_ += 1
        port += 1

    for i in range(50, 70):
        clock_agent_name = 'agent_clock_{}@10.0.0.{}:{}'.format(port,
                                                                i,
                                                                port)
        clock_agent = ClockAgent(AID(name=clock_agent_name), time_agent_name_2)
        agents.append((id_, clock_agent))
        clock_agents_list_2.append((id_, clock_agent))
        id_ += 1
        port += 1

    # carregamento do arquivo de configuração 
    # da simulação do sistema multiagente
    # topology = json.load(open('{}.json'.format(ID), 'r'))
    topology = json.load(open('topology.json', 'r'))
    # inserção dos agentes no arquivo de configuração    
    x, y = 0, 0
    for i, agent_info in enumerate(agents, start=len(topology['agents'])):
        x += random.randint(10, 100)
        y += random.randint(10,100)
        agent_data = {'id': agent_info[0],
                      'name': agent_info[1].aid.name,
                      'network': 'subnetwork-1',
                      'coordinates': [x, y]}
        topology['agents'].append(agent_data)


    # configuração dos links físicos e lógicos de comunicação
    aux1 = list()
    i = 1
    for agent_info_1, agent_info_2 in zip(clock_agents_list_1, clock_agents_list_2):
        data = {'link-id': i,
                'source-id': 1,
                'target-id': agent_info_1[0]}
        aux1.append(data)
        i += 1
        data = {'link-id': i,
                'source-id': 2,
                'target-id': agent_info_2[0]}
        aux1.append(data)
        i += 1
    data = {'link-id': i,
            'source-id': 1,
            'target-id': 2}
    aux1.append(data)

    topology['physical-links'] = aux1

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

    # json.dump(topology, open('{}.json'.format(ID), 'w'))
    json.dump(topology, open('topology.json', 'w'))
    
    # código para escrita da matriz de adjacencias
    import numpy as np
    # data = json.load(open('4555e8ac-83ce-11ea-bdf5-c16295e711fc.json', 'r'))
    data = topology
    n_agents = len(data['agents'])
    adj_array = np.zeros((n_agents, n_agents))
    for i, line in enumerate(adj_array):
        for d in data['physical-links']:
            if (i + 1) == d['source-id']:
                adj_array[i, d['target-id'] - 1] = 1
                adj_array[d['target-id'] - 1, i] = 1
    np.savetxt('adj_array.txt', adj_array, delimiter=' ', fmt='%d')

    # create the bus xy coordinates file
    coords = list()
    aux = [0, 0]
    for i in data['agents']:
        aux[0] += random.randint(10, 100)
        aux[1] += random.randint(10, 100)
        coords.append([i['id'], aux[0], aux[1]])
    coords = np.array(coords)
    np.savetxt('bus_xy.txt', coords, delimiter=',', fmt='%d')
    

    start_loop([i[1] for i in agents])
