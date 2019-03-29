#!coding=utf-8
# Hello world in PADE!
#
# Criado por Lucas S Melo em 21 de julho de 2015 - Fortaleza, Ceará - Brasil

from pade.misc.utility import display_message, call_in_thread, defer_to_thread
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
from calc_methods import demand_curve
from util import generate_timeseries
import random

MOSAIK_MODELS = {
    'api_version': '2.2',
    'models': {
        'ProsumerAgent': {
            'public': True,
            'params': [],
            'attrs': ['device_status'],
        },
    },
}

class MosaikSim(MosaikCon):

    def __init__(self, agent):
        super(MosaikSim, self).__init__(MOSAIK_MODELS, agent)
        self.prosumer_sim_prefix = 'ProsumerSim0-0.Prosumer_'
        self.prosumer_data = {'stochastic_gen': [],
                              'freely_control_gen': [],
                              'shiftable_load': [],
                              'buffering_device': [],
                              'user_action_device': [],
                              'storage_device': []}

    def init(self, sid, eid_prefix, prosumer_ref, start, step_size):
        # self.sid = sid
        self.prosumer_ref = 'ProsumerSim0-0.Prosumer_{}'.format(prosumer_ref)
        self.eid_prefix = eid_prefix
        self.eid = '{}{}'.format(self.eid_prefix, prosumer_ref)
        self.start = start
        self.step_size = step_size
        return MOSAIK_MODELS


    def create(self, num, model):
        entities = list()
        # self.eid = '{}0'.format(self.eid_prefix)
        entities.append(
            #{'eid': self.sim_id + '.' + str(i), 'type': model, 'rel': []})
            {'eid': self.eid, 'type': model})
        return entities

    def step(self, time, inputs):
        '''
        {'ProsumerAgent_10': 
            {'device_status': 
                {'ProsumerSim0-0.Prosumer_10': 
                    {'stochastic_gen': {'status': 0, 'demand': 0.0, 'forecast': 0.0},
                     'freely_control_gen': {'status': 0, 'demand': 0.0, 'forecast': 0.0},
                     'shiftable_load': {'status': 0, 'demand': 0.0, 'forecast': 0.0},
                     'buffering_device': {'status': 0, 'demand': 0.0, 'forecast': 0.0},
                     'user_action_device': {'status': 1, 'demand': 0.0649, 'forecast': 0.0},
                     'storage_device': {'status': 1, 'demand': 0.0, 'forecast': 0.0}
                    }
                }
            }
        }
        '''

        # lança comportamento que estabelece contrato com a concessionária 
        if time == 0 or time % (2 * 24 * 60 * 60) == 0:
            message = ACLMessage(ACLMessage.REQUEST)
            message.set_protocol(ACLMessage.FIPA_REQUEST_PROTOCOL)
            message.add_receiver(AID(name='utility'))
            content = {'type': 'QUERY_PRICE'}
            message.set_content(json.dumps(content))
            
            if time == 0:
                self.req_energ_to_utility = RequestEnergyToUtility(self.agent,
                                                                   message)
                self.agent.behaviours.append(self.req_energ_to_utility)
                self.req_energ_to_utility.on_start()
            else:
                self.req_energ_to_utility.message = message
                self.req_energ_to_utility.on_start()
            display_message(self.agent.aid.name,
                            'Query Prices Requested to utility.')

        if time % (5 * 60) == 0 and time != 0: # a cada 5 min
            # print(inputs)

            # =================================================
            # armazenamento dos parâmetros vindos do Mosaik
            # No momento apenas: staus e demanda.
            # =================================================

            for eid, attrs in inputs.items():

                device_status = attrs.get('device_status', {})
                for prosumer_eid, device_status_ in device_status.items():
                    
                    if device_status_.get('stochastic_gen'):
                        self.prosumer_data['stochastic_gen'].append(device_status_['stochastic_gen']['power'])
                    else:
                        self.prosumer_data['stochastic_gen'].append(0.0)

                    if device_status_.get('freely_control_gen'):
                        self.prosumer_data['freely_control_gen'].append(device_status_['freely_control_gen']['power'])
                    else:
                        self.prosumer_data['freely_control_gen'].append(0.0)
                    
                    if device_status_.get('shiftable_load'):
                        self.prosumer_data['shiftable_load'].append(device_status_['shiftable_load']['power'])
                    else:
                        self.prosumer_data['shiftable_load'].append(0.0)
                    
                    if device_status_.get('buffering_device'):
                        self.prosumer_data['buffering_device'].append(device_status_['buffering_device']['power'])
                    else:
                        self.prosumer_data['buffering_device'].append(0.0)
                    
                    if device_status_.get('user_action_device'):
                        self.prosumer_data['user_action_device'].append(device_status_['user_action_device']['power'])
                    else:
                        self.prosumer_data['user_action_device'].append(0.0)

                    if device_status_.get('storage_device'):
                        self.prosumer_data['storage_device'].append(device_status_['storage_device']['power'])
                    else:
                        self.prosumer_data['storage_device'].append(0.0)

            # =================================================
            # Definição dos comandos a serem enviados aos
            # dispositivos. Aqui deve estar a maior parte da 
            # inteligencia do sistema 
            # =================================================


            # =================================================
            # envio de comandos para os dispositivos modelados
            # no Mosaik
            # =================================================

            from_ = self.eid
            to_ = self.prosumer_ref
            data = {from_: {to_: {'commands': self.agent.device_dict}}}
            yield self.set_data_async(data)
            

            # message = ACLMessage(ACLMessage.REQUEST)
            # message.set_protocol(ACLMessage.FIPA_REQUEST_PROTOCOL)
            # message.add_receiver(AID(name='concentrator'))
            # message.set_content('communication')
            # comp = SendInformToAgentConcentrator(self.agent, message)
            # self.agent.behaviours.append(comp)
            # comp.on_start()

        ###################### FIX #############################

        # Após uma semana de simulação um valor de contrato deve ser fechado com
        # a concessionária. Esse valor será calculado neste pondo do código
        if time >= (7 * 24 * 60 * 60):
            pass

        # armazena os dados da simulação
        if time % (1 * 24 * 60 * 60) == 0 and time != 0: # a cada dois dias

            datetimes = generate_timeseries(start=self.start,
                                            time=time,
                                            step=15)
            self.prosumer_data_df = pd.DataFrame(self.prosumer_data)
            self.prosumer_data_df.index = datetimes
            self.prosumer_data_df.to_json('data/{}.json'.format(self.prosumer_ref))
            display_message(self.agent.aid.localname, 'data_recorded.')
        return time + self.step_size

    # def handle_get_data(self, data):
    #     print(data)

    def handle_set_data(self):
        pass

    # def handle_get_progress(self, progress):
    #     print(progress)

    def get_data(self, outputs):
        data = {}
        for eid, attrs in outputs.items():
            data[eid] = {}
            for attr in attrs:
                if attr not in MOSAIK_MODELS['models']['ProsumerAgent']['attrs']:
                    raise ValueError('Unknown output attribute: {}'.format(attr))
                data[eid][attr] = getattr(self.agent, 'device_dict')
        return data


class AuctionPropose(FipaContractNetProtocol):
    '''AuctionPropose

       FIPA-ContractNet Participant Behaviour that runs when an agent
       receives a CFP message. This comportment implements the auction
       role of the ProsumerAgent sending a propose for concentrator agent
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
        self.agent.calc_the_demand_curves()
        content = pickle.dumps(self.agent.dm_curve)
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


class RequestEnergyToUtility(FipaRequestProtocol):
    """Comportamento FIPA Request
    do agente Relogio"""
    def __init__(self, agent, message):
        super(RequestEnergyToUtility, self).__init__(agent=agent,
                                                     message=message,
                                                     is_initiator=True)

    def handle_inform(self, message):
        content = json.loads(message.content)
        if content['type'] == 'ENERGY_BUYED':
            display_message(self.agent.aid.localname,
                            'Energy Buyed from utility: {:03.2f} kW'.format(content['qtd']))
        elif content['type'] == 'PRICES':
            display_message(self.agent.aid.name,
                            'Prices received from utility {}'.format(content['prices']))
            
            # processo de otimizacao estocastica aqui
            utility_prices = content['prices']
            defer_to_thread(call_pyomo, self.optimal_value)

            answer = message.create_reply()
            answer.set_performative(ACLMessage.REQUEST)
            content = {'type': 'BUY_ENERGY',
                       'qtd': random.uniform(10, 20)}
            answer.set_content(json.dumps(content))
            self.agent.send(answer)
            display_message(self.agent.aid.name,
                            'Buying {:03.2f} kW from utility'.format(content['qtd']))

    def optimal_value(self, value):
        display_message(self.agent.aid.name, 'Value: {}'.format(value)) 

class ProsumerAgent(Agent):
    def __init__(self, aid, node_id):
        super(ProsumerAgent, self).__init__(aid=aid, debug=False)
        self.node_id = node_id
        self.mosaik_sim = MosaikSim(self)
        self.dm_curve = np.zeros(50)
        self.clear_price = None

        # open the config.json file with some important informations about
        # the device characteristics, read and store this information.
        config = json.load(open('config.json'))

        '''This part of code create a dictionary like this:

            {'stochastic_gen': {'power': 5.41, 'status': None, 'demand': None},
            'shiftable_load': {'power': 2.02, 'status': None, 'demand': None},
            'buffering_device': {'power': 2.1, 'status': None, 'demand': None},
            'user_action_device': {'power': 5.55, 'status': None, 'demand': None}}

        '''
        self.device_dict = dict()
        for device_type, device_info in config['devices'].items():
            if str(self.node_id) in device_info['powers'].keys():
                self.device_dict[device_type] = {'power': device_info['powers'][str(self.node_id)],
                                                 'status': None,
                                                 'demand': None}
        # print(self.aid.name)
        # print(self.device_dict)

        comp = AuctionPropose(self)
        self.behaviours.append(comp)

    def calc_the_demand_curves(self, prosumer_data=None):
        '''The parameter prosumer_data is a dictionary like this:
            {'stochastic_gen': [...],
            'shiftable_load': [...],
            'buffering_device': [...],
            'user_action_device': [...]}
        '''

        # =================================================
        # lógica para formação da curva de demanda de 
        # carga livre do usuário 
        # =================================================
        t, y1 = demand_curve(tm = random.uniform(0.5, 4.5),
                             ymin= random.uniform(1.0, 2.0), 
                             ymax= random.uniform(3.0, 5.0))

        # =================================================
        # lógica para formação da curva de demanda de 
        # geração intermitente
        # =================================================
        t, y2 = demand_curve(tm = random.uniform(0.5, 4.5),
                             ymin= - random.uniform(3.0, 5.0),
                             ymax= - random.uniform(1.0, 2.0))
        # =================================================
        # lógica para formação da curva de demanda de 
        # geração controlável 
        # =================================================
        t, y3 = demand_curve(tm = random.uniform(0.5, 4.5),
                             ymin= - random.uniform(3.0, 5.0),
                             ymax= - random.uniform(1.0, 2.0))

        # =================================================
        # lógica para formação da curva de demanda de 
        # dispositivo de armazenamento 
        # =================================================
        t, y4 = demand_curve(tm = random.uniform(0.5, 4.5),
                             ymin= random.uniform(1.0, 2.0),
                             ymax= random.uniform(3.0, 5.0))

        # =================================================
        # lógica para formação da curva de demanda de 
        # carga controlável
        # =================================================
        t, y5 = demand_curve(tm = random.uniform(0.5, 4.5),
                             ymin= random.uniform(1.0, 2.0), 
                             ymax= random.uniform(3.0, 5.0))

        self.dm_curve = (t, y1 + y2 + y3 + y4 + y5)

def call_pyomo():
    import time
    time.sleep(8.0)
    return random.uniform(0, 10)
