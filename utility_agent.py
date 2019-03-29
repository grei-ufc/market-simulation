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

import pandas as pd
import numpy as np
import json
import pickle
from calc_methods import utility_curve
import random

MOSAIK_MODELS = {
    'api_version': '2.2',
    'models': {
        'UtilityAgent': {
            'public': True,
            'params': [],
            'attrs': ['clear_price'],
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
        '''
        
        '''
        if time % (5 * 60) == 0 and time != 0: # a cada 5 min
            pass

        return time + self.step_size


    def handle_set_data(self):
        print('sucess in set_data process')

    def get_data(self, outputs):
        data = {}
        for eid, attrs in outputs.items():
            data[eid] = {}
            for attr in attrs:
                if attr not in MOSAIK_MODELS['models']['UtilityAgent']['attrs']:
                    raise ValueError('Unknown output attribute: {}'.format(attr))
                data[eid][attr] = getattr(self.agent, 'clear_price')
        return data


class AuctionPropose(FipaContractNetProtocol):
    '''AuctionPropose

       FIPA-ContractNet Participant Behaviour that runs when an agent
       receives a CFP message. This comportment implements the auction
       role of the DeviceAgent sending a propose for concentrator agent
       with the demand curve in message content.'''

    def __init__(self, agent):
        super(AuctionPropose, self).__init__(agent=agent,
                                             message=None,
                                             is_initiator=False)


    def handle_cfp(self, message):
        """
        """
        self.agent.call_later(random.uniform(0.1, 0.2), self._handle_cfp, message)

    def _handle_cfp(self, message):
        """
        """
        super(AuctionPropose, self).handle_cfp(message)
        self.message = message

        display_message(self.agent.aid.name, 'CFP message received')

        # =================================================
        # calcula a curva de preço vs. demanda
        # =================================================
        self.agent.calc_utility_curve()
        content = pickle.dumps(self.agent.utility_curve)
        answer = self.message.create_reply()
        answer.set_performative(ACLMessage.PROPOSE)
        answer.set_content(content)
        self.agent.send(answer)

    def handle_reject_propose(self, message):
        """
        """
        super(AuctionPropose, self).handle_reject_propose(message)

        display_message(self.agent.aid.name,
                        'REJECT_PROPOSAL message received')

    def handle_accept_propose(self, message):
        """
        """
        super(AuctionPropose, self).handle_accept_propose(message)

        self.agent.clear_price = float(message.content)
        display_message(self.agent.aid.name,
                        'CLEAR PRICE RECEIVED: U${:05.2f}'.format(self.agent.clear_price))

        answer = message.create_reply()
        answer.set_performative(ACLMessage.INFORM)
        answer.set_content('OK')
        self.agent.send(answer)


class SellEnergyBehaviour(FipaRequestProtocol):
    """Comportamento FIPA Request
    do agente Relogio"""
    def __init__(self, agent):
        super(SellEnergyBehaviour, self).__init__(agent=agent,
                                                            is_initiator=False)

    def handle_request(self, message):
        content = json.loads(message.content)
        if content['type'] == 'BUY_ENERGY':
            display_message(self.agent.aid.name,
                            'Utility received a propose of {:03.2f} kW'.format(content['qtd']))
            answer = message.create_reply()
            answer.set_performative(ACLMessage.INFORM)
            content = {'type': 'ENERGY_BUYED',
                       'qtd': content['qtd']}
            answer.set_content(json.dumps(content))
            self.agent.send(answer)
        elif content['type'] == 'QUERY_PRICE':
            display_message(self.agent.aid.name,
                            'Utility received a query for energy prices')
            answer = message.create_reply()
            answer.set_performative(ACLMessage.INFORM)
            content = {'type': 'PRICES',
                       'prices': self.agent.prices}
            answer.set_content(json.dumps(content))
            self.agent.send(answer)


class UtilityAgent(Agent):
    def __init__(self, aid):
        super(UtilityAgent, self).__init__(aid=aid, debug=False)
        self.mosaik_sim = MosaikSim(self)
        self.utility_curve = np.zeros(50)
        self.clear_price = None
        self.prices = (10.0, 20.0)

        b1 = AuctionPropose(self)
        self.behaviours.append(b1)

        b2 = SellEnergyBehaviour(self)
        self.behaviours.append(b2)

    def calc_utility_curve(self):
        '''
        '''

        # =================================================
        # lógica para formação da curva de demanda de 
        # carga livre do usuário 
        # =================================================
        t, y1 = utility_curve()
        self.utility_curve = (t, y1)
