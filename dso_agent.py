from pade.misc.utility import display_message, defer_to_thread
from pade.core.agent import Agent
from pade.acl.aid import AID
from pade.acl.messages import ACLMessage
from pade.behaviours.protocols import FipaRequestProtocol
from pade.behaviours.protocols import FipaContractNetProtocol
from pade.behaviours.protocols import FipaSubscribeProtocol
from pade.drivers.mosaik_driver import MosaikCon

from calc_methods import demand_curve
from grid_optimization import solve_dso_reschedule
from grid_optimization import run_powerflow_in_pandapower, create_grid_in_pandapower
from grid_optimization import create_branch_dict, create_power_flow_matrix
from grid_optimization import calc_grid_restrictions
from grid_optimization import solve_dso_operation

from mosaik_mygrid import model

import numpy as np
import random
import datetime as dt
import h5py
import json
import pickle
from ast import literal_eval
from pyfiglet import Figlet

MOSAIK_MODELS = {
    'api_version': '2.2',
    'models': {
        'DSOAgent': {
            'public': True,
            'params': [],
            'attrs': ['dso_param'],
        },
    },
}

with open('force.json', 'r') as f:
    GRID_ELEMENTS, ENTITY_MODEL = model.load_case(f)

SCHEDULE_TIME = 5 * 60
TIME_INTERVAL = 15 * 60
OPERATION_TIME_DELAY = 5 * 60


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
                {'eid': '{}.{}'.format(self.sim_id, i), 'type': model, 'rel': []})
        return entities_info

    def step(self, time, inputs):
        """

        """

        # ENVIO DE COMANDOS PARA O BESS AGENT VIA MOSAIK

        from_ = self.eid
        data = {from_: {}}
        for i in range(2, 5):
            bess_ref = 'BESSAgentSim{}-0.BESSAgent_{}'.format(i, i)
            to_ = bess_ref
            data[from_][to_] = {'status': None}
        # yield self.set_data_async(data)

        # COMPORTAMENTOS DE SCHEDULE

        if time == SCHEDULE_TIME:
            message = ACLMessage(ACLMessage.CFP)
            message.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
            for bess in self.agent.bess_list:
                message.add_receiver(AID(name='bess{}'.format(bess)))
            message.set_content('DSO_SCHEDULE')
            message.set_message_length(100)

            self.agent.call_later(0.1, self.launch_contract_net_protocol, message, 'SCHEDULE')
            f = Figlet()
            print(f.renderText('DSO to BESS. Schedule CFP'))
            return

        # COMPORTAMENTOS DE OPERAÇÃO
        if ((time - OPERATION_TIME_DELAY) % TIME_INTERVAL) == 0 and time != OPERATION_TIME_DELAY:
            message = ACLMessage(ACLMessage.CFP)
            message.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
            for bess in self.agent.bess_list:
                message.add_receiver(AID(name='bess{}'.format(bess)))
            message.set_content('DSO_AUCTION')
            message.set_message_length(100)
            self.agent.call_later(0.1, self.launch_contract_net_protocol, message, 'AUCTION')
            f = Figlet()
            print(f.renderText('DSO to BESS. Auction CFP'))
            return

        return time + self.step_size

    def get_data(self, outputs):
        data = {}
        for eid, attrs in outputs.items():
            data[eid] = {}
            for attr in attrs:
                if attr not in MOSAIK_MODELS['models']['DSOAgent']['attrs']:
                    raise ValueError('Unknown output attribute: {}'.format(attr))
                data[eid][attr] = getattr(self.agent, 'dso_param')
        return data

    def launch_contract_net_protocol(self, message, role):
        display_message(self.agent.aid.name, 'Launching FIPA-ContractNet Protocol...')
        self.agent.auction_finished = False
        if self.agent.comp_cnp_1 is None:
            self.agent.comp_cnp_1 = DSOInitiatorContractNetProtocol(self.agent, message, role)
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


class DSOInitiatorRequestProtocol(FipaRequestProtocol):
    def __init__(self, agent, message, role=None):
        super(DSOInitiatorRequestProtocol, self).__init__(agent=agent,
                                                          message=message,
                                                          is_initiator=True)
        self.role = role

    def handle_inform(self, message):
        config = pickle.loads(literal_eval(message.content))

        if self.role == 'MARKET_SCHEDULE':
            self.agent.total_storage_detailed_load = {str(i): j * 1e3 for i, j in config['total_storage_detailed_load'].items()}
            self.agent.prosumer_storage_detailed_load = {str(i): j * 1e3 for i, j in config['prosumer_storage_detailed_load'].items()}
            self.agent.bess_storage_detailed_load = {str(i): j * 1e3 for i, j in config['bess_storage_detailed_load'].items()}

            self.agent.old_prosumer_storage_detailed_load = {str(i): j * 1e3 for i, j in config['old_prosumer_storage_detailed_load'].items()}
            self.agent.new_detailed_load_dso = {str(i): j * 1e3 for i, j in config['new_detailed_load_dso'].items()}

            config = dict()
            config['prosumer_storage_detailed_load'] = self.agent.prosumer_storage_detailed_load
            config['bess_storage_detailed_load'] = self.agent.bess_storage_detailed_load
            config['base_detailed_load'] = self.agent.detailed_load
            content = pickle.dumps(config)

            self.agent.comp_cnp_2.answer.set_content(content)
            self.agent.comp_cnp_2.answer.set_message_length(np.random.randint(1000, 1500))
            self.agent.send(self.agent.comp_cnp_2.answer)

        elif self.role == 'MARKET_AUCTION_2':
            self.agent.real_time_total_storage_detailed_load = {str(i): j for i, j in config['total_storage_detailed_load'].items()}
            self.agent.real_time_prosumer_storage_detailed_load = {str(i): j for i, j in config['prosumer_storage_detailed_load'].items()}
            self.agent.real_time_bess_storage_detailed_load = {str(i): j for i, j in config['bess_storage_detailed_load'].items()}

            self.agent.real_time_old_prosumer_storage_detailed_load = {str(i): j for i, j in config['old_prosumer_storage_detailed_load'].items()}
            self.agent.real_time_new_detailed_load_dso = config['new_detailed_load_dso']

            config = dict()
            config['prosumer_storage_detailed_load'] = self.agent.real_time_new_detailed_load_dso
            content = pickle.dumps(config)

            self.agent.comp_cnp_2.answer.set_content(content)
            self.agent.comp_cnp_2.answer.set_message_length(np.random.randint(1000, 1500))
            self.agent.send(self.agent.comp_cnp_2.answer)


class DSOInitiatorContractNetProtocol(FipaContractNetProtocol):
    """AuctionClear

    Initial FIPA-ContractNet Behaviour that sends CFP messages
    to ProsumerAgents connected to BESSAgents asking for proposals.
    This behaviour also aggregate the proposals to find the
    clear value for the network state."""

    def __init__(self, agent, message, role):
        super(DSOInitiatorContractNetProtocol, self).__init__(
            agent=agent, message=message, is_initiator=True)
        self.cfp = message
        self.role = role
        self.restriction = dict()

    def handle_all_proposes(self, proposes):
        """
        """

        super(DSOInitiatorContractNetProtocol, self).handle_all_proposes(proposes)

        if self.role == 'AUCTION':
            self._handle_auction_proposes(proposes)
        elif self.role == 'SCHEDULE':
            self._handle_schedule_proposes(proposes)

    def _handle_schedule_proposes(self, proposes):
        display_message(self.agent.aid.name, 'Analyzing proposals...')

        agg_demand = np.zeros(96)
        # dict com chaves sendo nomes dos nós e valores lista 
        # com 96 pos. com schedule de carga
        self.agent.detailed_load = dict()
        self.agent.init_prosumer_storage_detailed_load = dict()
        self.agent.init_bess_storage_detailed_load = dict()
        
        self.agent.prosumer_storage_nodes = dict()
        self.agent.config_prosumer_bess_dso_dict = dict()

        self.agent.bess_storage_nodes = dict()
        self.agent.config_bess_dso_dict = dict()

        for propose in proposes:
            config = pickle.loads(literal_eval(propose.content))
            agg_demand += config['aggregate_demand']
            self.agent.detailed_load.update(config['detailed_load'])
            
            self.agent.init_prosumer_storage_detailed_load.update(config['prosumer_storage_detailed_load'])
            self.agent.config_prosumer_bess_dso_dict.update(config['prosumer_storage_config'])
            
            self.agent.init_bess_storage_detailed_load.update(config['bess_storage_detailed_load'])
            self.agent.config_bess_dso_dict.update(config['bess_storage_config'])

            bess_id = propose.sender.localname.split('bess')[1]
            self.agent.prosumer_storage_nodes[bess_id] = config['prosumer_storage_nodes']
            self.agent.bess_storage_nodes[bess_id] = config['bess_storage_nodes']

        # chama o metodo de analise do DSO em thread separada para não causar erro no loop do PADE
        defer_to_thread(self.analyse_schedule_grid_restrictions,
                        self.after_schedule_analyse_actions)

    def analyse_schedule_grid_restrictions(self):

        # verify if all the detailed_load and storage_detailed_load values have the same length
        aux1 = [len(v) for k, v in self.agent.detailed_load.items()]
        aux2 = [len(v) for k, v in self.agent.init_prosumer_storage_detailed_load.items()]
        if aux1[1:] == aux1[:-1] and aux2[1:] == aux2[:-1] and aux1[0] == aux2[0]:
            time_qtd = aux1[0]
        else:
            raise(Exception('The length of data in detailed_load is not the same!'))

        # adequação dos dicionarios de dados de carga
        # os pontos que não contém informação dos dicionários 
        # detailed_load, storage_detailed_load e control_storage_detailed_load
        #  são preenchidos com (time_qtd) valores zero.
        for node in self.agent.grid_data['nodes']:
            self.agent.detailed_load.setdefault(str(node['name']), np.zeros(time_qtd))
            self.agent.init_prosumer_storage_detailed_load.setdefault(str(node['name']), np.zeros(time_qtd))
            self.agent.init_bess_storage_detailed_load.setdefault(str(node['name']), np.zeros(time_qtd))
        # retira o nó '0' pois o Jacobiano não contem o nó referencia do sistema
        self.agent.init_prosumer_storage_detailed_load.pop('0')
        self.agent.init_bess_storage_detailed_load.pop('0')

        # define o dicionário com os lagrangianos para a otimização no caso de 
        # transactive control 
        self.agent.lagrangian_multiplier = {int(n): np.zeros(time_qtd) for n in self.agent.init_prosumer_storage_detailed_load.keys()}

        # cria o objecto net com as informções necessárias para execução de fluxo
        # de carga no pandapower
        self.agent.pp_net_schedule = create_grid_in_pandapower(self.agent.detailed_load)

        # executa fluxo de carga para cada um dos períodos estabelecidos nos dados
        # contidos nas informações de detailed_load
        (self.agent.v0_pu_list,
         self.agent.jac_inv_21_list) = run_powerflow_in_pandapower(self.agent.detailed_load,
                                                                   self.agent.pp_net_schedule,
                                                                   save=True)
        self.agent.branch_dict = create_branch_dict(self.agent.pp_net_schedule)
        self.agent.power_flow_matrix = create_power_flow_matrix(self.agent.branch_dict, self.agent.pp_net_schedule)

        return None

    def after_schedule_analyse_actions(self, result):
        # TODO: Esse metodo precisa ser refatorado por completo
        # pois nao representa mais o fluxo de informação proposto
        # storage_detailed_load = results[0]
        # new_scheduled_storage_load = results[1]
        # bess_storage_nodes = results[2]

        # self.agent.bess_nodes_schedule = new_scheduled_storage_load

        # answer = ACLMessage(ACLMessage.REJECT_PROPOSAL)
        # answer.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)

        # for bess_name, bess_nodes in bess_storage_nodes.items():
        #     new_schedules = dict()
        #     for bess_node in bess_nodes:
        #         new_schedules[str(bess_node)] = new_scheduled_storage_load[str(bess_node)]

        #     answer.set_content(pickle.dumps(new_schedules))
        #     answer.add_receiver(AID(name='bess{}'.format(bess_name)))
        #     self.agent.send(answer)

        self.agent.mosaik_sim.step_done_(time=60)
        display_message(self.agent.aid.name, '>>> STEP DONE')

    def _handle_auction_proposes(self, proposes):
        display_message(self.agent.aid.name, 'Analyzing proposals...')

        accepted_proposes_aids = list()
        not_accepted_proposes_aids = list()
        total_load = 0.0
        total_storage = 0.0
        detailed_load = dict()
        detailed_storage = dict()

        for message in proposes:
            display_message(self.agent.aid.name, 'PROPOSE message from {}'.format(message.sender.name))
            accepted_proposes_aids.append(message.sender.name)
            config = pickle.loads(literal_eval(message.content))

            for agent_id, load_value in config['real_time_load_value'].items():
                total_load += load_value
                detailed_load[str(agent_id)] = load_value

            for agent_id, storage_value in config['real_time_storage_value'].items():
                total_storage += storage_value
                detailed_storage[str(agent_id)] = storage_value

        #  tempo referente ao instante de tempo t = t0 + 2c
        time_index = int((self.agent.mosaik_sim.time -
                          OPERATION_TIME_DELAY) / TIME_INTERVAL) + 2
        # variavel com os valores de programação dos dispositivos
        # de armazenamento controláveis, para o instante de tempo
        # time_index 
        self.agent.init_real_time_bess_storage_detailed_load = {i: np.array([self.agent.bess_storage_detailed_load[i][time_index]])
            for i in self.agent.bess_storage_detailed_load.keys()}

        # adequação dos dicionarios de dados de carga
        # dos pontos que não contém informação dos dicionários 
        # detailed_load, storage_detailed_load e control_storage_detailed_load
        # são preenchidos com (time_qtd) valores zero.
        for node in self.agent.grid_data['nodes']:
            detailed_load.setdefault(str(node['name']), np.array([0.0]))
            detailed_storage.setdefault(str(node['name']), np.array([0.0]))
            self.agent.init_real_time_bess_storage_detailed_load.setdefault(str(node['name']), np.array([0.0]))

        detailed_load.pop('0')
        detailed_storage.pop('0')
        self.agent.init_real_time_bess_storage_detailed_load.pop('0')

        # avalia a diferença o que foi programado e o que será executado
        diff = dict()
        for k in self.agent.detailed_load.keys():
            if k in detailed_load.keys() and k in detailed_storage.keys():
                try:
                    a = self.agent.detailed_load[k][time_index] + \
                        self.agent.prosumer_storage_detailed_load[k][time_index]
                    b = detailed_load[k][0] + \
                        detailed_storage[k][0]
                    diff[k] = (a - b)
                    display_message(self.agent.aid.name,
                                    'PROSUMER {} --> DIFF: {:5.3f}'.format(k, diff[k]))
                except KeyError:
                    print('KeyError, chave nao encontrada no dicionario')

        total_detailed_load_kw = {i: [detailed_load[i][0] +
                                      detailed_storage[i][0] +
                                      self.agent.init_real_time_bess_storage_detailed_load[i][0]]
                                  for i in self.agent.bess_storage_detailed_load.keys()}

        if not self.agent.pp_net_operation:
            self.agent.pp_net_operation = create_grid_in_pandapower(self.agent.detailed_load)

        defer_to_thread(self.analyse_auction_grid_restrictions,
                        self.after_auction_analyse_actions,
                        total_detailed_load_kw,
                        detailed_load,
                        detailed_storage)

    def analyse_auction_grid_restrictions(self,
                                          total_detailed_load_kw,
                                          detailed_load,
                                          detailed_storage):

        (max_current_restriction,
         max_voltage_restriction,
         min_voltage_restriction) = calc_grid_restrictions(self.agent.pp_net_operation,
                                                           total_detailed_load_kw,
                                                           self.agent.power_flow_matrix,
                                                           self.agent.branch_dict)

        self.agent.max_current_restriction = max_current_restriction
        self.agent.max_voltage_restriction = max_voltage_restriction
        self.agent.min_voltage_restriction = min_voltage_restriction

        if (self.agent.max_current_restriction.any() or
            self.agent.max_voltage_restriction.any() or
            self.agent.min_voltage_restriction.any()):

            display_message(self.agent.aid.name, 'RESTRICAO VIOLADA NA OPERACAO')

            self.agent.grid_restriction = True

            detailed_load_plus_storage = {i: detailed_load[i] +
                                          detailed_storage[i]
                                          for i in detailed_load.keys()}

            v0_pu_list, jac_inv_21_list = run_powerflow_in_pandapower(detailed_load_plus_storage,
                                                                      self.agent.pp_net_operation,
                                                                      save=False)

            operation_model = solve_dso_operation(detailed_load_plus_storage,
                                                  self.agent.init_real_time_bess_storage_detailed_load,
                                                  self.agent.bess_storage_nodes,
                                                  v0_pu_list,
                                                  jac_inv_21_list,
                                                  self.agent.power_flow_matrix,
                                                  self.agent.branch_dict,
                                                  self.agent.config_bess_dso_dict)

            if operation_model:
                display_message(self.agent.aid.name, 'ALTERACAO CALCULADA E POSSIVEL')
                self.agent.bess_storage_alt = True

                # envia as novas programações para os dispositivos de
                # armazenamento controláveis
                self.agent.real_time_bess_storage_detailed_load = dict()
                for n in operation_model.set_node:
                    aux1 = list()
                    for t in operation_model.set_time:
                        aux1.append(operation_model.var_control_power[n, t].value * 1e3)
                    self.agent.real_time_bess_storage_detailed_load[str(n)] = np.array(aux1)

                config = dict()
                config['message_type'] = 'STORAGE_SCHEDULE_2'
                config['bess_storage_detailed_load'] = self.agent.real_time_bess_storage_detailed_load
                content = pickle.dumps(config)

                message = ACLMessage(ACLMessage.INFORM)
                message.set_protocol(ACLMessage.FIPA_SUBSCRIBE_PROTOCOL)
                message.set_message_length(np.random.randint(1000, 1500))
                message.set_content(content)

                self.agent.comp_pubsub_1.accept_confirmation_count = 0
                self.agent.comp_pubsub_1.schedule_accept_message = None
                self.agent.comp_pubsub_1.notify(message)

            else:
                display_message(self.agent.aid.name, 'ALTERACAO NAO E POSSIVEL')

                self.agent.real_time_detailed_load = detailed_load
                self.agent.init_real_time_prosumer_storage_detailed_load = detailed_storage

                (self.agent.v0_pu_list,
                 self.agent.jac_inv_21_list) = run_powerflow_in_pandapower(self.agent.real_time_detailed_load,
                                                                          self.agent.pp_net_operation,
                                                                          save=False)

                self.agent.lagrangian_multiplier = {int(n): np.zeros(1)
                                                    for n in self.agent.init_real_time_prosumer_storage_detailed_load.keys()}

                self.agent.bess_storage_alt = False
        else:
            display_message(self.agent.aid.name, 'NAO HA VIOLACAO DE RESTRICOES NA OPERACAO')
            self.agent.grid_restriction = False
            self.agent.bess_storage_alt = False

        return None

    def after_auction_analyse_actions(self, results):

        # answer = ACLMessage(ACLMessage.REJECT_PROPOSAL)
        # answer.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
        # answer.add_receiver(AID(name='bess{}'.format(bess_name)))
        # config = dict()
        # content = pickle.dumps(config)
        # answer.set_content(content)
        # self.agent.send(answer)
        if not self.agent.bess_storage_alt:
            self.agent.auction_finished = True
            self.agent.mosaik_sim.step_done()
            display_message(self.agent.aid.name, '>>> STEP DONE')

    def handle_inform(self, message):
        """
        """
        super(DSOInitiatorContractNetProtocol, self).handle_inform(message)

        display_message(self.agent.aid.name, 'INFORM message received')

    def handle_refuse(self, message):
        """
        """
        super(DSOInitiatorContractNetProtocol, self).handle_refuse(message)

        display_message(self.agent.aid.name, 'REFUSE message received')

    def handle_propose(self, message):
        """
        """
        super(DSOInitiatorContractNetProtocol, self).handle_propose(message)

        display_message(self.agent.aid.name, 'PROPOSE message received')


class DSOParticipantContractNetProtocol(FipaContractNetProtocol):
    def __init__(self, agent):
        super(DSOParticipantContractNetProtocol, self).__init__(agent=agent,
                                                                message=None,
                                                                is_initiator=False)
        self.role = None
        self.schedule_accept_message = None

    def handle_cfp(self, message):
        """
        """
        self.agent.call_later(random.uniform(0.1, 0.2), self._handle_cfp, message)

    def _handle_cfp(self, message):
        """
        """
        super(DSOParticipantContractNetProtocol, self).handle_cfp(message)
        self.message = message

        display_message(self.agent.aid.name, 'CFP message received')

        if message.content == 'MARKET_SCHEDULE':
            self._handle_schedule_request(message)
            self.role = 'MARKET_SCHEDULE'
        elif message.content == 'MARKET_AUCTION':
            self._handle_auction_request(message)
            self.role = 'MARKET_AUCTION'
        elif message.content == 'MARKET_AUCTION_2':
            self._handle_auction_2_request(message)
            self.role = 'MARKET_AUCTION_2'

    def _handle_schedule_request(self, message):

        config = dict()
        config['detailed_load'] = self.agent.detailed_load  # ok
        config['storage_detailed_load'] = self.agent.init_prosumer_storage_detailed_load  # ok
        config['control_storage_detailed_load'] = self.agent.init_bess_storage_detailed_load  # ok
        config['bess_storage_nodes'] = self.agent.prosumer_storage_nodes  # ok
        config['control_bess_storage_nodes'] = self.agent.bess_storage_nodes  # ok
        config['v0_pu_list'] = self.agent.v0_pu_list  # ok
        config['jac_inv_21_list'] = self.agent.jac_inv_21_list  # ok
        config['lagrangian_multiplier'] = self.agent.lagrangian_multiplier  # ok
        config['power_flow_matrix'] = self.agent.power_flow_matrix  # ok
        config['branch_dict'] = self.agent.branch_dict  # ok
        config['config_bess_dso_dict'] = self.agent.config_bess_dso_dict  # ok
        config['config_prosumer_bess_dso_dict'] = self.agent.config_prosumer_bess_dso_dict # ok

        message = ACLMessage(ACLMessage.REQUEST)
        message.set_protocol(ACLMessage.FIPA_REQUEST_PROTOCOL)
        message.add_receiver(AID(name='solver'))
        content = pickle.dumps(config)
        message.set_content(content)
        message.set_message_length(np.random.randint(1000, 1500))

        if self.agent.comp_request_1 is None:
            self.agent.comp_request_1 = DSOInitiatorRequestProtocol(self.agent,
                                                                    message,
                                                                    'MARKET_SCHEDULE')
            self.agent.behaviours.append(self.agent.comp_request_1)
            self.agent.comp_request_1.on_start()
        else:
            self.agent.comp_request_1.message = message
            self.agent.comp_request_1.role = 'MARKET_SCHEDULE'
            self.agent.comp_request_1.on_start()

        self.answer = self.message.create_reply()
        self.answer.set_performative(ACLMessage.PROPOSE)

    def _handle_auction_request(self, message):
        answer = self.message.create_reply()
        answer.set_performative(ACLMessage.PROPOSE)

        config = dict()
        config['grid_restriction'] = self.agent.grid_restriction
        config['bess_storage_alt'] = self.agent.bess_storage_alt
        content = pickle.dumps(config)

        answer.set_content(content)
        answer.set_message_length(np.random.randint(1000, 1500))
        self.agent.send(answer)

    def _handle_auction_2_request(self, message):
        # self.agent.init_real_time_prosumer_storage_detailed_load.setdefault('0', np.array([0.0]))
        # self.agent.init_real_time_bess_storage_detailed_load.setdefault('0', np.array([0.0]))

        config = dict()
        config['detailed_load'] = self.agent.real_time_detailed_load  # ok
        config['storage_detailed_load'] = self.agent.init_real_time_prosumer_storage_detailed_load  # ok
        config['control_storage_detailed_load'] = self.agent.init_real_time_bess_storage_detailed_load # ok
        config['bess_storage_nodes'] = self.agent.prosumer_storage_nodes  # ok
        config['control_bess_storage_nodes'] = self.agent.bess_storage_nodes  # ok
        config['v0_pu_list'] = self.agent.v0_pu_list  # ok
        config['jac_inv_21_list'] = self.agent.jac_inv_21_list  # ok
        config['lagrangian_multiplier'] = self.agent.lagrangian_multiplier  # ok
        config['power_flow_matrix'] = self.agent.power_flow_matrix  # ok
        config['branch_dict'] = self.agent.branch_dict  # ok
        config['config_bess_dso_dict'] = self.agent.config_bess_dso_dict  # ok
        config['config_prosumer_bess_dso_dict'] = self.agent.config_prosumer_bess_dso_dict # ok

        message = ACLMessage(ACLMessage.REQUEST)
        message.set_protocol(ACLMessage.FIPA_REQUEST_PROTOCOL)
        message.add_receiver(AID(name='solver'))
        content = pickle.dumps(config)
        message.set_content(content)
        message.set_message_length(np.random.randint(1000, 1500))

        if self.agent.comp_request_1 is None:
            self.agent.comp_request_1 = DSOInitiatorRequestProtocol(self.agent,
                                                                    message,
                                                                    'MARKET_AUCTION_2')
            self.agent.behaviours.append(self.agent.comp_request_1)
            self.agent.comp_request_1.on_start()
        else:
            self.agent.comp_request_1.message = message
            self.agent.comp_request_1.role = 'MARKET_AUCTION_2'
            self.agent.comp_request_1.on_start()

        self.answer = self.message.create_reply()
        self.answer.set_performative(ACLMessage.PROPOSE)

    def handle_accept_propose(self, message):
        super(DSOParticipantContractNetProtocol, self).handle_accept_propose(message)

        if self.role == 'MARKET_SCHEDULE':
            self.schedule_accept_message = message

            config = pickle.loads(literal_eval(message.content))
            self.agent.lagrangian_multiplier = config['lagrangian_multiplier']

            config = dict()
            config['message_type'] = 'STORAGE_SCHEDULE'
            config['bess_storage_detailed_load'] = self.agent.bess_storage_detailed_load
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

            defer_to_thread(self.analyse_new_schedule,
                            self.after_analyse_new_schedule)
        elif self.role == 'MARKET_AUCTION_2':
            config = pickle.loads(literal_eval(message.content))
            self.agent.lagrangian_multiplier = config['lagrangian_multiplier']

            config = dict()
            config['message_type'] = 'STORAGE_SCHEDULE_2'
            config['bess_storage_detailed_load'] = self.agent.real_time_bess_storage_detailed_load
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

    def analyse_new_schedule(self):
        # executa fluxo de carga com novo schedule de carga
        new_detailed_load = dict()
        for node in self.agent.detailed_load.keys():
            if node == '0':
                new_detailed_load[node] = self.agent.detailed_load[node]
            else:
                new_detailed_load[node] = (self.agent.detailed_load[node] +
                                           np.array(self.agent.total_storage_detailed_load[node]))

        v0_pu_list, jac_inv_21_list = run_powerflow_in_pandapower(new_detailed_load,
                                                                  self.agent.pp_net_schedule,
                                                                  save=True,
                                                                  file_name='new_power_flow_data')

    def after_analyse_new_schedule(self, results):
        pass

    def handle_reject_propose(self, message):
        super(DSOParticipantContractNetProtocol, self).handle_reject_propose(message)
        if self.role == 'MARKET_SCHEDULE':
            config = pickle.loads(literal_eval(message.content))
            self.agent.lagrangian_multiplier = config['lagrangian_multiplier']
        elif self.role == 'MARKET_AUCTION_2':
            config = pickle.loads(literal_eval(message.content))
            self.agent.lagrangian_multiplier = config['lagrangian_multiplier']

    def handle_inform(self, message):
        pass


class DSOPublisherProtocol(FipaSubscribeProtocol):

    def __init__(self, agent):
        super(DSOPublisherProtocol, self).__init__(agent,
                                                    message=None,
                                                    is_initiator=False)
        self.schedule_accept_message = None
        self.accept_confirmation_qtd = 0
        self.accept_confirmation_count = 0

    def handle_subscribe(self, message):
        self.register(message.sender)
        self.accept_confirmation_qtd = len(self.subscribers)
        display_message(self.agent.aid.name, message.content)
        answear = message.create_reply()
        answear.set_performative(ACLMessage.AGREE)
        answear.set_content('Subscribe message accepted')
        answear.set_message_length(100)
        self.agent.send(answear)

    def handle_cancel(self, message):
        self.deregister(self, message.sender)
        display_message(self.agent.aid.name, message.content)

    def notify(self, message):
        super(DSOPublisherProtocol, self).notify(message)

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
                if self.schedule_accept_message is not None:
                    reply = self.schedule_accept_message.create_reply()
                    reply.set_performative(ACLMessage.INFORM)
                    config = dict()
                    config['message_type'] = 'DSO CONFIRM'
                    content = pickle.dumps(config)
                    reply.set_content(content)
                    reply.set_message_length(100)
                    self.agent.send(reply)
                else:
                    self.agent.auction_finished = True
                    self.agent.mosaik_sim.step_done()
                    display_message(self.agent.aid.name, '>>> STEP DONE')

class DSOAgent(Agent):
    def __init__(self, aid, bess_list, mode):
        super(DSOAgent, self).__init__(aid=aid, debug=False, mode=mode)
        self.mosaik_sim = MosaikSim(self)
        self.bess_list = bess_list
        self.dso_param = None
        self.pp_net_schedule = None
        self.pp_net_operation = None
        self.runnning_power_flow = False

        self.grid_restriction = None
        self.bess_storage_alt = None
        self.max_current_restriction = None
        self.max_voltage_restriction = None
        self.min_voltage_restriction = None

        # variaveis para a fase de planejamento
        self.detailed_load = None
        self.total_storage_detailed_load = None
        self.init_prosumer_storage_detailed_load = None
        self.prosumer_storage_detailed_load = None
        self.init_bess_storage_detailed_load = None
        self.bess_storage_detailed_load = None
        self.prosumer_storage_nodes = None
        self.bess_storage_nodes = None
        self.v0_pu_list = None
        self.jac_inv_21_list = None
        self.lagrangian_multiplier = None
        self.power_flow_matrix = None
        self.branch_dict = None
        self.config_prosumer_bess_dso_dict = None
        self.config_bess_dso_dict = None

        # variaveis para a fase de operação

        self.real_time_detailed_load = None
        self.init_real_time_prosumer_storage_detailed_load = None
        self.init_real_time_bess_storage_detailed_load = None

        self.real_time_total_storage_detailed_load = None
        self.real_time_prosumer_storage_detailed_load = None
        self.real_time_bess_storage_detailed_load = None

        self.real_time_old_prosumer_storage_detailed_load = None
        self.real_time_new_detailed_load_dso = None

        # argumentos retornados pelo solver
        # como resltados do processo de otimização
        self.old_prosumer_storage_detailed_load = None
        self.new_detailed_load_dso = None

        with open('force.json', 'r') as f:
            self.grid_data = json.load(f)

        self.comp_cnp_1 = None
        self.comp_cnp_2 = DSOParticipantContractNetProtocol(self)
        self.behaviours.append(self.comp_cnp_2)

        self.comp_pubsub_1 = DSOPublisherProtocol(self)
        self.behaviours.append(self.comp_pubsub_1)

        self.comp_request_1 = None
