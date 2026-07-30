r"""Este arquivo contém as classes que implementam os comportamentos
fundamentais dos principais componentes elétricos de uma unidade
consumidora/produtora de energia, tais como:
- Load;
- Generation;
- Storage;
- Prosumer.
"""

from random import uniform, randint, choice
import datetime as dt
import json
import numpy as np
import pandas as pd

from load_data import get_load_data, get_gen_data


def generate_timeseries(start, time, step):
    """
        start = string em formato datetime: dd/mm/YYYY - hh:mm:ss
        time = tamanho da série temporal em segundos
        step = step de tempo em minutos
    """
    time_step = step * 60 # seconds
    #dt_start = dt.datetime.strptime(start, '%d/%m/%Y - %H:%M:%S')
    dt_start = start
    delta = dt.timedelta(0, time)

    delta_sec = delta.days * (24 * 60 * 60) + delta.seconds

    res = [dt_start + dt.timedelta(0, t) for t in range(0, delta_sec, time_step)]
    # res_pp = [i.strftime('%D - %T') for i in res]
    return res



def random_shiftable_load_generator(qtd=None,
                                    demand_range=None,
                                    frequency_range=None,
                                    cycles_range=None):
    """cria lista de cargas como esta:

    loads = [{'id': 1, 'demand': 0.8, 'cycles': 20, 'frequency': 1},
             {'id': 2, 'demand': 0.5, 'cycles': 5, 'frequency': 1},
             {'id': 3, 'demand': 1.8, 'cycles': 2, 'frequency': 2},
             {'id': 4, 'demand': 0.7, 'cycles': 5, 'frequency': 4}]"""
    loads = []
    for i in range(qtd):
        load = {'id': i,
                'demand': uniform(demand_range[0], demand_range[1]),
                'cycles': randint(cycles_range[0], cycles_range[1]),
                'frequency': randint(frequency_range[0], frequency_range[1])}
        loads.append(load)

    return loads

def random_schedule_load_generator(loads=None, datetime=None):
    """cria lista de agendamento de cargas
    schedules = [{'id': 1,
                  'start': dt.datetime.strptime('01/08/2019 - 02:00:00', '%d/%m/%Y - %H:%M:%S')},
                 {'id': 2,
                  'start': dt.datetime.strptime('01/08/2019 - 06:00:00', '%d/%m/%Y - %H:%M:%S')},
                 {'id': 3,
                  'start': dt.datetime.strptime('01/08/2019 - 08:00:00', '%d/%m/%Y - %H:%M:%S')},
                 {'id': 4,
                  'start': dt.datetime.strptime('01/08/2019 - 12:00:00', '%d/%m/%Y - %H:%M:%S')}
                ]
    """
    schedules = []
    times = generate_timeseries(datetime, 24 * 60 * 60, 15)
    for load in loads:
        schedule = {'id': load['id'], 'start': choice(times)}
        schedules.append(schedule)
    return schedules


class ShiftableLoad(object):

    def __init__(self, datetime, loads):
        """
            This are devices that can shift its operation in time within certain limits
            datetime = string em formato datetime: dd/mm/YYYY - hh:mm:ss
            loads = a list of dictonaries with values of shiftable loads demand in kW, number of 15min action
                    cycles and it's frequency in days.
                    loads = [{'id': 1, 'demand': 0.8, 'cycles': 4, 'frequency': 1}]
        """
        self.datetime = datetime
        self.loads = pd.DataFrame(loads)
        self.loads.set_index('id', inplace=True)
        self.p_out = 0.0

    def set_schedule(self, schedule_list):
        for i in schedule_list:
            i['end'] = i['start'] + self.loads.loc[i['id']]['cycles'] * dt.timedelta(minutes=15)
            i['status'] = False
        schedule_dt = pd.DataFrame(schedule_list).set_index('id')
        self.loads = self.loads.join(schedule_dt)

        # this ensure that the columns start and end
        self.loads['start'] = pd.to_datetime(self.loads['start'])
        self.loads['end'] = pd.to_datetime(self.loads['end'])

    def step(self, datetime, commands):
        demand = 0.0

        start_loads = self.loads.loc[self.loads.start == datetime]
        for index, row in start_loads.iterrows():
            self.loads.at[index, 'status'] = True
            # print('Load {} started........'.format(index))

        end_loads = self.loads.loc[self.loads.end == datetime]
        for index, row in end_loads.iterrows():
            self.loads.at[index, 'status'] = False
            # FIX THIS
            # self.loads.at[index, 'start'] += dt.timedelta(days=row['frequency'])
            # self.loads.at[index, 'end'] += dt.timedelta(days=row['frequency']) + row['cycles'] * dt.timedelta(minutes=15)
            # print('Load {} ended........'.format(index))

        active_loads = self.loads.loc[self.loads.status == True]
        for index, row in active_loads.iterrows():
            demand += row['demand']

        self.p_out = float(demand)
        return self.p_out


class UserLoad(object):
    """Representa uma classe que a cada passo
    de tempo retorna a demanda média de energia 
    para um determinado período de tempo.
    """
    def __init__(self, datetime, max_dem_value, load_id=None):

        self.p_out = 0.0
        self.demand_forecast = 0.0
        self.datetime = datetime
        self.load_id = load_id


        # ============================================================
        # ATENÇAO: Este trecho de código irá variar de acordo com 
        # os dados que estão sendo utilizados
        t_series = generate_timeseries(datetime, 1 * 24 * 60 * 60, 15)  # 1 dia segmentado em intervalos de 15 min.

        # definição da curva de carga do consumidor
        data = get_load_data(load_index=self.load_id)
        data = data[:24*4]
        # normalizacao dos valores de carga retornados
        data = (data-data.min())/(data.max()-data.min())
        data = max_dem_value * data.values

        self.load_curve = pd.DataFrame(data, index=t_series, columns=['pload', 'qload'])
        # ============================================================

    def step(self, datetime, commands):
        """
        """
        time_delta = datetime - self.datetime
        delta_in_hours = time_delta.seconds / (60.0 * 60.0)

        self.datetime = datetime
        self.p_out = self.load_curve['pload'][datetime]
        self.energy = round(self.p_out * delta_in_hours, 2)

        return float(self.p_out)

    def forecast(self, datetime):
        datetime_list = [datetime + dt.timedelta(0, 15.0 * 60.0 * i) for i in range(15)]
        self.demand_forecast = np.mean(self.load_curve['pload'][datetime_list])
        self.energy_forecast = round(self.demand_forecast * 15.0 / 60.0, 2)
        return self.demand_forecast

    def __repr__(self):
        return 'Load'


class DieselGeneration(object):
    """
        Descrição
        ----------

        O modelo aqui desenvolvido faz as seguintes considerações:
        O gerador só pode estar em dois estados:
        1. Desligado
        2. Ligado e gerando a potência nominal
        
        A quantidade de combustível restante no tanque do gerador 
        não está sendo levada em consideração, ou seja,
        assume-se que sempre haverá combustível suficiente para o
        gerador.

        A cada passo de interação no método step() será calculado
        o custo marginal da produção de energia para o próximo leilão
        e a poência atual entregue pelo gerador à rede elétrica, que pode 
        ser 0.0 caso o gerador encontre-se desligado ou igual sua potência
        nominal caso encontre-se desligado.
    """
    def __init__(self,
                 datetime,
                 fuel_price=0.0,
                 generator_fuel_rate=0.0,
                 generator_electrical_power=0.0,
                 maintenance_cost_rate=0.0,
                 add_startup_maintenance_cost=0.0,
                 add_startup_fuel_use=0.0):

        self.datetime = datetime
        self.on_off = False
        self.fuel_price = fuel_price # in US$/m3
        self.generator_fuel_rate = generator_fuel_rate # in Wh/m3
        self.generator_electrical_power = generator_electrical_power # in Watts
        self.maintenance_cost_rate = maintenance_cost_rate # in US$/h
        self.add_startup_maintenance_cost = add_startup_maintenance_cost # in US$
        self.add_startup_fuel_use = add_startup_fuel_use # in m3
        self.p_out = 0.0
        self.data = pd.DataFrame()

    def calc_marginal_cost(self, time, started):
        marg_cost = (self.generator_electrical_power * self.fuel_price)
        marg_cost /= self.generator_fuel_rate
        marg_cost += self.maintenance_cost_rate
        marg_cost *= time
        if started is False:
            marg_cost += self.add_startup_maintenance_cost
            marg_cost += self.add_startup_fuel_use * self.fuel_price
        elif started is True:
            pass
        return marg_cost

    def step(self, datetime, commands):

        delta_in_hours = 0.0
        self.delta = datetime - self.datetime
        delta_in_hours = self.delta.seconds / (60.0 * 60.0)
        
        self.p_out = 0.0

        if commands.get('on_off') is not None:
            self.on_off = commands['on_off']
        
        # =================================================
        # cálculo do custo marginal do gerador diesel
        # para o intervalo de 15min na próxima negociação
        # =================================================
        marg_cost = self.calc_marginal_cost(0.25, self.on_off)
        self.datetime = datetime

        if self.on_off is True:
            self.p_out = self.generator_electrical_power

        # self.data = self.data.append({'datetime': datetime,
        #                               'state': self.on_off,
        #                               'demand': demand,
        #                               'marginal_cost': marg_cost},
        #                               ignore_index=True)
        
        return - float(self.p_out)


class PVGeneration(object):
    """Representa uma classe que a cada passo
    de tempo retorna a produção média de energia 
    para um determinado período de tempo.
    """
    def __init__(self, datetime, max_gen_value, gen_id=None):

        self.p_out = 0.0
        self.demand_forecast = 0.0
        self.datetime = datetime
        self.gen_id = gen_id

        # ============================================================
        # ATENÇÂO: Este trecho de código irá variar de acordo com 
        # os dados que estão sendo utilizados
        t_series = generate_timeseries(datetime, 1 * 24 * 60 * 60, 15)  # 1 dia segmentado em intervalos de 15 min.

        # definição da curva de geração
        data = get_gen_data(gen_index=self.gen_id)
        data = data[:24*4]
        # normalizacao dos valores de geracao retornados
        data = (data-data.min())/(data.max()-data.min())
        data = max_gen_value * data.values

        self.gen_curve = pd.DataFrame(data, index=t_series, columns=['pgen'])
        # ============================================================

    def step(self, datetime, commands):
        """
        """
        time_delta = datetime - self.datetime
        delta_in_hours = time_delta.seconds / (60.0 * 60.0)
        self.datetime = datetime
        self.p_out = self.gen_curve['pgen'][datetime]
        self.energy = round(self.p_out * delta_in_hours, 2)

        return - float(self.p_out)

    def forecast(self, datetime):
        datetime_list = [datetime + dt.timedelta(0, 15.0 * 60.0 * i) for i in range(15)]
        self.energy_forecast = round(self.demand_forecast * 15.0 / 60.0, 2)
        return - self.demand_forecast

    def __repr__(self):
        return 'Generation'


class Storage(object):
    """
    Descrição
    ---------

    O modelo de bateria desenvolvido até este ponto
    realiza as seguintes considerações:
    1. A bateria pode estar em um de três estados possíveis:
        - loading
        - waiting
        - unloading
    2. Sempre que nos estados loading ou unloading a bateria
    estrá funcionando em sua potência nominal.

    O histório de preços terá 50 posições de armazenamento e só
    começará suas análises depois de ter 20 posições preenchidas.
    A analise será da seguinte forma: Os 8 maiores preços e os 
    8 menores preços serão descartados, após o descarte o menor
    preço da lista será o preço máximo de compra de energia e o
    maior preço da lista será o preço mínimo de venda.

    """

    def __init__(self,
                 datetime,
                 storage_electrical_rate=0.1,
                 storage_capacity=2.0,
                 efficiency=1.0):

        self.storage_capacity = storage_capacity  # in Wh
        self.storage_energy_level = 0.5 * storage_capacity  # in Wh
        self.storage_minimum_backup = 0.1 * storage_capacity
        self.storage_state = 'charging'  # can be charging, discharging or floating
        self.storage_electrical_power = storage_electrical_rate * storage_capacity  # in W in hours
        self.efficiency = efficiency
        self.datetime = datetime
        self.p_out = 0.0
        self.data = pd.DataFrame()

    def step(self, datetime, commands):

        time_interval = datetime - self.datetime
        t_interv_in_hours = time_interval.seconds / (60.0 * 60.0)
        self.datetime = datetime

        self.p_out
        if commands.get('storage_mode') != None:
            self.p_out = commands['power_level']
        else:
            pass 

        # verifica se existe comando para a bateria,
        # se não houver continua no estado definido
        # anteriormente
        # if commands.get('storage_mode') != None:
        #     if commands['storage_mode'] == 'charge':
                
        #         if self.storage_energy_level < self.storage_capacity:
        #             energy = self.storage_electrical_power * t_interv_in_hours
        #             self.storage_energy_level += (energy * self.efficiency)
        #             self.storage_state = 'charging'
        #             self.p_out = commands['power_level']
        #         else:
        #             self.p_out = 0.0
        #     elif commands['storage_mode'] == 'discharge':
        #         if self.storage_energy_level > self.storage_minimum_backup:
        #             energy = self.storage_electrical_power * t_interv_in_hours
        #             self.storage_energy_level -= (energy * self.efficiency)
        #             self.storage_state = 'discharging'
        #             self.p_out = commands['power_level']
        #         else:
        #             self.p_out = 0.0
        #     elif commands['storage_mode'] == 'float':
        #         self.storage_state = 'floating'
        #         self.p_out = 0.0
        # else:
        #     if self.storage_state == 'charging':
        #         if self.storage_energy_level < self.storage_capacity:
        #             energy = self.storage_electrical_power * t_interv_in_hours
        #             self.storage_energy_level += (energy * self.efficiency)
        #             self.p_out = commands['power_level']
        #         else:
        #             self.p_out = 0.0

        #     elif self.storage_state == 'floating':
        #         self.p_out = 0.0

        #     elif self.storage_state == 'discharging':
        #         if self.storage_energy_level > self.storage_minimum_backup:
        #             energy = self.storage_electrical_power * t_interv_in_hours
        #             self.storage_energy_level -= (energy * self.efficiency)
        #             self.p_out = commands['power_level']
        #         else:
        #             self.p_out = 0.0

        return float(self.p_out)

    def __repr__(self):
        return 'Storage'


class BufferingDevice(object):

    def __init__(self, datetime, demand):
        self.datetime = datetime
        self.p_out = demand

    def step(self, datetime, commands):
        return self.p_out


class Prosumer(object):
    """Esta classe implementa a lógica de consumo/produção
    de energia para cada passo de tempo de um prosumidor
    utilizando para isso instâncias das demais classes
    deste módulo, tais como Load, Generation e Storage
    """
    def __init__(self, datetime, name, param_dict):
        """
            config is a dictionary like this:
            {
                'stochastic_gen': {
                    'value': value 
                },
                'shiftable_load': {
                    'value' : value
                },
                'buffering_device': {
                    'value': value
                }
                'storage_device': {
                    'value': value
                }
                'freely_control_gen': {
                    'value': value
                }
                'user_action_device': {
                    'value': value
                }
            }
        """
        self.datetime = datetime
        self.name = name
        self.prosumer_id = int(name.split('_')[1])
        self.stochastic_gen = None
        self.shiftable_load = None
        self.buffering_device = None
        self.storage_device = None
        self.freely_control_gen = None
        self.user_action_device = None
        self.p_out = 0.0
        self.demand = 0.0

        # =================================================
        # inicialização dos objetos que representam o
        # comportamento de cada um dos devices com suas
        # condições pré-estabelecidas
        # =================================================

        self.prosumer_entity_data = {
            'eid': self.name,
            'type': 'Prosumer',
            'rel': [],
            'children': [],
        }

        # TODO: set the params values in config.json and set them in devices objects

        for device_name, device_params in param_dict.items():
            if device_name == 'stochastic_gen':
                self.stochastic_gen = PVGeneration(datetime=datetime,
                                                   max_gen_value=device_params['size'],
                                                   gen_id=self.prosumer_id)

                child = {
                    'eid': '{}:stochastic_gen'.format(self.name),
                    'type': 'PVGeneration',
                }
                self.prosumer_entity_data['children'].append(child)

            elif device_name == 'shiftable_load':
                start_datetime = datetime + dt.timedelta(hours=int(uniform(5, 22)))

                loads = random_shiftable_load_generator(qtd=randint(1, 5),
                                                        demand_range=(0.5, 1.2),
                                                        frequency_range=(1, 5),
                                                        cycles_range=(2, 6))

                schedules = random_schedule_load_generator(loads, datetime)

                self.shiftable_load = ShiftableLoad(datetime=datetime,
                                                    loads=loads)
                self.shiftable_load.set_schedule(schedules)

                child = {
                    'eid': '{}:shiftable_load'.format(self.name),
                    'type': 'ShiftableLoad',
                }
                self.prosumer_entity_data['children'].append(child)

            elif device_name == 'buffering_device':
                self.buffering_device = BufferingDevice(datetime=datetime,
                                                        demand=device_params['size'])
                child = {
                    'eid': '{}:buffering_device'.format(self.name),
                    'type': 'BufferingDevice',
                }
                self.prosumer_entity_data['children'].append(child)

            elif device_name == 'storage_device':

                storage_size = device_params['size']

                self.storage_device = Storage(datetime=datetime,
                                              storage_electrical_rate=0.05,
                                              storage_capacity=2.0)
                child = {
                    'eid': '{}:storage_device'.format(self.name),
                    'type': 'Storage',
                }
                self.prosumer_entity_data['children'].append(child)

            elif device_name == 'freely_control_gen':

                gen_el_power = device_params['size']

                self.freely_control_gen = DieselGeneration(datetime=datetime,
                                                           fuel_price=1.2 * 1e3,
                                                           generator_fuel_rate=2933e3,
                                                           generator_electrical_power=gen_el_power,
                                                           maintenance_cost_rate=0.5,
                                                           add_startup_maintenance_cost=0.1,
                                                           add_startup_fuel_use=0.001)
                child = {
                    'eid': '{}:freely_control_gen'.format(self.name),
                    'type': 'DieselGeneration',
                }
                self.prosumer_entity_data['children'].append(child)

            elif device_name == 'user_action_device':
                self.user_action_device = UserLoad(datetime=datetime,
                                                   max_dem_value=device_params['size'],
                                                   load_id=self.prosumer_id)
                child = {
                    'eid': '{}:user_action_device'.format(self.name),
                    'type': 'UserLoad',
                }
                self.prosumer_entity_data['children'].append(child)

    def step(self, datetime, input_):
        """
        """

        time_interval = datetime - self.datetime
        t_interv_in_hours = time_interval.seconds / (60.0 * 60.0)

        self.datetime = datetime
        self.p_out = 0.0
        # =================================================
        # Realiza cálculo de demanda (+/-) de cada um dos
        # dispositivos.
        #
        # Também realiza ajustes nas configurações dos
        # dispositivos de acordo com os comandos enviados
        # pelo agente device.
        # =================================================
        if self.stochastic_gen is not None:
            if input_:
                power = self.stochastic_gen.step(datetime, input_['stochastic_gen'])
            else:
                power = self.stochastic_gen.step(datetime, {})
            self.p_out += power
        if self.user_action_device is not None:
            if input_:
                power = self.user_action_device.step(datetime, input_['user_action_device'])
            else:
                power = self.user_action_device.step(datetime, {})
            self.p_out += power
        if self.freely_control_gen is not None:
            if input_:
                power = self.freely_control_gen.step(datetime, input_['freely_control_gen'])
            else:
                power = self.freely_control_gen.step(datetime, {})
            # self.p_out += power
        if self.storage_device is not None:
            if input_:
                power = self.storage_device.step(datetime, input_['storage_device'])
            else:
                power = self.storage_device.step(datetime, {'power_level': 0.0})
            self.p_out += power
        if self.shiftable_load is not None:
            if input_:
                power = self.shiftable_load.step(datetime, input_['shiftable_load'])
            else:
                power = self.shiftable_load.step(datetime, {})
            # self.p_out += power
        if self.buffering_device is not None:
            if input_:
                power = self.buffering_device.step(datetime, input_['buffering_device'])
            else:
                power = self.buffering_device.step(datetime, {})
            # self.p_out += power

        self.p_out = round(self.p_out, 4)

    def __repr__(self):
        return 'Prosumer: {}'.format(self.name)


class Simulator(object):
    """Esta classe cria instâncias da classe
    Prosumer e faz a chamada de seu método step
    para cada passo de tempo de simulação.
    """
    def __init__(self, start_datetime):
        """
            self.prosumers: It's a dictionary with all prosumers created according with parameters
            in passed in add_prosumers method.
            sel.data: 
            self.start_datetime: A datetime object made with a string with the start date 
                in the format dd/mm/YYYY - hh:mm:ss  
        """
        self.prosumers = dict()
        self.start_datetime = dt.datetime.strptime(start_datetime, '%d/%m/%Y - %H:%M:%S')

    def add_prosumers(self, config_dict):
        """Inits the prosumers

        This method initiate the prosumers getting as input arg a dictionary with
        the following format:
        
            {
            '1': {
                'stochastic_gen': param_dict,
                'shiftable_load': param_dict
                 ....
                 }
            '2': {
                'stochastic_gen': param_dict,
                'shiftable_load': param_dict,
                 ....
                 }
            ....
            }
        """

        #

        entity_list = []
        for node, param_dict in config_dict.items():
            name = 'Prosumer_{}'.format(node)
            """ To inicialize the Prosumer class it's necessary
             a dictionary in this format:
                {
                    'stochastic_gen': {'value': value },
                    'shiftable_load': {'value' : value},
                    ...
                }
            """
            prosumer = Prosumer(self.start_datetime, name, param_dict)
            self.prosumers[name] = prosumer
            entity_list.append(prosumer.prosumer_entity_data)

        return entity_list

    def step(self, time, inputs):
        """
        """

        delta = dt.timedelta(0, time)
        datetime = self.start_datetime + delta
        for prosumer_name, prosumer in self.prosumers.items():
            _inputs = {}
            for dest_eid, attrs in inputs.items():
                if prosumer_name in dest_eid:
                    try:
                        prosumer_eid, device_name = dest_eid.split(':')
                        _inputs[device_name] = list(attrs['commands'].values())[0]
                    except ValueError:
                        pass
            prosumer.step(datetime, _inputs)


def main():
    """This is a test method.

    This method aims to test some functionalities in
    the classes defined in this module.
    """
    # -------------------------------------------
    # Carrega as configurações de simulação
    # e inicializa os prosumers e seus devices
    # -------------------------------------------

    start = '01/10/2019 - 00:00:00'
    sim = Simulator(start_datetime=start)

    # carrega o arquivo de configuracao config.json
    # e monta o dicionario com os parametros de cada
    # um dos prosumers
    config_file = json.load(open('config.json'))
    # Cria dicionario da seguinte forma:
    """{
        '1': {
            'stochastic_gen': {'value': 2.1},
            'shiftable_load': {'value': 1.2},
             ....
             }
        '2': {
            'stochastic_gen': {'value': 2.1},
            'shiftable_load': {'value': 1.2},
             ....
             }
        ....
        }
    """
    config_dict = {str(i): {} for i in config_file['nodes_lv']}
    for i, j in config_file['devices'].items():
        for k, w in j['powers'].items():
            config_dict[k][i] = {'value': w}

    sim.add_prosumers(config_dict)

    # -------------------------------------------
    # Configura e executa o Loop de passos
    # de simulação
    # -------------------------------------------

    # parametros de tempo de simulação e de passo de tempo
    time = 5 * 24 * 60 * 60  # 5 dias
    time_step = 15 * 60  # 15 minutos
    delta = dt.timedelta(minutes=15)
    delta_sec = delta.days * time + delta.seconds

    from tqdm import tqdm
    from time import sleep
    for i in tqdm(range(0, delta_sec, time_step)):
        sleep(0.05)
        sim.step(time=i, inputs={})


if __name__ == '__main__':
    main()
