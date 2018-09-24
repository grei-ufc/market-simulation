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
        'DeviceAgent': {
            'public': True,
            'params': ['prosumers_id'],
            'attrs': ['power_forecast'],
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
        
        # Comportamento a cada 5 min
        if time % (5 * 60) == 0 and time != 0:
            print(inputs)
            message = ACLMessage(ACLMessage.REQUEST)
            message.set_protocol(ACLMessage.FIPA_REQUEST_PROTOCOL)
            message.add_receiver(AID(name='concentrator'))
            message.set_content('communication')
            comp = SendInformToAgentConcentrator(self.agent, message)
            self.agent.behaviours.append(comp)
            comp.on_start()
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


class SendInformToAgentConcentrator(FipaRequestProtocol):
    """Comportamento FIPA Request
    do agente Relogio"""
    def __init__(self, agent, message):
        super(SendInformToAgentConcentrator, self).__init__(agent=agent,
                                                            message=message,
                                                            is_initiator=True)

    def handle_inform(self, message):
        display_message(self.agent.aid.localname, message.content)


class DeviceAgent(Agent):
    def __init__(self, aid):
        super(DeviceAgent, self).__init__(aid=aid, debug=False)
        self.mosaik_sim = MosaikSim(self)

