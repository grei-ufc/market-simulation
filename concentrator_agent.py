#!coding=utf-8
# Hello world in PADE!
#
# Criado por Lucas S Melo em 21 de julho de 2015 - Fortaleza, Ceará - Brasil

from pade.misc.utility import display_message
from pade.misc.common import PadeSession
from pade.core.agent import Agent
from pade.acl.aid import AID
from pade.acl.messages import ACLMessage
from pade.behaviours.protocols import FipaRequestProtocol
from pade.behaviours.protocols import TimedBehaviour
from pade.drivers.mosaik_driver import MosaikCon

from time import sleep

MOSAIK_MODELS = {
    'api_version': '2.2',
    'models': {
        'ConcentratorAgent': {
            'public': True,
            'params': ['prosumers_id'],
            'attrs': [],
        },
    },
}

class MosaikSim(MosaikCon):

    def __init__(self, agent):
        super(MosaikSim, self).__init__(MOSAIK_MODELS, agent)
        self.entities = list()


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
        return time + self.step_size

    # def handle_get_data(self, data):
    #     print(data)

    # def handle_set_data(self):
    #     print('sucess in set_data process')

    # def handle_get_progress(self, progress):
    #     print(progress)

    def get_data(self, outputs):
        response = dict()
        for model, list_values in outputs.items():
            response[model] = dict()
            for value in list_values:
                response[model][value] = 1.0
        return response

class ReceiveInformFromAgentDevice(FipaRequestProtocol):
    """Comportamento FIPA Request
    do agente Relogio"""
    def __init__(self, agent):
        super(ReceiveInformFromAgentDevice, self).__init__(agent=agent,
                                                           message=None,
                                                           is_initiator=False)

    def handle_request(self, message):
        display_message(self.agent.aid.localname, message.content)

class ConcentratorAgent(Agent):
    def __init__(self, aid):
        super(ConcentratorAgent, self).__init__(aid=aid, debug=False)
        self.mosaik_sim = MosaikSim(self)

        # Behaviours
        behaviour_1 = ReceiveInformFromAgentDevice(self)
        self.behaviours.append(behaviour_1)
