from pade.misc.utility import display_message, defer_to_thread, get_reactor
from pade.core.agent import Agent
from pade.acl.messages import ACLMessage
from pade.acl.aid import AID
from pade.behaviours.protocols import FipaRequestProtocol

from random import randint
import pickle
from ast import literal_eval
import numpy as np
import pandas as pd
import time

from stochastic_model.run_stochastic_model import main as solve_prosumer_model
from grid_optimization import solve_dso_reschedule as solve_dso_model
from grid_optimization import solve_bess_reschedule as solve_bess_model


prices_data = pd.read_excel('epex_sample.xlsx', sheet_name='spot_data', index_col=0)
_prices = prices_data.iloc[:, randint(0, 6)].to_numpy()
PRICES = np.array([])
for i in _prices:
    PRICES = np.concatenate((PRICES, np.ones(4) * i))


class CompRequest(FipaRequestProtocol):
    """FIPA Request Behaviour of the Time agent.
    """

    def __init__(self, agent):
        super(CompRequest, self).__init__(agent=agent,
                                          message=None,
                                          is_initiator=False)

        self.solver_queue = list()

    def handle_request(self, message):
        super(CompRequest, self).handle_request(message)
        self.process_solve_request(message, False)

    def process_solve_request(self, message, active):
        a = active and self.solver_queue
        b = not active and self.solver_queue
        c = not active and not self.solver_queue

        if a:
            config = pickle.loads(literal_eval(message.content))
            print('solver queue lenght: {}'.format(len(self.solver_queue)))
            if 'prosumer' in message.sender.name:
                self.calc_prosumer_model(config)
            elif 'bess' in message.sender.name:
                self.calc_bess_model(config)
            elif 'dso' in message.sender.name:
                self.calc_dso_model(config)
        elif b:
            self.solver_queue.append(message)
        elif c:
            config = pickle.loads(literal_eval(message.content))
            print('solver queue lenght: {}'.format(len(self.solver_queue)))
            self.solver_queue.append(message)
            if 'prosumer' in message.sender.name:
                self.calc_prosumer_model(config)
            elif 'bess' in message.sender.name:
                self.calc_bess_model(config)
            elif 'dso' in message.sender.name:
                self.calc_dso_model(config)

    def calc_prosumer_model(self, config):
        display_message(self.agent.aid.name, 'STARTING PROSUMER OPTIMIZATION PROCESS...')
        defer_to_thread(solve_prosumer_model,
                        self.process_prosumer_model_results,
                        config)

    def calc_bess_model(self, config):
        display_message(self.agent.aid.name, 'STARTING BESS OPTIMIZATION PROCESS...')
        defer_to_thread(solve_bess_model,
                        self.process_bess_model_results,
                        config['nodes'],
                        config['storage_detailed_load'],
                        config['lagrangian_multiplier'],
                        config['prosumer_storage_config'])

    def calc_dso_model(self, config):
        display_message(self.agent.aid.name, 'STARTING DSO OPTIMIZATION PROCESS...')
        defer_to_thread(solve_dso_model,
                        self.process_dso_model_results,
                        config['detailed_load'],
                        config['storage_detailed_load'],
                        config['control_storage_detailed_load'],
                        config['bess_storage_nodes'],
                        config['control_bess_storage_nodes'],
                        config['v0_pu_list'],
                        config['jac_inv_21_list'],
                        config['lagrangian_multiplier'],
                        config['power_flow_matrix'],
                        config['branch_dict'],
                        config['config_bess_dso_dict'],
                        config['config_prosumer_bess_dso_dict'])

    def process_prosumer_model_results(self, model):
        message = self.solver_queue.pop(0)
        config = pickle.loads(literal_eval(message.content))

        content = dict()
        content['bilateral_contract_purchase'] = [i.value for i in model.p_bilateral.values()]

        if config['has_storage']:
            c = np.array(list(model.p_charge.get_values().values()))
            d = np.array(list(model.p_discharge.get_values().values()))
            content['storage_schedule'] = c - d
            content['storage_charge_commands'] = list(model.charging.get_values().values())
            content['storage_discharge_commands'] = list(model.discharging.get_values().values())
        else:
            content['storage_schedule'] = np.zeros(96)
            content['storage_charge_commands'] = list(np.zeros(96))
            content['storage_discharge_commands'] = list(np.zeros(96))

        display_message(self.agent.aid.name, 'PROSUMER OPTIMIZATION PROCESS FINISHED...')

        reply = message.create_reply()
        reply.set_performative(ACLMessage.INFORM)

        reply.set_content(pickle.dumps(content))
        self.agent.send(reply)

        if self.solver_queue:
            message = self.solver_queue[0]
            self.agent.call_later(0.1,
                                  self.process_solve_request,
                                  message,
                                  True)

    def process_bess_model_results(self, model):
        message = self.solver_queue.pop(0)

        prosumer_storage_detailed_load = dict()
        for n in model.set_node:
            aux1 = list()
            for t in model.set_time:
                aux1.append(model.var_power[n, t].value)
            prosumer_storage_detailed_load[n] = np.array(aux1)

        new_detailed_load_bess = dict()
        for n in model.set_node:
            laux = list()
            for t in model.set_time:
                laux.append(model.var_power[n, t].value)
            new_detailed_load_bess[str(n)] = np.array(laux)

        config = dict()
        config['prosumer_storage_detailed_load'] = prosumer_storage_detailed_load
        config['new_detailed_load_bess'] = new_detailed_load_bess

        content = pickle.dumps(config)

        display_message(self.agent.aid.name, 'BESS OPTIMIZATION PROCESS FINISHED...')

        reply = message.create_reply()
        reply.set_performative(ACLMessage.INFORM)
        reply.set_content(content)
        self.agent.send(reply)

        if self.solver_queue:
            message = self.solver_queue[0]
            self.agent.call_later(0.1,
                                  self.process_solve_request,
                                  message,
                                  True)

    def process_dso_model_results(self, model):
        message = self.solver_queue.pop(0)

        total_storage_detailed_load = dict()
        prosumer_storage_detailed_load = dict()
        bess_storage_detailed_load = dict()
        old_prosumer_storage_detailed_load = dict()

        for n in model.set_node:
            aux1 = list()
            aux2 = list()
            aux3 = list()
            aux4 = list()
            for t in model.set_time:
                aux1.append(model.var_power[n, t].value + model.var_control_power[n, t].value)
                aux2.append(model.var_power[n, t].value)
                aux3.append(model.var_control_power[n, t].value)
                aux4.append(model.param_power[n, t])

            total_storage_detailed_load[n] = np.array(aux1)
            prosumer_storage_detailed_load[n] = np.array(aux2)
            bess_storage_detailed_load[n] = np.array(aux3)
            old_prosumer_storage_detailed_load[n] = np.array(aux4)

        new_detailed_load_dso = dict()
        for n in model.set_node:
            laux = list()
            for t in model.set_time:
                laux.append(model.var_power[n, t].value)
            new_detailed_load_dso[str(n)] = np.array(laux)

        config = dict()
        config['total_storage_detailed_load'] = total_storage_detailed_load
        config['prosumer_storage_detailed_load'] = prosumer_storage_detailed_load
        config['bess_storage_detailed_load'] = bess_storage_detailed_load
        config['old_prosumer_storage_detailed_load'] = old_prosumer_storage_detailed_load
        config['new_detailed_load_dso'] = new_detailed_load_dso

        content = pickle.dumps(config)

        display_message(self.agent.aid.name, 'DSO OPTIMIZATION PROCESS FINISHED...')

        reply = message.create_reply()
        reply.set_performative(ACLMessage.INFORM)
        reply.set_content(content)
        self.agent.send(reply)

        if self.solver_queue:
            message = self.solver_queue[0]
            self.agent.call_later(0.1,
                                  self.process_solve_request,
                                  message,
                                  True)


class SolverAgent(Agent):
    """Class that defines the Time agent."""

    def __init__(self, aid, mode):
        super(SolverAgent, self).__init__(aid=aid, debug=False, mode=mode)
        self.comport_request = CompRequest(self)
        self.behaviours.append(self.comport_request)
