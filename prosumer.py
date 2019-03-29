r"""Este arquivo contém as classes que implementam os comportamentos
fundamentais dos principais componentes elétricos de uma unidade
consumidora/produtora de energia, tais como:
- Load;
- Generation;
- Storage;
- Prosumer.
"""

from random import uniform
import datetime as dt
import json
import enlopy as el
import numpy as np

def generate_timeseries(start, time, step):
    '''
        start = string em formato datetime: dd/mm/YYYY - hh:mm:ss
        time = tamanho da série temporal em segundos
        step = step de tempo em minutos
    '''
    time_step = step * 60 # seconds
    dt_start = dt.datetime.strptime(start, '%d/%m/%Y - %H:%M:%S')
    delta = dt.timedelta(0, time)

    delta_sec = delta.days * (24 * 60 * 60) + delta.seconds

    res = [dt_start + dt.timedelta(0, t) for t in range(0, delta_sec, time_step)]
    # res_pp = [i.strftime('%D - %T') for i in res]
    return res

class ShiftableLoad(object):

    OFF = 0
    ON = 1

    def __init__(self, datetime, start_datetime, demand, time_delta):
        '''
            datetime = string em formato datetime: dd/mm/YYYY - hh:mm:ss
            start_time = string em formato datetime: dd/mm/YYYY - hh:mm:ss
            demand = valor de demanda da carga em kva
            time_in_hours = time delta de tempo de execução da carga

            ======= Script de Testes ================
            datetimes = generate_timeseries('24/09/2018 - 00:00:00', 72*60*60, 5)
            sl1 = ShiftableLoad('24/09/2018 - 00:00:00', '24/09/2018 - 10:00:00', 2.0, dt.timedelta(hours=0.5))
            for datetime in datetimes:
                sl1.step(datetime)
        '''
        self.datetime = datetime
        self.start_datetime = start_datetime
        self.demand = demand
        self.time_delta = time_delta
        self.status = self.OFF
        self.executed_today = False
        self.time_left_in_sec = self.time_delta.seconds


    def step(self, datetime, commands):
        demand = 0.0
        delta_in_hours = 0.0

        if self.status == self.OFF:
            if datetime >= self.start_datetime and not self.executed_today:
                self.status = self.ON
            else:
                if datetime.day == self.start_datetime.day and self.executed_today:
                    self.executed_today = False
                    self.time_left_in_sec = self.time_delta.seconds

        if self.status == self.ON:
            demand = self.demand

            self.delta = datetime - self.datetime
            if self.delta.seconds <= self.time_left_in_sec:
                self.time_left_in_sec -= self.delta.seconds
                delta_in_hours = self.delta.seconds / (60.0 * 60.0)
            else:
                delta_in_hours = self.time_left_in_sec / (60.0 * 60.0)
                self.time_left_in_sec = 0
                self.executed_today = True
                self.start_datetime += dt.timedelta(hours=24)
                self.status = self.OFF
            
        self.demand = round(demand, 2)
        self.energy = round(self.demand * delta_in_hours, 2)
        # energy = self.demand * (exec_time / (60.0 * 60.0))
        
        if demand != 0.0:
            print('Load Executed: {:.2f} in {}'.format(energy, demand))
        
        return self.demand, 0.0


class UserLoad(object):
    """Representa uma classe que a cada passo
    de tempo retorna a demanda média de energia 
    para um determinado período de tempo.
    """
    def __init__(self, datetime, user_daily_energy):

        self.demand = 0.0
        self.datetime = datetime

        # definição da curva de carga do consumidor
        self.load_curve = el.gen_daily_stoch_el(user_daily_energy)

    def step(self, datetime, commands):
        '''
        '''
        time_delta = datetime - self.datetime
        delta_in_hours = time_delta.seconds / (60.0 * 60.0)

        self.datetime = datetime
        self.demand = np.interp(datetime.hour + datetime.minute / 60.0,
                                np.arange(24),
                                self.load_curve)
        self.energy = round(self.demand * delta_in_hours, 2)
        
        return self.demand, self.forecast(datetime)

    def forecast(self, datetime):
        datetime_list = [datetime + dt.timedelta(0, 15.0 * 60.0 + i * 60.0) for i in range(1, 16)]
        hours = [round(i.hour + i.minute / 60.0, 2) for i in datetime_list]
        self.demand_forecast = np.mean(np.interp(hours, np.arange(24), self.load_curve))
        self.energy_forecast = round(self.demand_forecast * 15.0 / 60.0, 2)
        return self.demand_forecast

    def __repr__(self):
        return 'Load'


class DieselGeneration(object):
    '''
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

        Script de Teste
        ---------------
        
        import datetime as dt
        import random
        from prosumer import generate_timeseries

        dt_start = dt.datetime.strptime('28/02/2019 - 00:00:00', '%d/%m/%Y - %H:%M:%S')
        dg1 = DieselGeneration(dt_start,
                               fuel_price=1.2*1e3,
                               generator_fuel_rate=2933e3,
                               generator_electrical_power=5.5e3,
                               maintenance_cost_rate=0.5,
                               add_startup_maintenance_cost=0.1,
                               add_startup_fuel_use=0.001)
                               
        for t in generate_timeseries(start='28/02/2019 - 00:15:00', time=10*60*60, step=15):
            status = random.choice([True, False])
            marginal_cost = dg1.step(datetime=t, commands={'on_off': status})
            if status:
                print('gerador ligado')
            else:
                print('gerador desligado')    
            print('US$ {}'.format(marginal_cost))
    '''
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
        
        if commands.get('on_off') is not None:
            self.on_off = commands['on_off']
        
        # =================================================
        # cálculo do custo marginal do gerador diesel
        # para o intervalo de 15min na próxima negociação
        # =================================================
        marg_cost = self.calc_marginal_cost(0.25, self.on_off)
        self.datetime = datetime
        

        if self.on_off is True:
            return self.generator_electrical_power, marg_cost
        elif self.on_off is not True:
            return 0.0, marg_cost


class PVGeneration(object):
    """Representa uma classe que a cada passo
    de tempo retorna a produção média de energia 
    para um determinado período de tempo.
    """
    def __init__(self, datetime, demand):
        self.demand = demand
        self.datetime = datetime

    def step(self, datetime, commands):
        delta_de_tempo = datetime - self.datetime
        delta_em_horas = delta_de_tempo.seconds / (60.0 * 60.0)
        self.datetime = datetime

        if datetime.hour >= 18 or datetime.hour < 6:
            self.demand = 0.0
        else:
            self.demand = round(uniform(0.2, 1.2), 3)
        
        self.energy = round(self.demand * delta_em_horas, 3)
        
        return - self.demand, - self.forecast(datetime)

    def forecast(self, datetime):
        if datetime.hour >= 18 or datetime.hour < 7:
            self.power_forecast = 0.0
        else:
            self.power_forecast = round(uniform(0.2, 1.2), 3)

        self.energy = round(self.power_forecast * 15.0 / 60.0, 3)
        
        return self.power_forecast

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


    Script de Teste
    ---------------

    import datetime as dt
    import random
    from prosumer import generate_timeseries
    dt_start = dt.datetime.strptime('28/02/2019 - 00:00:00', '%d/%m/%Y - %H:%M:%S')
    sd1 = Storage(dt_start,
                  storage_electrical_power=2.0e3,
                  storage_capacity=30e3)

    for t in generate_timeseries(start='28/02/2019 - 00:15:00', time=10*60*60, step=15):
        commands= random.choice([{'energy_price': random.uniform(1.0, 3.0)}, {}])
        power = sd1.step(datetime=t, commands=commands)
        print('power delivered {} storage level: {}'.format(power, sd1.storage_charge_qtd))

    """

    def __init__(self,
                 datetime,
                 storage_electrical_power,
                 storage_capacity):
        
        self.storage_capacity = storage_capacity# in wh
        self.storage_charge_qtd = 0.4 * storage_capacity # in wh
        self.storage_minimum_backup = 0.2 * storage_capacity
        self.storage_state = 'loading' # can be loading, unloading or waiting
        self.storage_electrical_power = storage_electrical_power # in Watts
        self.storage_charge_discharge_time = storage_capacity / storage_electrical_power # in hours
        self.price_history_vector = list()
        self.max_buy_price = None # in US$ 
        self.min_sell_price = None # in US$
        self.datetime = datetime

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

    def step(self, datetime, commands):

        delta_de_tempo = datetime - self.datetime
        delta_em_horas = delta_de_tempo.seconds / (60.0 * 60.0)
        self.datetime = datetime

        prices = tuple([self.max_buy_price, self.min_sell_price])

        # verifica se existe comando de preço, se não houver,
        # continua no estado definido anteriormente
        if commands.get('energy_price') is not None:

            self.price_history_vector.append(commands['energy_price'])
            self.calc_min_sell_and_max_buy_prices()

            if commands['energy_price'] < self.max_buy_price:
                # compra energia
                self.calc_min_sell_and_max_buy_prices()
                if self.storage_charge_qtd < self.storage_capacity:
                    energy_buyed = self.storage_electrical_power * delta_em_horas
                    self.storage_charge_qtd += energy_buyed
                    self.storage_state = 'loading'

                    return self.storage_electrical_power, prices
                else:
                    return 0.0, prices

            elif commands['energy_price'] > self.max_buy_price and commands['energy_price'] < self.min_sell_price:
                # bateria em estado de espera
                self.calc_min_sell_and_max_buy_prices()
                self.storage_state = 'waiting'
                return 0.0, prices

            elif commands['energy_price'] > self.min_sell_price:
                # vende energia
                self.calc_min_sell_and_max_buy_prices()
                if self.storage_charge_qtd > self.storage_minimum_backup:
                    energy_selled = self.storage_electrical_power * delta_em_horas
                    self.storage_charge_qtd -= energy_selled
                    self.storage_state = 'unloading'
                    return - self.storage_electrical_power, prices
                else:
                    return 0.0, prices
        else:
            if self.storage_state == 'loading':
                # compra energia
                if self.storage_charge_qtd < self.storage_capacity:
                    energy_buyed = self.storage_electrical_power * delta_em_horas
                    self.storage_charge_qtd += energy_buyed
                    return self.storage_electrical_power, prices
                else:
                    return 0.0, prices

            elif self.storage_state == 'waiting':
                # bateria em estado de espera
                return 0.0, prices

            elif self.storage_state == 'unloading':
                # vende energia
                if self.storage_charge_qtd > self.storage_minimum_backup:
                    energy_selled = self.storage_electrical_power * delta_em_horas
                    self.storage_charge_qtd -= energy_selled
                    return - self.storage_electrical_power, prices
                else:
                    return 0.0, prices

    def __repr__(self):
        return 'Storage'


class BufferingDevice(object):

    def __init__(self, datetime, demand):
        self.datetime = datetime
        self.demand = demand

    def step(self, datetime, commands):
        return 0.0, 0.0


class Prosumer(object):
    """Esta classe implementa a lógica de consumo/produção
    de energia para cada passo de tempo de um prosumidor
    utilizando para isso instâncias das demais classes
    deste módulo, tais como Load, Generation e Storage
    """
    def __init__(self, datetime, name, config):
        '''
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
                'freely_control_gem': {
                    'value': value
                }
                'user_action_device': {
                    'value': value
                }
            }
        '''
        self.datetime = datetime
        self.name = name
        self.prosumer_id = int(name.split('_')[1])
        self.stochastic_gen = None
        self.shiftable_load = None
        self.buffering_device = None
        self.storage_device = None
        self.freely_control_gem = None
        self.user_action_device = None


        # =================================================
        # inicialização dos objetos que representam o
        # comportamento de cada um dos devices com suas
        # condições pré-estabelecidas
        # =================================================

        self.device_status = dict()
        for device_name, device_values in config.items():
            if device_name == 'stochastic_gen':
                self.stochastic_gen = PVGeneration(datetime=datetime,
                                                   demand=device_values['value'])
                self.device_status['stochastic_gen'] = {'status': 1,
                                                        'power': 0.0}

            elif device_name == 'shiftable_load':
                start_datetime = datetime + dt.timedelta(hours=int(uniform(5, 22)))
                self.shiftable_load = ShiftableLoad(datetime=datetime,
                                                    start_datetime=start_datetime,
                                                    demand=device_values['value'],
                                                    time_delta=dt.timedelta(hours=0.5))
                self.device_status['shiftable_load'] = {'status': 0,
                                                        'power': 0.0}

            elif device_name == 'buffering_device':
                self.buffering_device = BufferingDevice(datetime=datetime,
                                                        demand=device_values['value'])
                self.device_status['buffering_device'] = {'status': 0,
                                                          'power': 0.0}

            elif device_name == 'storage_device':
                
                storage_el_power = device_values['value']
                
                self.storage_device = Storage(datetime=datetime,
                                              storage_electrical_power=storage_el_power,
                                              storage_capacity=30e3)
                self.device_status['storage_device'] = {'status': 0,
                                                        'power': 0.0}

            elif device_name == 'freely_control_gem':

                gen_el_power = device_values['value']
                
                self.freely_control_gem = DieselGeneration(datetime=datetime,
                                                           fuel_price=1.2*1e3,
                                                           generator_fuel_rate=2933e3,
                                                           generator_electrical_power=gen_el_power,
                                                           maintenance_cost_rate=0.5,
                                                           add_startup_maintenance_cost=0.1,
                                                           add_startup_fuel_use=0.001)
                self.device_status['freely_control_gem'] = {'status': 0,
                                                            'power': 0.0}

            elif device_name == 'user_action_device':
                self.user_action_device = UserLoad(datetime=datetime,
                                                   user_daily_energy=device_values['value'])
                self.device_status['user_action_device'] = {'status': 1,
                                                            'power': 0.0}

        # mosaik simulation controller params
        self.demand = 0.0
        self.power_forecast = 0.0

    def step(self, datetime, input_):
        '''
        {
            'commands': {
                'ProsumerAgent_4': {
                    'stochastic_gen': {'power': 5.41, 'status': None, 'demand': None},
                    'shiftable_load': {'power': 2.02, 'status': None, 'demand': None},
                    'buffering_device': {'power': 2.1, 'status': None, 'demand': None},
                    'user_action_device': {'power': 5.55, 'status': None, 'demand': None}
                }.
            }
        }
        '''

        delta_de_tempo = datetime - self.datetime
        delta_em_horas = delta_de_tempo.seconds / (60.0 * 60.0)

        self.datetime = datetime
        self.demand = 0.0
        self.forecast = 0.0

        # =================================================
        # realiza previsão de demanda (+/-) de cada um dos
        # dispositivos não controláveis e calcula outros
        # parâmetros importantes de dispositivos controlá-
        # veis para formãção de suas curvas de oferta.
        #
        # Também realiza ajustes nas configurações dos
        # dispositivos de acordo com os comandos enviados
        # pelo agente device.
        # =================================================
        if not input_:
            return

        commands = input_['commands']['ProsumerAgent_' + str(self.prosumer_id)]
        # ok
        if self.stochastic_gen is not None:
            d, f = self.stochastic_gen.step(datetime, commands['stochastic_gen'])
            self.device_status['stochastic_gen']['power'] = d
            self.device_status['stochastic_gen']['forecast'] = f
            # self.demand += d
            # self.forecast += f
        # ok
        if self.user_action_device is not None:
            d, f = self.user_action_device.step(datetime, commands['user_action_device'])
            self.device_status['user_action_device']['power'] = d
            self.device_status['user_action_device']['forecast'] = f
            # self.demand += d
            # self.forecast += f
        # the output it's the marginal cost and the power delivered
        if self.freely_control_gem is not None:
            power, marginal_cost = self.freely_control_gem.step(datetime, commands['freely_control_gem'])
            self.device_status['freely_control_gem']['power'] = d
            self.device_status['freely_control_gem']['marginal_cost'] = marginal_cost
            # self.demand += d
            # self.forecast += f
        # informar autonomia
        if self.storage_device is not None:
            power, prices = self.storage_device.step(datetime, commands['storage_device'])
            self.device_status['storage_device']['power'] = d
            self.device_status['storage_device']['prices'] = prices
            # self.demand += d
            # self.forecast += f
        # informar ciclos de carga executados e pendentes
        if self.shiftable_load is not None:
            d, f = self.shiftable_load.step(datetime, commands['shiftable_load'])
            self.device_status['shiftable_load']['power'] = d
            self.device_status['shiftable_load']['forecast'] = f
            # self.demand += d
            # self.forecast += f
        # not defined
        if self.buffering_device is not None:
            d, f = self.buffering_device.step(datetime, commands['buffering_device'])
            self.device_status['buffering_device']['power'] = d
            self.device_status['buffering_device']['forecast'] = f
            # self.demand += d
            # self.forecast += f

    def forecast(self, datetime):
        self.load.forecast(datetime)
        if self.has_der:
            self.generation.forecast(datetime)
            self.power_forecast = self.load.demand_forecast - self.generation.power_forecast
        else:
            self.power_forecast = self.load.demand_forecast


    def __repr__(self):
        return 'Prosumer: {}'.format(self.name)


class Simulator(object):
    """Esta classe cria instâncias da classe
    Prosumer e faz a chamada de seu método step
    para cada passo de tempo de simulação.
    """
    def __init__(self, start_datetime):
        self.prosumers = dict()
        self.data = list()
        self.start_datetime = dt.datetime.strptime(start_datetime, '%d/%m/%Y - %H:%M:%S')

    def add_prosumers(self, configs):
        for node, config in configs.items():
            name = 'Prosumer_{}'.format(node)
            prosumer = Prosumer(self.start_datetime, name, config)
            self.prosumers[name] = prosumer
            self.data.append([])

    def step(self, time, inputs):

        '''The inputs dictionary has the folowing form:
            {'Prosumer_4': {
                'commands': {
                    'ProsumerAgent_4': {
                        'stochastic_gen': {'power': 5.41, 'status': None, 'demand': None},
                        'shiftable_load': {'power': 2.02, 'status': None, 'demand': None},
                        'buffering_device': {'power': 2.1, 'status': None, 'demand': None},
                        'user_action_device': {'power': 5.55, 'status': None, 'demand': None}
                    }
                }
            },
            'Prosumer_6': {
                'commands': {
                    'ProsumerAgent_6': {
                        'shiftable_load': {'power': 0.03, 'status': None, 'demand': None},
                        'buffering_device': {'power': 2.41, 'status': None, 'demand': None},
                        'user_action_device': {'power': 1.82, 'status': None, 'demand': None}
                    }
                }
            },
            ...
        }
        '''

        delta = dt.timedelta(0, time)
        datetime = self.start_datetime + delta
        for prosumer_name, prosumer in self.prosumers.items():
            prosumer.step(datetime, inputs.get(prosumer_name))
            
            # ================================
            # PRIORIDADE PARA FIX!
            # ================================

            # data = {'datetime': datetime.strftime('%D - %T'),
            #         'demand': 0.0}
            # self.data[prosumer_name].append(data)


def main():

    start = '14/03/2018 - 00:00:00'
    sim = Simulator(start_datetime=start)
    for i in range(5):
        sim.add_prosumer()

    time_step = 15 * 60 # seconds
    time = 1 * 60 * 60
    delta = dt.timedelta(0, time)
    delta_sec = delta.days * (24 * 60 * 60) + delta.seconds
    
    for i in range(0, delta_sec, time_step):
        sim.step(i)

    for i, inst in enumerate(sim.data):
        print('%d: %s' % (i, inst))


if __name__ == '__main__':
    main()

