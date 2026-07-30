from pade.misc.utility import display_message, start_loop
from pade.core.agent import Agent
from pade.acl.aid import AID
from pade.acl.messages import ACLMessage
from pade.behaviours.protocols import FipaContractNetProtocol
from sys import argv
from random import uniform, randint, choice

import os
import json


class CompContNet1(FipaContractNetProtocol):
    '''CompContNet1

       Initial FIPA-ContractNet Behaviour that sends CFP messages
       to other feeder agents asking for restoration proposals.
       This behaviour also analyzes the proposals and selects the
       one it judges to be the best.'''

    def __init__(self, agent, message):
        super(CompContNet1, self).__init__(
            agent=agent, message=message, is_initiator=True)
        self.cfp = message

    def handle_all_proposes(self, proposes):
        """
        """

        super(CompContNet1, self).handle_all_proposes(proposes)

        best_proposer = None
        higher_power = 0.0
        other_proposers = list()
        display_message(self.agent.aid.name, 'Analyzing proposals...')

        i = 1

        # logic to select proposals by the higher available power.
        for message in proposes:
            content = message.content
            power = float(content)
            display_message(self.agent.aid.name,
                            'Analyzing proposal {i}'.format(i=i))
            display_message(self.agent.aid.name,
                            'Power Offered: {pot}'.format(pot=power))
            i += 1
            if power > higher_power:
                if best_proposer is not None:
                    other_proposers.append(best_proposer)

                higher_power = power
                best_proposer = message.sender
            else:
                other_proposers.append(message.sender)

        display_message(self.agent.aid.name,
                        'The best proposal was: {pot} VA'.format(
                            pot=higher_power))

        if other_proposers != []:
            display_message(self.agent.aid.name,
                            'Sending REJECT_PROPOSAL answers...')
            answer = ACLMessage(ACLMessage.REJECT_PROPOSAL)
            answer.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
            answer.set_content('')
            for agent in other_proposers:
                answer.add_receiver(agent)

            self.agent.send(answer)

        if best_proposer is not None:
            display_message(self.agent.aid.name,
                            'Sending ACCEPT_PROPOSAL answer...')

            answer = ACLMessage(ACLMessage.ACCEPT_PROPOSAL)
            answer.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
            answer.set_content('OK')
            answer.add_receiver(best_proposer)
            self.agent.send(answer)

    def handle_inform(self, message):
        """
        """
        super(CompContNet1, self).handle_inform(message)

        display_message(self.agent.aid.name, 'INFORM message received')

    def handle_refuse(self, message):
        """
        """
        super(CompContNet1, self).handle_refuse(message)

        display_message(self.agent.aid.name, 'REFUSE message received')

    def handle_propose(self, message):
        """
        """
        super(CompContNet1, self).handle_propose(message)

        display_message(self.agent.aid.name, 'PROPOSE message received')


class CompContNet2(FipaContractNetProtocol):
    '''CompContNet2

       FIPA-ContractNet Participant Behaviour that runs when an agent
       receives a CFP message. A proposal is sent and if it is selected,
       the restrictions are analized to enable the restoration.'''

    def __init__(self, agent):
        super(CompContNet2, self).__init__(agent=agent,
                                           message=None,
                                           is_initiator=False)

    def handle_cfp(self, message):
        """
        """
        self.agent.call_later(1.0, self._handle_cfp, message)

    def _handle_cfp(self, message):
        """
        """
        super(CompContNet2, self).handle_cfp(message)
        self.message = message

        if self.agent.send_propose:
            display_message(self.agent.aid.name, 'CFP message received - It will be replyed.')
            answer = self.message.create_reply()
            answer.set_performative(ACLMessage.PROPOSE)
            answer.set_content(str(self.agent.pot_disp))
            self.agent.send(answer)
        else:
            display_message(self.agent.aid.name, 'CFP message received - It will not be replyed.')

    def handle_reject_propose(self, message):
        """
        """
        super(CompContNet2, self).handle_reject_propose(message)

        display_message(self.agent.aid.name,
                        'REJECT_PROPOSAL message received')

    def handle_accept_propose(self, message):
        """
        """
        super(CompContNet2, self).handle_accept_propose(message)

        display_message(self.agent.aid.name,
                        'ACCEPT_PROPOSE message received')

        answer = message.create_reply()
        answer.set_performative(ACLMessage.INFORM)
        answer.set_content('OK')
        self.agent.send(answer)


class AgentInitiator(Agent):

    def __init__(self, aid, participants):
        super(AgentInitiator, self).__init__(aid=aid,
                                             mode='simulation',
                                             debug=False)

        message = ACLMessage(ACLMessage.CFP)
        message.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
        message.set_content('60.0')

        for participant in participants:
            message.add_receiver(AID(name=participant))

        self.call_later(8.0, self.launch_contract_net_protocol, message)

    def launch_contract_net_protocol(self, message):
        comp = CompContNet1(self, message)
        self.behaviours.append(comp)
        comp.on_start()


class AgentParticipant(Agent):

    def __init__(self, aid, pot_disp, send_propose=True):
        super(AgentParticipant, self).__init__(aid=aid,
                                               mode='simulation',
                                               debug=False)
        self.pot_disp = pot_disp
        self.send_propose = send_propose
        comp = CompContNet2(self)

        self.behaviours.append(comp)

if __name__ == "__main__":
    port = int(argv[1])
    id_ = 1
    agents = list()
    participants_agents = list()

    for i in range(5):
        agent_name = 'agent_participant_{}@10.0.0.{}:{}'.format(port, id_, port)
        agent_part = AgentParticipant(AID(name=agent_name),
                                      uniform(100.0, 500.0),
                                      send_propose=choice([True, False]))
        agents.append((id_, agent_part))
        participants_agents.append((id_, agent_part))
        port += 1
        id_ += 1

    agent_name = 'agent_initiator_{}@10.0.0.{}:{}'.format(port, id_, port)
    agente_init = AgentInitiator(AID(name=agent_name),
                                 [i[1].aid.name for i in agents])
    agents.append((id_, agente_init))


    # TOPOLOGY CONFIGURATION

    try:
        os.remove('adj_array.txt')
    except FileNotFoundError as e:
        print('The file adj_array.txt is not present in this directory.')

    try:
        os.remove('bus_xy.txt')
    except FileNotFoundError as e:
        print('The file bus_xy.txt is not present in this directory.')

    topology = json.load(open('topology.json', 'r'))
    # inserção dos agentes no arquivo de configuração    
    x, y = 0, 0
    for i, agent_info in enumerate(agents, start=len(topology['agents'])):
        x += randint(10, 100)
        y += randint(10,100)
        agent_data = {'id': agent_info[0],
                      'name': agent_info[1].aid.name,
                      'network': 'subnetwork-1',
                      'coordinates': [x, y]}
        topology['agents'].append(agent_data)

    # configuração dos links físicos e lógicos de comunicação
    aux1 = list()
    i = 1
    for agent_info in participants_agents:
        data = {'link-id': i,
                'source-id': id_,
                'target-id': agent_info[0]}
        aux1.append(data)
        i += 1
    topology['physical-links'] = aux1

    # configuração dos links lógicos de comunicação
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
        aux[0] += randint(10, 100)
        aux[1] += randint(10, 100)
        coords.append([i['id'], aux[0], aux[1]])
    coords = np.array(coords)
    np.savetxt('bus_xy.txt', coords, delimiter=',', fmt='%d')

    start_loop([i[1] for i in agents])
