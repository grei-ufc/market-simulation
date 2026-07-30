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

from pade.misc.utility import call_later
from twisted.internet import defer
from time import sleep

from start_mosaik_sim import load_low_voltage_prosumers

import numpy as np
import pandas as pd
import pickle
from ast import literal_eval
import random
import h5py
from pyfiglet import Figlet 


MOSAIK_MODELS = {
    'api_version': '2.2',
    'models': {
        'BESSAgent': {
            'public': True,
            'params': [],
            'attrs': ['demand', 'clear_price', 'vpa', 'vpb', 'vpc'],
        },
    },
}

SCHEDULE_TIME = 0
TIME_INTERVAL = 15 * 60
SEND_COMMANDS_TIME_DELAY = 0
OPERATION_TIME_DELAY = 60


class MosaikSim(MosaikCon):

    def __init__(self, agent):
        super(MosaikSim, self).__init__(MOSAIK_MODELS, agent)
        self.entities = dict()

        # parametros relacionados à analise de preços
        self.price_history_vector = list()
        self.max_buy_price = None # in US$ 
        self.min_sell_price = None # in US$
        self.clear_price = None
        self.auction_finished = False

    def init(self, sid, eid_prefix, bess_ref, start, step_size):
        self.eid_prefix = eid_prefix
        self.start = start
        self.step_size = step_size
        self.eid = '{}{}'.format(self.eid_prefix, bess_ref)
        self.bess_ref = 'BESSSim0-0.BESS_{}'.format(bess_ref)

        return MOSAIK_MODELS

    def create(self, num, model):
        return [{'eid': self.eid, 'type': model}]

    def step(self, time, inputs):

        if time == SCHEDULE_TIME:
            message = ACLMessage(ACLMessage.CFP)
            message.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
            for node in self.agent.transformer['nodes']:
                message.add_receiver(AID(name='prosumer{}'.format(node)))
            message.set_content('REQUEST FOR SCHEDULE')
            message.set_message_length(100)
            self.agent.call_later(random.uniform(0.0, 0.5), self.launch_contract_net_protocol, message, 'SCHEDULE')
            self.agent.mosaik_freezed = True
            f = Figlet()
            print(f.renderText('BESS to Pros. Schedule CFP'))
            return

        if ((time - SEND_COMMANDS_TIME_DELAY) % TIME_INTERVAL) == 0 and time != SEND_COMMANDS_TIME_DELAY:
            commands = dict()
            if self.agent.bess_storage_detailed_load is not None:
                from_ = self.eid
                data = {from_: {}}
                for node, values in self.agent.bess_storage_detailed_load.items():
                    t = int(time/(15 * 60)) + 1
                    if values[t] > 0.0:
                        commands = {'commands': {'storage_mode': 'charge',
                                                 'power_level': values[t]}}
                    else:
                        commands = {'commands': {'storage_mode': 'discharge',
                                                 'power_level': values[t]}}
                    to_ = '{}:storage{}'.format(self.bess_ref, node)
                    data[from_][to_] = commands
                yield self.set_data_async(data)

            # from_ = self.eid
            # to_ = self.bess_ref
            # data = {from_: {to_: commands}}
            # yield self.set_data_async(data)

        if ((time - OPERATION_TIME_DELAY) % TIME_INTERVAL) == 0 and time != OPERATION_TIME_DELAY:
            message = ACLMessage(ACLMessage.CFP)
            message.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
            for node in self.agent.transformer['nodes']:
                message.add_receiver(AID(name='prosumer{}'.format(node)))
            message.set_content('REQUEST FOR AUCTION')
            message.set_message_length(100)
            self.agent.call_later(0.1, self.launch_contract_net_protocol, message, 'AUCTION')
            f = Figlet()
            print(f.renderText('BESS to Pros. Auction CFP'))
            return

        return time + self.step_size

    def calc_min_sell_and_max_buy_prices(self):
        if len(self.price_history_vector) >= 20:
            price_vector_sorted = list(self.price_history_vector)
            price_vector_sorted.sort()
            price_vector_sorted = price_vector_sorted[5:-5]

            self.max_buy_price = min(price_vector_sorted)
            self.min_sell_price = max(price_vector_sorted)

            if len(self.price_history_vector) >= 50:
                self.price_history_vector.pop(0)
        else:
            self.max_buy_price = sum(self.price_history_vector) / len(self.price_history_vector)
            self.min_sell_price = 1.5 * self.max_buy_price

    def launch_contract_net_protocol(self, message, role):
        display_message(self.agent.aid.name, 'Launching FIPA-ContractNet Protocol...')
        self.agent.auction_finished = False
        if self.agent.comp_cnp_1 is None:
            self.agent.comp_cnp_1 = BESSInitiatorContractNetProtocol(self.agent, message, role)
            self.agent.behaviours.append(self.agent.comp_cnp_1)
            self.agent.comp_cnp_1.on_start()
        else:
            self.agent.comp_cnp_1.message = message
            self.agent.comp_cnp_1.role = role
            self.agent.comp_cnp_1.on_start()

    def get_data(self, outputs):
        data = {}
        for eid, attrs in outputs.items():
            data[eid] = {}
            for attr in attrs:
                if attr not in MOSAIK_MODELS['models']['BESSAgent']['attrs']:
                    raise ValueError('Unknown output attribute: {}'.format(attr))
                data[eid][attr] = getattr(self.agent, 'clear_price')
        return data


class BESSInitiatorRequestProtocol(FipaRequestProtocol):
    def __init__(self, agent, message, role=None):
        super(BESSInitiatorRequestProtocol, self).__init__(agent=agent,
                                                           message=message,
                                                           is_initiator=True)
        self.role = role

    def handle_inform(self, message):
        super(BESSInitiatorRequestProtocol, self).handle_inform(message)

        if self.role == 'DSO_SCHEDULE':
            # a ser implementado
            pass

        elif self.role == 'MARKET_SCHEDULE':

            config = pickle.loads(literal_eval(message.content))
            self.agent.prosumer_storage_detailed_load = {str(i): j * 1e3 for i, j in config['prosumer_storage_detailed_load'].items()}
            self.agent.new_detailed_load_bess = {str(i): j * 1e3 for i, j in config['new_detailed_load_bess'].items()}

            config = dict()
            config['prosumer_storage_detailed_load'] = self.agent.new_detailed_load_bess
            config['prosumer_bilateral_contract_purchase'] = self.agent.prosumer_bilateral_contract_purchase
            content = pickle.dumps(config)

            self.agent.comp_cnp_2.answer.set_content(content)
            self.agent.comp_cnp_2.answer.set_message_length(np.random.randint(1000, 1500))
            self.agent.send(self.agent.comp_cnp_2.answer)

        elif self.role == 'MARKET_AUCTION_2':
            config = pickle.loads(literal_eval(message.content))
            self.agent.real_time_prosumer_storage_value = {str(i): j for i, j in config['prosumer_storage_detailed_load'].items()}
            self.agent.real_time_new_detailed_load_bess = config['new_detailed_load_bess']

            config = dict()
            config['prosumer_storage_detailed_load'] = self.agent.real_time_new_detailed_load_bess
            content = pickle.dumps(config)

            self.agent.comp_cnp_2.answer.set_content(content)
            self.agent.comp_cnp_2.answer.set_message_length(np.random.randint(1000, 1500))
            self.agent.send(self.agent.comp_cnp_2.answer)


class BESSInitiatorContractNetProtocol(FipaContractNetProtocol):
    """AuctionClear

    Initial FIPA-ContractNet Behaviour that sends CFP messages
    to ProsumerAgents connected to BESSAgents asking for proposals.
    This behaviour also aggregate the proposals to find the
    clear value for the network state."""

    def __init__(self, agent, message, role):
        super(BESSInitiatorContractNetProtocol, self).__init__(
            agent=agent,
            message=message,
            is_initiator=True)
        self.cfp = message
        self.role = role

    def handle_all_proposes(self, proposes):
        """
        """

        super(BESSInitiatorContractNetProtocol, self).handle_all_proposes(proposes)
        display_message(self.agent.aid.name, 'HANDLING PROPOSES FROM PROSUMERS AGENTS...')
        if self.role == 'AUCTION':
            self._handle_auction_proposes(proposes)
        elif self.role == 'SCHEDULE':
            self._handle_schedule_proposes(proposes)

    def _handle_auction_proposes(self, proposes):
        display_message(self.agent.aid.name, 'Analyzing proposals...')

        self.agent.real_time_demand_bid = dict()
        accepted_proposes_aids = list()
        not_accepted_proposes_aids = list()

        for message in proposes:
            display_message(self.agent.aid.name, 'PROPOSE message from {}'.format(message.sender.name))
            accepted_proposes_aids.append(message.sender.name)
            prosumer_agent_id = message.sender.localname.split('prosumer')[1]
            content = pickle.loads(literal_eval(message.content))

            self.agent.real_time_demand_bid[prosumer_agent_id] = content['real_time_demand_bid']
            self.agent.real_time_prosumer_load_value[prosumer_agent_id] = np.array([content['real_time_load_value']])
            self.agent.init_real_time_prosumer_storage_value[prosumer_agent_id] = np.array([content['real_time_storage_value']])

        self.agent.auction_finished = True

        self.agent.mosaik_sim.step_done()
        display_message(self.agent.aid.name, '>>> STEP DONE')

    def _handle_schedule_proposes(self, proposes):
        display_message(self.agent.aid.name, 'SCHEDULING ANALISYS...')

        # armazena os valores de demanda programados e enviados pelos
        # prosumers agents em um dicionário detalhado (detailed_load)
        # e agredados em uma variável (agg_load)
        detailed_load = dict()
        prosumer_bilateral_contract_purchase = dict()
        prosumer_storage_detailed_load = dict()
        prosumer_storage_config = dict()
        bess_storage_detailed_load = dict()

        agg_load = np.zeros(96)

        for propose in proposes:
            content = pickle.loads(literal_eval(propose.content))
            prosumer_id = propose.sender.localname.split('prosumer')[1]
            detailed_load[prosumer_id] = content['detailed_load']
            prosumer_bilateral_contract_purchase[prosumer_id] = content['bilateral_contract_purchase']
            prosumer_storage_detailed_load[prosumer_id] = content['storage_detailed_load']
            prosumer_storage_config[prosumer_id] = content['prosumer_storage_config']

            agg_load += content['detailed_load'] + content['storage_detailed_load']

        # registra a programaçao dos dispositivos de armazenamento controlados
        # pelo BESS, nesse caso a programação é inteiramente zerada
        for bess_node in self.agent.transformer['bess_nodes']:
            bess_storage_detailed_load[str(bess_node)] = np.zeros(24 * 4)

        self.agent.aggregate_demand = agg_load
        self.agent.prosumer_detailed_load = detailed_load
        self.agent.prosumer_bilateral_contract_purchase = {int(i): j for i, j in prosumer_bilateral_contract_purchase.items()}
        self.agent.init_prosumer_storage_detailed_load = prosumer_storage_detailed_load
        self.agent.prosumer_storage_config = {int(i): j for i, j in prosumer_storage_config.items()}
        self.agent.prosumer_storage_nodes = [int(i) for i, j in prosumer_storage_config.items()
                                             if j['has_storage']]
        self.agent.bess_storage_detailed_load = bess_storage_detailed_load

        display_message(self.agent.aid.localname, '>>> STORAGE SCHEDULE RECEIVED')

        if self.agent.mosaik_freezed:
            self.agent.mosaik_sim.step_done()
            display_message(self.agent.aid.name, '>>> STEP DONE')
            self.agent.mosaik_freezed = False

    def handle_inform(self, message):
        """
        """
        super(BESSInitiatorContractNetProtocol, self).handle_inform(message)

        display_message(self.agent.aid.name, 'INFORM message received')

    def handle_refuse(self, message):
        """
        """
        super(BESSInitiatorContractNetProtocol, self).handle_refuse(message)

        display_message(self.agent.aid.name, 'REFUSE message received')

    def handle_propose(self, message):
        """
        """
        super(BESSInitiatorContractNetProtocol, self).handle_propose(message)

        display_message(self.agent.aid.name, 'PROPOSE message received')


class BESSParticipantContractNetProtocol(FipaContractNetProtocol):
    """AuctionPropose

    FIPA-ContractNet Participant Behaviour that runs when an agent
    receives a CFP message. This behaviour implements the auction
    role of the ProsumerAgent sending a propose for BESS agent
    with the demand curve in message content."""

    def __init__(self, agent):
        super(BESSParticipantContractNetProtocol, self).__init__(agent=agent,
                                                                 message=None,
                                                                 is_initiator=False)
        self.role = None


    def handle_cfp(self, message):
        """
        """
        self.agent.call_later(random.uniform(0.1, 0.2), self._handle_cfp, message)

    def _handle_cfp(self, message):
        """
        """
        super(BESSParticipantContractNetProtocol, self).handle_cfp(message)
        self.message = message

        display_message(self.agent.aid.name, 'CFP message received')

        if message.content == 'DSO_SCHEDULE':
            self._handle_dso_schedule_request(message)
            self.role = 'DSO_SCHEDULE'
        elif message.content == 'DSO_AUCTION':
            self._handle_dso_auction_request(message)
            self.role = 'DSO_AUCTION'
        elif message.content == 'MARKET_SCHEDULE':
            self._handle_market_schedule_request(message)
            self.role = 'MARKET_SCHEDULE'
        elif message.content == 'MARKET_AUCTION':
            self._handle_market_auction_request(message)
            self.role = 'MARKET_AUCTION'
        elif message.content == 'MARKET_AUCTION_2':
            self._handle_market_auction_2_request(message)
            self.role = 'MARKET_AUCTION_2'

    def _handle_dso_schedule_request(self, message):
        # =================================================
        # calcula a curva de preço vs. demanda
        # =================================================
        self.agent.lagrangian_multiplier = {n: np.zeros(self.agent.time_qtd)
                                            for n in self.agent.transformer['nodes']}

        config = dict()
        config['aggregate_demand'] = self.agent.aggregate_demand
        config['detailed_load'] = self.agent.prosumer_detailed_load
        
        config['prosumer_storage_detailed_load'] = self.agent.init_prosumer_storage_detailed_load
        config['prosumer_storage_config'] = self.agent.prosumer_storage_config
        config['prosumer_storage_nodes'] = self.agent.prosumer_storage_nodes

        config['bess_storage_detailed_load'] = self.agent.bess_storage_detailed_load
        config['bess_storage_config'] = self.agent.bess_storage_config
        config['bess_storage_nodes'] = self.agent.bess_storage_nodes

        content = pickle.dumps(config)
        answer = self.message.create_reply()
        answer.set_performative(ACLMessage.PROPOSE)
        answer.set_content(content)
        answer.set_message_length(np.random.randint(1000, 1500))
        self.agent.send(answer)

    def _handle_dso_auction_request(self, message):

        self.agent.lagrangian_multiplier = {n: np.zeros(1)
                                            for n in self.agent.transformer['nodes']}

        config = dict()

        config['real_time_load_value'] = self.agent.real_time_prosumer_load_value
        config['real_time_storage_value'] = self.agent.init_real_time_prosumer_storage_value
        content = pickle.dumps(config)

        answer = self.message.create_reply()
        answer.set_performative(ACLMessage.PROPOSE)
        answer.set_content(content)
        answer.set_message_length(np.random.randint(1000, 1500))
        self.agent.send(answer)

    def _handle_market_schedule_request(self, message):

        config = dict()
        config['nodes'] = self.agent.prosumer_storage_nodes  # ok
        config['storage_detailed_load'] = self.agent.init_prosumer_storage_detailed_load  # ok
        config['lagrangian_multiplier'] = self.agent.lagrangian_multiplier  # ok
        config['prosumer_storage_config'] = self.agent.prosumer_storage_config  # ok

        message = ACLMessage(ACLMessage.REQUEST)
        message.set_protocol(ACLMessage.FIPA_REQUEST_PROTOCOL)
        message.add_receiver(AID(name='solver'))
        content = pickle.dumps(config)
        message.set_content(content)
        message.set_message_length(np.random.randint(1000, 1500))

        if self.agent.comp_request_1 is None:
            self.agent.comp_request_1 = BESSInitiatorRequestProtocol(self.agent,
                                                                     message,
                                                                     role='MARKET_SCHEDULE')
            self.agent.behaviours.append(self.agent.comp_request_1)
            self.agent.comp_request_1.on_start()
        else:
            self.agent.comp_request_1.message = message
            self.agent.comp_request_1.role = 'MARKET_SCHEDULE'
            self.agent.comp_request_1.on_start()

        self.answer = self.message.create_reply()
        self.answer.set_performative(ACLMessage.PROPOSE)

    def _handle_market_auction_request(self, message):
        config = dict()

        config['real_time_demand_bid'] = self.agent.real_time_demand_bid

        content = pickle.dumps(config)

        answer = self.message.create_reply()
        answer.set_performative(ACLMessage.PROPOSE)
        answer.set_content(content)
        answer.set_message_length(np.random.randint(1000, 1500))
        self.agent.send(answer)

    def _handle_market_auction_2_request(self, message):
        config = dict()
        config['nodes'] = self.agent.prosumer_storage_nodes  # ok
        config['storage_detailed_load'] = self.agent.init_real_time_prosumer_storage_value  # ok
        config['lagrangian_multiplier'] = self.agent.lagrangian_multiplier  # ok
        config['prosumer_storage_config'] = self.agent.prosumer_storage_config  # ok

        message = ACLMessage(ACLMessage.REQUEST)
        message.set_protocol(ACLMessage.FIPA_REQUEST_PROTOCOL)
        message.add_receiver(AID(name='solver'))
        content = pickle.dumps(config)
        message.set_content(content)
        message.set_message_length(np.random.randint(1000, 1500))

        if self.agent.comp_request_1 is None:
            self.agent.comp_request_1 = BESSInitiatorRequestProtocol(self.agent,
                                                                     message,
                                                                     role='MARKET_AUCTION_2')
            self.agent.behaviours.append(self.agent.comp_request_1)
            self.agent.comp_request_1.on_start()
        else:
            self.agent.comp_request_1.message = message
            self.agent.comp_request_1.role = 'MARKET_AUCTION_2'
            self.agent.comp_request_1.on_start()

        self.answer = self.message.create_reply()
        self.answer.set_performative(ACLMessage.PROPOSE)

    def handle_reject_propose(self, message):
        """
        """
        super(BESSParticipantContractNetProtocol, self).handle_reject_propose(message)
        display_message(self.agent.aid.name, 'REJECT_PROPOSAL message received')

        if self.role == 'DSO_SCHEDULE':
            bess_storage_detailed_load = pickle.loads(literal_eval(message.content))
            for node, data in bess_storage_detailed_load.items():
                self.agent.bess_storage_detailed_load[str(node)] = data

        elif self.role == 'DSO_AUCTION':
            # ESTA É UMA CONFIGURAÇÃO DE INDICE DE TEMPO E ESTA ASSOCIADA
            # AO TEMPO DE EXECUÇÃO DO COMPORTAMENTO DE AUCTION DO DSO
            # QUE NO CASO ACONTECE SEMPRE 2 MINUTOS APÓS CADA CICLO DE
            # DE 15 MIN DE CO-SIMULAÇÃO
            time = int((self.agent.mosaik_sim.time - OPERATION_TIME_DELAY) / TIME_INTERVAL) + 2

            bess_storage_detailed_load = pickle.loads(literal_eval(message.content))
            for node, data in bess_storage_detailed_load.items():
                self.agent.bess_storage_detailed_load[str(node)][time] = data[0]

        elif self.role == 'MARKET_SCHEDULE':
            config = pickle.loads(literal_eval(message.content))
            self.agent.lagrangian_multiplier = config['lagrangian_multiplier']

        elif self.role == 'MARKET_AUCTION_2':
            config = pickle.loads(literal_eval(message.content))
            self.agent.lagrangian_multiplier = config['lagrangian_multiplier']

    def handle_accept_propose(self, message):
        """
        """
        super(BESSParticipantContractNetProtocol, self).handle_accept_propose(message)

        if self.role == 'MARKET_SCHEDULE':
            config = pickle.loads(literal_eval(message.content))
            self.agent.lagrangian_multiplier = config['lagrangian_multiplier']

            config = dict()
            config['message_type'] = 'STORAGE_SCHEDULE'
            config['prosumer_storage_detailed_load'] = self.agent.prosumer_storage_detailed_load
            content = pickle.dumps(config)

            message_ = ACLMessage(ACLMessage.INFORM)
            message_.set_protocol(ACLMessage.FIPA_SUBSCRIBE_PROTOCOL)
            message_.set_content(content)
            message_.set_message_length(np.random.randint(1000, 1500))

            # configura o comportamento do protocolo FIPA Subscriber
            # para contar as confirmações de mensagens recebidas
            # e enviar a confirmação para o Market Agent
            self.agent.comp_pubsub_1.accept_confirmation_count = 0
            self.agent.comp_pubsub_1.schedule_accept_message = message
            self.agent.comp_pubsub_1.notify(message_)

        elif self.role == 'MARKET_AUCTION_2':
            config = pickle.loads(literal_eval(message.content))
            self.agent.lagrangian_multiplier = config['lagrangian_multiplier']

            config = dict()
            config['message_type'] = 'STORAGE_SCHEDULE_2'
            config['prosumer_storage_detailed_load'] = self.agent.real_time_prosumer_storage_value
            content = pickle.dumps(config)

            message_ = ACLMessage(ACLMessage.INFORM)
            message_.set_protocol(ACLMessage.FIPA_SUBSCRIBE_PROTOCOL)
            message_.set_content(content)
            message_.set_message_length(np.random.randint(1000, 1500))

            # configura o comportamento do protocolo FIPA Subscriber
            # para contar as confirmações de mensagens recebidas
            # e enviar a confirmação para o Market Agent
            self.agent.comp_pubsub_1.accept_confirmation_count = 0
            self.agent.comp_pubsub_1.schedule_accept_message = message
            self.agent.comp_pubsub_1.notify(message_)

class BESSPublisherProtocol(FipaSubscribeProtocol):

    def __init__(self, agent):
        super(BESSPublisherProtocol, self).__init__(agent,
                                                    message=None,
                                                    is_initiator=False)
        self.schedule_accept_message = None
        self.accept_confirmation_qtd = 0
        self.accept_confirmation_count = 0


    def handle_subscribe(self, message):
        self.register(message.sender)
        self.accept_confirmation_qtd = len(self.subscribers)
        display_message(self.agent.aid.name, message.content)
        answer = message.create_reply()
        answer.set_performative(ACLMessage.AGREE)
        answer.set_content('Subscribe message accepted')
        answer.set_message_length(100)
        self.agent.send(answer)

    def handle_cancel(self, message):
        self.deregister(self, message.sender)
        display_message(self.agent.aid.name, message.content)

    def notify(self, message):
        super(BESSPublisherProtocol, self).notify(message)

    def handle_inform(self, message):

        config = pickle.loads(literal_eval(message.content))
        if config['message_type'] == 'SUBSCRIBER CONFIRM':
            self.accept_confirmation_count += 1
            display_message(self.agent.aid.name,
                            'S: {}/R: {}'.format(self.accept_confirmation_qtd,
                                                 self.accept_confirmation_count
                                                 )
                            )
            if self.accept_confirmation_count == self.accept_confirmation_qtd:
                # Envia mensagem de confirmação para o Agent Market
                reply = self.schedule_accept_message.create_reply()
                reply.set_performative(ACLMessage.INFORM)
                config = dict()
                config['message_type'] = 'BESS CONFIRM'
                content = pickle.dumps(config)
                reply.set_content(content)
                reply.set_message_length(100)
                self.agent.send(reply)


class BESSSubscriberProtocol(FipaSubscribeProtocol):
    def __init__(self, agent, message):
        super(BESSSubscriberProtocol, self).__init__(agent,
                                                     message,
                                                     is_initiator=True)
        pass

    def handle_agree(self, message):
        display_message(self.agent.aid.name, message.content)

    def handle_inform(self, message):
        config = pickle.loads(literal_eval(message.content))

        if config['message_type'] == 'STORAGE_SCHEDULE':
            bess_storage_detailed_load = config['bess_storage_detailed_load']
            for i, j in bess_storage_detailed_load.items():
                if int(i) in self.agent.bess_storage_nodes:
                    display_message(self.agent.aid.name, 'BESS {} STORAGE UPDATED'.format(i))
                    self.agent.bess_storage_detailed_load[str(i)] = j

        elif config['message_type'] == 'STORAGE_SCHEDULE_2':
            time = int((self.agent.mosaik_sim.time -
                        OPERATION_TIME_DELAY) /
                       TIME_INTERVAL) + 2
            bess_storage_detailed_load = config['bess_storage_detailed_load']
            for i, j in bess_storage_detailed_load.items():
                if int(i) in self.agent.bess_storage_nodes:
                    display_message(self.agent.aid.name, 'BESS {} STORAGE UPDATED'.format(i))
                    self.agent.bess_storage_detailed_load[str(i)][time] = j[0]
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


class BESSAgent(Agent):

    def __init__(self,
                 aid,
                 # prosumer_storage_config,
                 bess_storage_config,
                 transformer,
                 mode):

        super(BESSAgent, self).__init__(aid=aid, debug=False, mode=mode)
        self.mosaik_sim = MosaikSim(self)
        self.transformer = transformer

        self.time_qtd = 4 * 24
        self.aggregate_demand = None

        # variaveis para a fase de planejamento
        self.prosumer_detailed_load = None
        self.init_prosumer_storage_detailed_load = None
        self.prosumer_bilateral_contract_purchase = None

        self.prosumer_storage_detailed_load = None
        self.prosumer_storage_config = None
        self.prosumer_storage_nodes = None

        self.bess_storage_detailed_load = None
        self.bess_storage_config = {int(i): j for i, j in bess_storage_config.items()}
        self.bess_storage_nodes = [int(i) for i in self.bess_storage_config.keys()]
        self.new_detailed_load_bess = None

        self.lagrangian_multiplier = None

        # variaveis para a fase de operação
        self.clear_price = 0.0
        self.real_time_demand_bid = dict()
        self.real_time_prosumer_load_value = dict()
        self.init_real_time_prosumer_storage_value = dict()
        self.real_time_prosumer_storage_value = None
        self.real_time_bess_storage_value = None
        self.real_time_new_detailed_load_bess = None

        self.mosaik_freezed = False

        # Behaviours
        self.comp_pubsub_1 = BESSPublisherProtocol(self)
        self.behaviours.append(self.comp_pubsub_1)

        self.comp_pubsub_2 = None

        self.comp_cnp_1 = None

        self.comp_cnp_2 = BESSParticipantContractNetProtocol(self)
        self.behaviours.append(self.comp_cnp_2)

        self.comp_request_1 = None

        msg = ACLMessage(ACLMessage.SUBSCRIBE)
        msg.set_protocol(ACLMessage.FIPA_SUBSCRIBE_PROTOCOL)
        msg.set_content('Subscription request')
        msg.add_receiver(AID(name='dso'))
        msg.set_message_length(100)
        self.call_later(10.0, self.launch_subscriber_protocol, msg)

    def launch_subscriber_protocol(self, message):
        self.comp_pubsub_2 = BESSSubscriberProtocol(self, message)
        self.behaviours.append(self.comp_pubsub_2)
        self.comp_pubsub_2.on_start()
