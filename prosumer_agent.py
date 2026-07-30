#!coding=utf-8
# Hello world in PADE!
#
# Criado por Lucas S Melo em 21 de julho de 2015 - Fortaleza, Ceará - Brasil

from pade.misc.utility import display_message
from pade.core.agent import Agent
from pade.acl.aid import AID
from pade.acl.messages import ACLMessage
from pade.behaviours.protocols import FipaContractNetProtocol
from pade.behaviours.protocols import FipaSubscribeProtocol
from pade.behaviours.protocols import FipaRequestProtocol
from pade.drivers.mosaik_driver import MosaikCon

import numpy as np
import pandas as pd
import json
import pickle
from ast import literal_eval
import random
import h5py
from calc_methods import demand_curve
from load_data import get_load_data, get_gen_data

MOSAIK_MODELS = {
    'api_version': '2.2',
    'models': {
        'ProsumerAgent': {
            'public': True,
            'params': [],
            'attrs': ['demand', 'demand_diff', 'p_out', 'vpa', 'vpb', 'vpc'],
        },
    },
}

SCHEDULE_TIME = None
TIME_INTERVAL = 15 * 60
OPERATION_TIME_DELAY = 0

class MosaikSim(MosaikCon):

    def __init__(self, agent):
        super(MosaikSim, self).__init__(MOSAIK_MODELS, agent)

    def init(self, sid, eid_prefix, prosumer_ref, start, step_size):
        # self.sid = sid
        self.prosumer_ref = 'ProsumerSim0-0.Prosumer_{}'.format(prosumer_ref)
        self.eid_prefix = eid_prefix
        self.eid = '{}{}'.format(self.eid_prefix, prosumer_ref)
        self.start = start
        self.step_size = step_size
        return MOSAIK_MODELS

    def create(self, num, model):
        return [{'eid': self.eid, 'type': model}]

    def step(self, time, inputs):
        """
        Prosumer agent simulator step method
        :param time:
        :param inputs:
        :return:
        """

        real_time_demand = 0.0

        outputs = {}
        for dest_eid, attrs in inputs.items():
            attr = attrs.get('p_out', {})
            # print('---> {}: data received from:'.format(dest_eid))
            for src_fullid, val in attr.items():
                # print('    {} --> p_out: {:5.2f}'.format(src_fullid, val))

                device_type = src_fullid.split(':')[1]

                if device_type == 'user_action_device':
                    # print('         ... Controling user action device')
                    real_time_demand += val
                    # sending commands to device
                    if self.agent.clear_price is None:
                        c = random.choice(['on', 'off'])
                        outputs[src_fullid] = {'commands': c}
                    else:
                        pass
                elif device_type == 'stochastic_gen':
                    # print('         ... Controling stochastic gen device')
                    real_time_demand += val
                    # sending commands to device
                    if self.agent.clear_price is None:
                        c = random.choice(['on', 'off'])
                        outputs[src_fullid] = {'commands': c}
                    else:
                        pass
                elif device_type == 'freely_control_gen':
                    # print('         ... Controling freely control gen device')
                    # real_time_demand += val

                    # sending commands to device
                    if self.agent.clear_price is None:
                        c = random.choice(['on', 'off'])
                        outputs[src_fullid] = {'commands': {}}
                        # outputs[src_fullid] = {'commands': {'on_off': c}}
                    else:
                        pass
                elif device_type == 'storage_device':
                    # print('         ... Controling storage device')
                    real_time_demand += val
                    # sending commands to device
                    outputs[src_fullid] = {
                        'commands': {
                            'storage_mode': 'float',
                            'power_level': 0.0
                            }
                        }
                    if self.agent.storage_detailed_load is not None:
                        t = int((time - OPERATION_TIME_DELAY) / TIME_INTERVAL) + 1
                        if self.agent.storage_detailed_load[t] > 0.0:
                            outputs[src_fullid] = {
                                'commands': {
                                    'storage_mode': 'charge',
                                    'power_level': self.agent.storage_detailed_load[t]
                                    }
                                }
                        else:
                            outputs[src_fullid] = {
                                'commands': {
                                    'storage_mode': 'discharge',
                                    'power_level': self.agent.storage_detailed_load[t]
                                    }
                                }
                elif device_type == 'shiftable_load':
                    # print('         ... Controling shiftable load device')
                    # real_time_demand += val
                    # sending commands to device
                    if self.agent.clear_price is None:
                        c = random.choice(['on', 'off'])
                        outputs[src_fullid] = {'commands': c}
                    else:
                        pass
                elif device_type == 'buffering_device':
                    # print('         ... Controling buffering device')
                    # real_time_demand += val
                    # sending commands to device
                    if self.agent.clear_price is None:
                        c = random.choice(['on', 'off'])
                        outputs[src_fullid] = {'commands': c}
                    else:
                        pass

        self.agent.real_time_demand = real_time_demand
        # =================================================
        # envio de comandos para os dispositivos modelados
        # no Mosaik
        # =================================================
        from_ = self.eid

        yield self.set_data_async({from_: outputs})

        return time + self.step_size

    def handle_set_data(self):
        pass

    def get_data(self, outputs):
        data = {}
        for eid, attrs in outputs.items():
            data[eid] = {}
            for attr in attrs:
                if attr not in MOSAIK_MODELS['models']['ProsumerAgent']['attrs']:
                    raise ValueError('Unknown output attribute: {}'.format(attr))
                data[eid][attr] = getattr(self.agent, attr)
        return data


class ProsumerInitiatorRequestProtocol(FipaRequestProtocol):
    """FIPA Request Behaviour.
    """
    def __init__(self, agent, message):
        super(ProsumerInitiatorRequestProtocol, self).__init__(agent=agent,
                                                               message=message,
                                                               is_initiator=True)

    def handle_inform(self, message):
        content = pickle.loads(literal_eval(message.content))

        # aramazena o valor de energia a ser comprado no mercado bilateral
        self.agent.bilateral_contract_purchase = content['bilateral_contract_purchase']

        # armazena schedule de storage no banco de dados do agente
        self.agent.storage_forecast = content['storage_schedule']

        display_message(self.agent.aid.localname, 'STORAGE SCHEDULE RECEIVED')

        # calcula o schedule total do prosumer para enviar ao BESS
        # TODO: atualizar os valores de previsao de carga e de geração 
        # de acordo com o tempo de simulação
        detailed_load = self.agent.load_forecast - self.agent.gen_forecast
        storage_detailed_load = self.agent.storage_forecast

        self.agent.detailed_load = detailed_load

        self.agent.storage_detailed_load = storage_detailed_load

        content = dict()
        content['bilateral_contract_purchase'] = self.agent.bilateral_contract_purchase
        content['detailed_load'] = detailed_load
        content['storage_detailed_load'] = storage_detailed_load
        content['prosumer_storage_config'] = self.agent.storage_config

        self.agent.comp_cnp_1.answer.set_content(pickle.dumps(content))
        self.agent.comp_cnp_1.answer.set_message_length(np.random.randint(1000, 1500))
        self.agent.send(self.agent.comp_cnp_1.answer)


class ProsumerParticipantRequestProtocol(FipaRequestProtocol):
    """FIPA Request Behaviour.
    """
    def __init__(self, agent):
        super(ProsumerParticipantRequestProtocol, self).__init__(agent=agent,
                                                                 message=None,
                                                                 is_initiator=False)

    def handle_request(self, message):
        super(ProsumerParticipantRequestProtocol, self).handle_request(message)
        display_message(self.agent.aid.localname, 'request message received')
        reply = message.create_reply()
        reply.set_performative(ACLMessage.INFORM)
        config = dict()
        content = pickle.dumps(config)
        reply.set_content(content)
        reply.set_message_length(np.random.randint(1000, 1500))
        self.agent.send(reply)


class ProsumerContractNetProtocol(FipaContractNetProtocol):
    """AuctionPropose

    FIPA-ContractNet Participant Behaviour that runs when an agent
    receives a CFP message. This behaviour implements the auction
    role of the ProsumerAgent sending a propose for BESS agent
    with the demand curve in message content."""

    def __init__(self, agent):
        super(ProsumerContractNetProtocol, self).__init__(agent=agent,
                                                          message=None,
                                                          is_initiator=False)

    def handle_cfp(self, message):
        """
        """
        if message.content == 'REQUEST FOR AUCTION':
            self.agent.call_later(random.uniform(0.1, 0.2),
                                  self._handle_cfp_for_auction, message)
        elif message.content == 'REQUEST FOR SCHEDULE':
            self.agent.call_later(random.uniform(0.1, 0.2),
                                  self._handle_cfp_for_schedule, message)

    def _handle_cfp_for_auction(self, message):
        """
        """
        super(ProsumerContractNetProtocol, self).handle_cfp(message)
        reply = message.create_reply()
        reply.set_performative(ACLMessage.PROPOSE)

        #######################################################
        #    CALCULO IMPORTANTE PARA OPERAÇÃO DO SISTEMA
        #######################################################
        time_index = int((self.agent.mosaik_sim.time - OPERATION_TIME_DELAY) / TIME_INTERVAL) + 2

        # fator de desvio
        if time_index == 10:
            fd = np.random.uniform(0.8, 1.2)
        else:
            fd = 1.0
        
        # valor programado para consumo/entrega de energia para o proximo intervalo de 30 min
        a = self.agent.detailed_load[time_index]
        a_ = self.agent.storage_detailed_load[time_index]
        # valor mais atual previsto para daqui a 30 min
        b = a * fd
        b_ =  a_
        # valor contratatado no mercado da termo
        c = self.agent.bilateral_contract_purchase[time_index] 
        # diferençao entre o valor de energia programado e o realizado
        d = np.linalg.norm((a + a_) - (b + b_))

        # Calculo da diferença entre o valor de energia contratado no mercado a termo
        # e o valor de energia necessária para suprir as necessidades do prosumer.
        # Nesse caso não há excedente de geração e o bid é de compra de energia
        if (b + b_) >= 0:
            if (b + b_) > c:
                demand_bid = (b + b_) - c
            else:
                demand_bid = 0.0
        # caso haja excende de geração, o bid será para venda de energia
        else:
            demand_bid = (b + b_)

        display_message(self.agent.aid.name,
                        'BID FOR REAL TIME MARKET: {:5.3f}'.format(demand_bid))
        config = dict()
        config['real_time_demand_bid'] = demand_bid
        config['real_time_load_value'] = b
        config['real_time_storage_value'] = b_
        #######################################################################
        #######################################################################

        content = pickle.dumps(config)
        reply.set_content(content)
        reply.set_message_length(np.random.randint(100, 500))
        self.agent.send(reply)

    def _handle_cfp_for_schedule(self, message):

        config = dict()
        if 'storage_device' in self.agent.param_device_dict.keys():
            config['has_storage'] = True
            config['storage_rate'] = self.agent.param_device_dict['storage_device']['rate']
            config['storage_size'] = self.agent.param_device_dict['storage_device']['size']
            config['max_energy_flow'] = self.agent.param_device_dict['storage_device']['max_energy_flow']
            config['max_soc'] = self.agent.param_device_dict['storage_device']['max_soc']
            config['min_soc'] = self.agent.param_device_dict['storage_device']['min_soc']
        else:
            config['has_storage'] = False

        config['bilateral_price'] = 38.0
        config['bilateral_max'] = 5.0

        config['node_id'] = int(self.agent.node_id)

        if 'user_action_device' in self.agent.param_device_dict.keys():
            config['load_kw'] = self.agent.param_device_dict['user_action_device']['size']

        if 'stochastic_gen' in self.agent.param_device_dict.keys():
            config['gen_kw'] = self.agent.param_device_dict['stochastic_gen']['size']
        else:
            config['gen_kw'] = 0.0

        self.agent.storage_config = config

        message = ACLMessage(ACLMessage.REQUEST)
        message.set_protocol(ACLMessage.FIPA_REQUEST_PROTOCOL)
        message.add_receiver(AID(name='solver'))

        content = pickle.dumps(self.agent.storage_config)
        message.set_content(content)

        # Envia mensagem solicitando execução do algoritmo de otimização
        # para definir schedule do dispositivo de armazenamento.
        # Enquanto o procedimento de otimização é executado pelo solver agent
        # o agente posumer aguarda para que após o recebimento do schedule
        #  otimizado responda a mensagem de CFP recebida do agente BESS

        if self.agent.comp_request_2 is None:
            self.agent.comp_request_2 = ProsumerInitiatorRequestProtocol(self.agent, message)
            self.agent.behaviours.append(self.agent.comp_request_2)
            self.agent.comp_request_2.on_start()
        else:
            self.agent.comp_request_2.message = message
            self.agent.comp_request_2.on_start()

        self.answer = self.message.create_reply()
        self.answer.set_performative(ACLMessage.PROPOSE)

    def handle_reject_propose(self, message):
        """
        """
        super(ProsumerContractNetProtocol, self).handle_reject_propose(message)

        display_message(self.agent.aid.name, 'REJECT_PROPOSAL message received')

    def handle_accept_propose(self, message):
        """
        """
        super(ProsumerContractNetProtocol, self).handle_accept_propose(message)

        display_message(self.agent.aid.name, 'ACCEPT_PROPOSAL message received')

        answer = message.create_reply()
        answer.set_performative(ACLMessage.INFORM)
        answer.set_content('OK')

        answer.set_message_length(100)
        self.agent.send(answer)


class ProsumerSubscriberProtocol(FipaSubscribeProtocol):
    def __init__(self, agent, message):
        super(ProsumerSubscriberProtocol, self).__init__(agent,
                                                         message,
                                                         is_initiator=True)
        pass

    def handle_agree(self, message):
        display_message(self.agent.aid.name, message.content)

    def handle_inform(self, message):

        config = pickle.loads(literal_eval(message.content))
        if config['message_type'] == 'AUCTION_PRICE':
            pass
        elif config['message_type'] == 'STORAGE_SCHEDULE':
            prosumer_storage_detailed_load = config['prosumer_storage_detailed_load']
            for i, j in prosumer_storage_detailed_load.items():
                if i == self.agent.node_id:
                    display_message(self.agent.aid.name, 'PROSUMER {} STORAGE UPDATED'.format(self.agent.node_id))
                    self.agent.storage_detailed_load = j
        elif config['message_type'] == 'STORAGE_SCHEDULE_2':
            time = int((self.agent.mosaik_sim.time -
                        OPERATION_TIME_DELAY) /
                       TIME_INTERVAL) + 2
            prosumer_storage_detailed_load = config['prosumer_storage_detailed_load']
            for i, j in prosumer_storage_detailed_load.items():
                if i == self.agent.node_id:
                    display_message(self.agent.aid.name, 'PROSUMER {} STORAGE UPDATED'.format(self.agent.node_id))
                    self.agent.storage_detailed_load[time] = j
        else:
            return

        reply = message.create_reply()
        reply.set_performative(ACLMessage.INFORM)
        config = dict()
        config['message_type'] = 'SUBSCRIBER CONFIRM'
        content = pickle.dumps(config)
        reply.set_content(content)
        reply.set_message_length(100)
        self.agent.send(reply)


class ProsumerAgent(Agent):
    def __init__(self, aid, node_id, bess_id, params, mode):
        super(ProsumerAgent, self).__init__(aid=aid, debug=False, mode=mode)
        self.node_id = node_id
        self.bess_id = bess_id
        self.mosaik_sim = MosaikSim(self)
        self.param_device_dict = params

        self.detailed_load = None
        self.storage_detailed_load = None
        self.storage_config = None

        self.schedule = None
        self.real_time_demand = 0.0

        self.demand_diff = 0.0
        self.bilateral_contract_purchase = 0.0

        # inicialização das variaveis de previsão de carga, geração e armazenamento
        self.load_forecast = get_load_data(load_index=int(self.node_id))
        self.load_forecast = self.load_forecast.pload[:24*4]
        # normalizacao dos valores de carga retornados
        self.load_forecast = (self.load_forecast-self.load_forecast.min())/(self.load_forecast.max()-self.load_forecast.min())
        # escala os valores pelo fator de carga maxima
        # e transforma o dataframe em array
        load_max = self.param_device_dict['user_action_device']['size']
        self.load_forecast = load_max * self.load_forecast.values

        if 'stochastic_gen' in self.param_device_dict.keys():
            self.gen_forecast = get_gen_data(gen_index=int(self.node_id))
            self.gen_forecast = self.gen_forecast.pgen[:24*4]
            # normalizacao dos valores de geracao retornados
            self.gen_forecast = (self.gen_forecast-self.gen_forecast.min())/(self.gen_forecast.max()-self.gen_forecast.min())
            # escala os valores pelo fator de geracao maxima
            # e transforma o dataframe em array
            gen_max = self.param_device_dict['stochastic_gen']['size']
            self.gen_forecast = gen_max * self.gen_forecast.values

        else:
            self.gen_forecast = np.zeros(96)

        self.storage_forecast = np.zeros(96)

        self.clear_price = None

        self.comp_cnp_1 = ProsumerContractNetProtocol(self)
        self.behaviours.append(self.comp_cnp_1)

        self.comp_request_1 = ProsumerParticipantRequestProtocol(self)
        self.behaviours.append(self.comp_request_1)

        self.comp_request_2 = None

        msg = ACLMessage(ACLMessage.SUBSCRIBE)
        msg.set_protocol(ACLMessage.FIPA_SUBSCRIBE_PROTOCOL)
        msg.set_content('Subscription request')
        msg.add_receiver(AID(name='bess{}'.format(self.bess_id)))
        msg.set_message_length(100)

        self.call_later(8.0, self.launch_subscriber_protocol, msg)

    def launch_subscriber_protocol(self, message):
        self.comp_pubsub_1 = ProsumerSubscriberProtocol(self, message)
        self.behaviours.append(self.comp_pubsub_1)
        self.comp_pubsub_1.on_start()
