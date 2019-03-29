#!coding=utf-8
# Hello world in PADE!
#
# Criado por Lucas S Melo em 21 de julho de 2015 - Fortaleza, Ceará - Brasil

from pade.misc.utility import display_message
from pade.core.agent import Agent
from pade.acl.aid import AID
from pade.acl.messages import ACLMessage
from pade.behaviours.protocols import FipaRequestProtocol
from pade.behaviours.protocols import TimedBehaviour
from pade.behaviours.protocols import FipaContractNetProtocol
from pade.drivers.mosaik_driver import MosaikCon
from pade.misc.utility import call_later

from twisted.internet import defer

from start_mosaik_sim import load_low_voltage_prosumers
import pickle
import numpy as np

from time import sleep

import matplotlib.pyplot as plt

MOSAIK_MODELS = {
    'api_version': '2.2',
    'models': {
        'ConcentratorAgent': {
            'public': True,
            'params': [],
            'attrs': ['device_status', 'clear_price'],
        },
    },
}

class MosaikSim(MosaikCon):

    def __init__(self, agent):
        super(MosaikSim, self).__init__(MOSAIK_MODELS, agent)
        self.entities = list()
        self.comp = None


    def init(self, sid, eid_prefix, start, step_size):
        self.eid_prefix = eid_prefix
        self.start = start
        self.step_size = step_size
        return MOSAIK_MODELS


    def create(self, num, model):
        entities_info = list()
        for i in range(num):
            entities_info.append(
                {'eid': self.sim_id + '.' + str(i), 'type': model, 'rel': []})
        return entities_info

    def step(self, time, inputs):

        # Inicia o mercado após período de aquisição de dados de uma semana 
        # com negociações a cada uma hora.
        if time % (1 * 60 * 60) == 0 and time != 0 and time >= (7* 24 * 60 * 60):
            message = ACLMessage(ACLMessage.CFP)
            message.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
            message.set_content('SEND YOUR PROPOSE')

            for participant in self.agent.participants:
                message.add_receiver(AID(name=participant))

            self.agent.call_later(0.1, self.launch_contract_net_protocol, message)
            return
            # self.launch_contract_net_protocol(message)
            # d = defer.Deferred()
            # d.addCallback(self.next_step)
            # self.agent.call_later(1.0, d.callback, time)

            # return d

        return time + self.step_size


    def next_step(self, time):
        return time + self.step_size

    def launch_contract_net_protocol(self, message):
        print('Launch FIPA-ContractNet...')
        self.agent.auction_finished = False
        if self.comp is None:
            self.comp = AuctionClear(self.agent, message)
            self.agent.behaviours.append(self.comp)
            self.comp.on_start()
        else:
            self.comp.message = message
            self.comp.on_start()

    def get_data(self, outputs):
        data = {}
        for eid, attrs in outputs.items():
            data[eid] = {}
            for attr in attrs:
                if attr not in MOSAIK_MODELS['models']['ConcentratorAgent']['attrs']:
                    raise ValueError('Unknown output attribute: {}'.format(attr))
                data[eid][attr] = getattr(self.agent, 'clear_price')
        return data

class AuctionClear(FipaContractNetProtocol):
    '''AuctionClear

       Initial FIPA-ContractNet Behaviour that sends CFP messages
       to other DeviceAgents asking for curves proposals.
       This behaviour also analyzes the proposals and sum its
       to find the cler value for the state of network.'''

    def __init__(self, agent, message):
        super(AuctionClear, self).__init__(
            agent=agent, message=message, is_initiator=True)
        self.cfp = message

    def handle_all_proposes(self, proposes):
        """
        """

        super(AuctionClear, self).handle_all_proposes(proposes)

        display_message(self.agent.aid.name, 'Analyzing proposals...')

        self.t = np.linspace(0.0, 5.0, 50)
        self.y = np.zeros(50)
        accepted_proposes_aids = list()
        not_accepted_proposes_aids = list()
        # logic to select proposals by the higher available power.
        # In the propose analysis some others restrictions need to be
        # verified, like the price interval that needs to be in conformance.   
        for message in proposes:
            display_message(self.agent.aid.name,'PROPOSE message from {}'.format(message.sender.name))

            t, y = pickle.loads(message.content)
            if self.t.all() == t.all():
                self.y += y
                accepted_proposes_aids.append(message.sender.name)
            else:
                not_accepted_proposes_aids.append(message.sender.name)

        # finfding the clear price
        try:
            index_ = np.where(self.y[:-1] * self.y[1:] < 0.0)[0][0]
            self.agent.clear_price = float((self.t[index_] + self.t[index_ + 1]) / 2.0)
            display_message(self.agent.aid.name, 'The clear price is U${:05.2f}'.format(self.agent.clear_price))
        except Exception as e:
            display_message(self.agent.aid.name, 'No match for clear price!')
            self.agent.clear_price = 0.0

        if not_accepted_proposes_aids:
            display_message(self.agent.aid.name, 'Sending REJECT_PROPOSAL answers...')
            answer = ACLMessage(ACLMessage.REJECT_PROPOSAL)
            answer.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
            answer.set_content('')
            for aid in not_accepted_proposes_aids:
                answer.add_receiver(aid)
            self.agent.send(answer)

        if accepted_proposes_aids:
            display_message(self.agent.aid.name, 'Sending ACCEPT_PROPOSAL answer...')
            answer = ACLMessage(ACLMessage.ACCEPT_PROPOSAL)
            answer.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
            answer.set_content(str(self.agent.clear_price))
            for aid in accepted_proposes_aids:
                answer.add_receiver(aid)
            self.agent.send(answer)

        self.agent.auction_finished = True

        self.agent.mosaik_sim.step_done()

    def handle_inform(self, message):
        """
        """
        super(AuctionClear, self).handle_inform(message)

        display_message(self.agent.aid.name, 'INFORM message received')

    def handle_refuse(self, message):
        """
        """
        super(AuctionClear, self).handle_refuse(message)

        display_message(self.agent.aid.name, 'REFUSE message received')

    def handle_propose(self, message):
        """
        """
        super(AuctionClear, self).handle_propose(message)

        display_message(self.agent.aid.name, 'PROPOSE message received')


class ReceiveInformFromProsumerAgent(FipaRequestProtocol):
    """Comportamento FIPA Request
    do agente Relogio"""
    def __init__(self, agent):
        super(ReceiveInformFromProsumerAgent, self).__init__(agent=agent,
                                                             message=None,
                                                             is_initiator=False)

    def handle_request(self, message):
        display_message(self.agent.aid.localname, message.content)


class ConcentratorAgent(Agent):
    def __init__(self, aid):
        super(ConcentratorAgent, self).__init__(aid=aid, debug=False)
        self.mosaik_sim = MosaikSim(self)

        self.clear_price = None
        self.auction_finished = False
        # carrega os nomes dos agentes participantes do leilão
        prosumers_id = load_low_voltage_prosumers('force.json')
        self.participants = list() 
        for p_id in prosumers_id:
            name = 'device' + str(p_id)
            self.participants.append(name)

        self.participants.append('utility')

        # Behaviours
        behaviour_1 = ReceiveInformFromProsumerAgent(self)
        self.behaviours.append(behaviour_1)
