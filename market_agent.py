from pade.misc.utility import display_message, defer_to_thread
from pade.core.agent import Agent
from pade.acl.aid import AID
from pade.acl.messages import ACLMessage
from pade.behaviours.protocols import FipaRequestProtocol
from pade.behaviours.protocols import FipaContractNetProtocol
from pade.drivers.mosaik_driver import MosaikCon
from load_data import get_spot_prices_data

import numpy as np
import pandas as pd
import datetime as dt
import h5py
import json
import pickle
from ast import literal_eval
from pyfiglet import Figlet

MOSAIK_MODELS = {
    'api_version': '2.2',
    'models': {
        'MarketAgent': {
            'public': True,
            'params': [],
            'attrs': [],

        },
    },
}

SCHEDULE_TIME = 10 * 60
TIME_INTERVAL = 15 * 60
OPERATION_TIME_DELAY = 10 * 60


class MosaikSim(MosaikCon):

    def __init__(self, agent):
        super(MosaikSim, self).__init__(MOSAIK_MODELS, agent)
        self.entities = list()

    def init(self, sid, eid_prefix, start, step_size):
        self.eid_prefix = eid_prefix
        self.eid = '{}{}'.format(self.eid_prefix, '0')
        self.start = start
        self.step_size = step_size
        return MOSAIK_MODELS

    def create(self, num, model):
        entities_info = list()
        for i in range(num):
            entities_info.append(
                {'eid': '{}.{}'.format(self.sim_id, i), 'type': model, 'rel': []}
            )
        return entities_info

    def step(self, time, inputs):

        if time == SCHEDULE_TIME:
            message = ACLMessage(ACLMessage.CFP)
            message.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
            for bess in self.agent.bess_list:
                message.add_receiver(AID(name='bess{}'.format(bess)))
            message.add_receiver(AID(name='dso'))
            message.set_content('MARKET_SCHEDULE')
            message.set_message_length(100)
            self.agent.call_later(0.1, self.launch_contract_net_protocol, message, 'MARKET_SCHEDULE')
            f = Figlet()
            print(f.renderText('Market Schedule CFP'))
            return

        if ((time - OPERATION_TIME_DELAY) % TIME_INTERVAL) == 0 and time != OPERATION_TIME_DELAY:
            message = ACLMessage(ACLMessage.CFP)
            message.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
            for bess in self.agent.bess_list:
                message.add_receiver(AID(name='bess{}'.format(bess)))
            message.add_receiver(AID(name='dso'))
            message.set_content('MARKET_AUCTION')
            message.set_message_length(100)
            self.agent.call_later(0.1, self.launch_contract_net_protocol, message, 'MARKET_AUCTION')
            f = Figlet()
            print(f.renderText('Market Auction CFP'))
            return
        return time + self.step_size

    def get_data(self, outputs):
        data = {}
        for eid, attrs in outputs.items():
            data[eid] = {}
            for attr in attrs:
                if attr not in MOSAIK_MODELS['models']['MarketAgent']['attrs']:
                    raise ValueError('Unknown output attribute: {}'.format(attr))
                # TODO: inserir o nome do atributo a ser enviado pelo market agent
                data[eid][attr] = getattr(self.agent, '')
        return data

    def launch_contract_net_protocol(self, message, role):
        display_message(self.agent.aid.name, 'Launching FIPA-ContractNet Protocol...')
        self.agent.auction_finished = False
        if self.agent.comp_cnp_1 is None:
            self.agent.comp_cnp_1 = MarketInitiatorContractNetProtocol(self.agent, message, role)
            self.agent.behaviours.append(self.agent.comp_cnp_1)
            self.agent.comp_cnp_1.on_start()
        else:
            self.agent.comp_cnp_1.message = message
            self.agent.comp_cnp_1.role = role
            self.agent.comp_cnp_1.on_start()

    def step_done_(self, time):
        message = self._create_message(1, self.msg_id_step, self.time + self.step_size + time)
        self.agent.mosaik_connection.transport.write(message)
        self.agent.mosaik_connection.message = None
        self.agent.mosaik_connection.mosaik_msg_id = None
        self.agent.mosaik_connection.await_gen = None


class MarketInitiatorContractNetProtocol(FipaContractNetProtocol):
    def __init__(self, agent, message, role):
        super(MarketInitiatorContractNetProtocol, self).__init__(agent=agent,
            message=message, is_initiator=True)
        self.cpf = message
        self.role = role
        self.restriction = dict()
        self.accept_confirmation_qtd = 0
        self.accept_confirmation_count = 0

    def handle_all_proposes(self, proposes):
        super(MarketInitiatorContractNetProtocol, self).handle_all_proposes(proposes)

        if self.role == 'MARKET_AUCTION':
            self._handle_auction_proposes(proposes)
        elif self.role == 'MARKET_SCHEDULE':
            self._handle_schedule_proposes(proposes)
        elif self.role == 'MARKET_AUCTION_2':
            self._handle_auction_2_prososes(proposes)

    def handle_inform(self, message):

        config = pickle.loads(literal_eval(message.content))
        if config['message_type'] == 'DSO CONFIRM' or config['message_type'] == 'BESS CONFIRM':
            self.accept_confirmation_count += 1
            display_message(self.agent.aid.name, '{} received.'.format(config['message_type']))
            if self.accept_confirmation_count == self.accept_confirmation_qtd:
                self.agent.mosaik_sim.step_done_(time=60)
                display_message(self.agent.aid.name, '>>> STEP DONE')

    def _handle_schedule_proposes(self, proposes):
        display_message(self.agent.aid.name, 'Analysing proposals')

        prosumer_storage_detailed_load_bess = dict()
        prosumer_storage_detailed_load_dso = dict()
        bess_storage_detailed_load_dso = dict()
        base_detailed_load_dso = dict()

        for propose in proposes:
            content = pickle.loads(literal_eval(propose.content))
            if 'bess' in propose.sender.name:
                prosumer_storage_detailed_load_bess.update(content['prosumer_storage_detailed_load'])
            elif 'dso' in propose.sender.name:
                prosumer_storage_detailed_load_dso.update(content['prosumer_storage_detailed_load'])
                bess_storage_detailed_load_dso.update(content['bess_storage_detailed_load'])
                base_detailed_load_dso.update(content['base_detailed_load'])


        if not self.agent.prosumer_bilateral_contract_purchase:
            self.agent.prosumer_bilateral_contract_purchase = dict()
            for propose in proposes:
                content = pickle.loads(literal_eval(propose.content))
                if 'bess' in propose.sender.name:
                    self.agent.prosumer_bilateral_contract_purchase.update(content['prosumer_bilateral_contract_purchase'])

            self.agent.save_transactions_data(data_dict=self.agent.prosumer_bilateral_contract_purchase,
                                              market='bilateral')

        # ##############################################
        # verificação das chaves dos dicionários:
        # - prosumer_storage_detailed_load_bess
        # - prosumer_storage_detailed_load_dso
        # ##############################################
        time_qtd = 4 * 24
        prosumer_nodes = [i['name'] for i in self.agent.grid_data['nodes']]
        prosumer_nodes.pop(0)
        for n in prosumer_nodes:
            prosumer_storage_detailed_load_bess.setdefault(str(n), np.zeros(time_qtd))
            prosumer_storage_detailed_load_dso.setdefault(str(n), np.zeros(time_qtd))

        # ##############################################
        # ATUALIZAZACAO DOS MULTIPLICADORES DE LAGRANGE
        # ##############################################

        # m = 1.0
        # alpha = (1 + m) / (aux + m)
        alpha = 0.0005

        lag_mult_old = pd.DataFrame(self.agent.lagrangian_multiplier)
        for n in prosumer_storage_detailed_load_bess.keys():
            aux = prosumer_storage_detailed_load_bess[n] - prosumer_storage_detailed_load_dso[n]
            self.agent.lagrangian_multiplier[int(n)] += alpha * aux

        lag_mult_new = pd.DataFrame(self.agent.lagrangian_multiplier)

        if lag_mult_old.max().max() == 0.0:
            end = False
        else:
            diff = lag_mult_old - lag_mult_new
            print('Lagrangian diff = {}'.format(abs(diff).max().max()))
            print((lag_mult_new).max().sort_values(ascending=False).head(10))
            if (abs(diff) < 1e-4).all(axis=None):
                end = True
            else:
                end = False

        with h5py.File('schedules_data.hdf5', 'a') as f:
            num = str(self.agent.iteraction_number)
            f.create_group(num)

            aux = f[num].create_group('prosumer_storage_detailed_load_bess')
            for i, j in prosumer_storage_detailed_load_bess.items():
                aux.create_dataset(name=i, data=j)

            aux = f[num].create_group('prosumer_storage_detailed_load_dso')
            for i, j in prosumer_storage_detailed_load_dso.items():
                aux.create_dataset(name=i, data=j)

            aux = f[num].create_group('bess_storage_detailed_load_dso')
            for i, j in bess_storage_detailed_load_dso.items():
                aux.create_dataset(name=i, data=j)

            aux = f[num].create_group('base_detailed_load_dso')
            for i, j in base_detailed_load_dso.items():
                aux.create_dataset(name=i, data=j)

            aux = f[num].create_group('lagrangian_multiplier')
            for i, j in self.agent.lagrangian_multiplier.items():
                aux.create_dataset(name=str(i), data=j)

            self.agent.iteraction_number += 1

        if end:
            lag_mult_new.to_json('lagrangian.json')

            answer = ACLMessage(ACLMessage.ACCEPT_PROPOSAL)
            answer.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)

            self.accept_confirmation_qtd = 0
            self.accept_confirmation_count = 0
            for bess in self.agent.bess_list:
                answer.add_receiver(AID(name='bess{}'.format(bess)))
                self.accept_confirmation_qtd += 1
            answer.add_receiver(AID(name='dso'))
            self.accept_confirmation_qtd += 1

            config = dict()
            config['lagrangian_multiplier'] = self.agent.lagrangian_multiplier
            answer.set_content(pickle.dumps(config))
            answer.set_message_length(np.random.randint(1000, 1500))
            self.agent.send(answer)
        else:
            answer = ACLMessage(ACLMessage.REJECT_PROPOSAL)
            answer.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)

            for bess in self.agent.bess_list:
                answer.add_receiver(AID(name='bess{}'.format(bess)))
            answer.add_receiver(AID(name='dso'))

            config = dict()
            config['lagrangian_multiplier'] = self.agent.lagrangian_multiplier
            answer.set_content(pickle.dumps(config))
            answer.set_message_length(np.random.randint(1000, 1500))
            self.agent.send(answer)

            message = ACLMessage(ACLMessage.CFP)
            message.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
            for bess in self.agent.bess_list:
                message.add_receiver(AID(name='bess{}'.format(bess)))
            message.add_receiver(AID(name='dso'))
            message.set_content('MARKET_SCHEDULE')
            message.set_message_length(100)

            self.agent.call_later(0.1,
                                  self.launch_contract_net_protocol,
                                  message,
                                  'MARKET_SCHEDULE')

    def _handle_auction_proposes(self, proposes):
        display_message(self.agent.aid.name, 'Analysing auctions proposals...')

        accepted_proposes_aids = list()
        not_accepted_proposes_aids = list()
        total_bids = 0.0
        prosumers_bids = dict()
        grid_restriction = False
        bess_storage_alt = False

        for message in proposes:
            display_message(self.agent.aid.name, 'PROPOSE message from {}'.format(message.sender.name))
            accepted_proposes_aids.append(message.sender.name)
            config = pickle.loads(literal_eval(message.content))
            if 'dso' not in message.sender.name:
                for agent_id, bid_value in config['real_time_demand_bid'].items():
                    total_bids += bid_value
                    prosumers_bids[agent_id] = [bid_value]
            else:
                grid_restriction = config['grid_restriction']
                bess_storage_alt = config['bess_storage_alt']

        # verifica se alguma restrição operacional foi encontrada
        # pelo DSO no momento da operação em decorrêcia de alguma
        # alteração de programação definida pelo prosumidor
        if grid_restriction:
            display_message(self.agent.aid.name, 'GRID RESTRICTION IN OPERATION TIME')

            # verifica se foi possível a eliminação da violação de
            # restrição operacional por meio da alteração da programação
            # dos dispositivos de armazenamento coordenados pelo DSO
            if bess_storage_alt:
                display_message(self.agent.aid.name, 'ALTERACAO POSSIVEL SOMENTE NOS BESS CONTROLÁVEIS')
            # caso não seja possível eliminação das violaçãoes de
            # restrições operacionais somente alterando a programação
            # dos dispositivos de armazenamento coordenados pelo DSO
            # então será necessária a abertura de um leilão de operação
            else:
                message = ACLMessage(ACLMessage.CFP)
                message.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
                for bess in self.agent.bess_list:
                    message.add_receiver(AID(name='bess{}'.format(bess)))
                message.add_receiver(AID(name='dso'))
                message.set_content('MARKET_AUCTION_2')
                message.set_message_length(100)

                self.agent.call_later(0.1,
                                      self.launch_contract_net_protocol,
                                      message,
                                      'MARKET_AUCTION_2')
                return None
        else:
            display_message(self.agent.aid.name, 'NAO FOI IDENTIF. OCORR. DE GRID REST. PELO DSO')

        #######################################################################
        # exibe os solicitado pelos agentes prosumers para o
        # ciclo de negociação t = t0 + 2c do mercado de tempo real
        time_index = int((self.agent.mosaik_sim.time - OPERATION_TIME_DELAY) / TIME_INTERVAL) + 2
        price = self.agent.spot_prices[time_index]

        self.agent.save_transactions_data(data_dict=prosumers_bids, market='spot', value_um=price)

        display_message(self.agent.aid.name,
                        'TOTAL BIDs in REAL TIME MARKET: {:5.3f} \
                         PRICE: {:5.3f}'.format(total_bids, price))

        self.agent.mosaik_sim.step_done_(time=60)
        display_message(self.agent.aid.name, '>>> STEP DONE')

    def _handle_auction_2_prososes(self, proposes):
        display_message(self.agent.aid.name, 'Analysing proposals')

        prosumer_storage_detailed_load_bess = dict()
        prosumer_storage_detailed_load_dso = dict()

        for propose in proposes:
            content = pickle.loads(literal_eval(propose.content))
            if 'bess' in propose.sender.name:
                prosumer_storage_detailed_load_bess.update(content['prosumer_storage_detailed_load'])
            elif 'dso' in propose.sender.name:
                prosumer_storage_detailed_load_dso.update(content['prosumer_storage_detailed_load'])

        # ##############################################
        # verificação das chaves dos dicionários:
        # - prosumer_storage_detailed_load_bess
        # - prosumer_storage_detailed_load_dso
        # ##############################################
        time_qtd = 1
        prosumer_nodes = [i['name'] for i in self.agent.grid_data['nodes']]
        prosumer_nodes.pop(0)
        for n in prosumer_nodes:
            prosumer_storage_detailed_load_bess.setdefault(str(n), np.zeros(time_qtd))
            prosumer_storage_detailed_load_dso.setdefault(str(n), np.zeros(time_qtd))

        # ##############################################
        # ATUALIZAZACAO DOS MULTIPLICADORES DE LAGRANGE
        # ##############################################

        # m = 1.0
        # alpha = (1 + m) / (aux + m)
        alpha = 0.001

        lag_mult_old = pd.DataFrame(self.agent.lagrangian_multiplier)
        for n in prosumer_storage_detailed_load_bess.keys():
            aux = prosumer_storage_detailed_load_bess[n] - prosumer_storage_detailed_load_dso[n]
            self.agent.lagrangian_multiplier[int(n)] += alpha * aux

        lag_mult_new = pd.DataFrame(self.agent.lagrangian_multiplier)

        if lag_mult_old.max().max() == 0.0:
            end = False
        else:
            diff = lag_mult_old - lag_mult_new
            print('Lagrangian diff = {}'.format(abs(diff).max().max()))
            print((lag_mult_new).max().sort_values(ascending=False).head(10))
            if (abs(diff) < 1e-4).all(axis=None):
                end = True
            else:
                end = False

        if end:
            answer = ACLMessage(ACLMessage.ACCEPT_PROPOSAL)
            answer.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)

            for bess in self.agent.bess_list:
                answer.add_receiver(AID(name='bess{}'.format(bess)))
            answer.add_receiver(AID(name='dso'))

            config = dict()
            config['lagrangian_multiplier'] = self.agent.lagrangian_multiplier
            answer.set_content(pickle.dumps(config))
            answer.set_message_length(np.random.randint(1000, 1500))
            self.agent.send(answer)
        else:
            answer = ACLMessage(ACLMessage.REJECT_PROPOSAL)
            answer.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)

            for bess in self.agent.bess_list:
                answer.add_receiver(AID(name='bess{}'.format(bess)))
            answer.add_receiver(AID(name='dso'))

            config = dict()
            config['lagrangian_multiplier'] = self.agent.lagrangian_multiplier
            answer.set_content(pickle.dumps(config))
            answer.set_message_length(np.random.randint(1000, 1500))
            self.agent.send(answer)

            message = ACLMessage(ACLMessage.CFP)
            message.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
            for bess in self.agent.bess_list:
                message.add_receiver(AID(name='bess{}'.format(bess)))
            message.add_receiver(AID(name='dso'))
            message.set_content('MARKET_AUCTION_2')
            message.set_message_length(100)

            self.agent.call_later(0.1,
                                  self.launch_contract_net_protocol,
                                  message,
                                  'MARKET_SCHEDULE_2')

    def launch_contract_net_protocol(self, message, role):
        display_message(self.agent.aid.name, 'Launching FIPA-ContractNet Protocol...')

        self.message = message
        self.role = role
        self.on_start()


class MarketAgent(Agent):
    def __init__(self, aid, bess_list, mode):
        super(MarketAgent, self).__init__(aid=aid, debug=False, mode=mode)
        self.iteraction_number = 1
        self.mosaik_sim = MosaikSim(self)
        self.bess_list = bess_list
        self.spot_prices = get_spot_prices_data(spot_index=15).Price.values[:96]

        self.prosumer_bilateral_contract_purchase = None

        with open('force.json', 'r') as f:
            self.grid_data = json.load(f)

        time_qtd = 4 * 24
        storage_nodes = [i['name'] for i in self.grid_data['nodes']]
        storage_nodes.pop(0)

        self.comp_cnp_1 = None

        self.lagrangian_multiplier = {int(n): np.zeros(time_qtd) for n in storage_nodes}

    def save_transactions_data(self, data_dict=dict(), market=None, value_um=-1.0):

        with h5py.File('transactions_data.hdf5', 'a') as f:

            for i, j in data_dict.items():
                id_ = str(len(f))
                f.create_group(id_)
                if market == 'bilateral':
                    f[id_].attrs['name'] = i # nome do nó asociado
                    f[id_].attrs['type'] = market
                    f[id_].attrs['qtd_kw'] = j
                    f[id_].attrs['value_um'] = value_um
                elif market == 'spot':
                    f[id_].attrs['name'] = i
                    f[id_].attrs['type'] = market
                    f[id_].attrs['qtd_kw'] = j
                    f[id_].attrs['value_um'] = value_um
