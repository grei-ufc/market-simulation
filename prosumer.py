"""Este arquivo contém as classes que implementam os comportamentos
fundamentais dos principais componentes elétricos de uma unidade
consumidora/produtora de energia, tais como:
- Load;
- Generation;
- Storage;
- Prosumer.
"""

from random import uniform
import datetime as dt
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
        self.datetime = dt.datetime.strptime(datetime, '%d/%m/%Y - %H:%M:%S')
        self.start_datetime = dt.datetime.strptime(start_datetime, '%d/%m/%Y - %H:%M:%S')
        self.demand = demand
        self.time_delta = time_delta
        self.status = self.OFF
        self.executed_today = False
        self.time_left_in_sec = self.time_delta.seconds


    def step(self, datetime):
        exec_time = 0.0
        if self.status == self.OFF:
            if (datetime >= self.start_datetime) and (not self.executed_today):
                self.status = self.ON
            else:
                if (datetime.day == self.start_datetime.day) and (self.executed_today):
                    self.executed_today = False
                    self.time_left_in_sec = self.time_delta.seconds

        if self.status == self.ON:
            self.delta = datetime - self.datetime
            if self.delta.seconds <= self.time_left_in_sec:
                self.time_left_in_sec -= self.delta.seconds
                exec_time = self.delta.seconds
            else:
                exec_time = self.time_left_in_sec
                self.time_left_in_sec = 0
                self.executed_today = True
                self.start_datetime += dt.timedelta(hours=24)
                self.status = self.OFF
            
        self.datetime = datetime
        energy = self.demand * (exec_time / (60.0 * 60.0))
        
        if energy != 0.0:
            print('Load Executed: {:.2f} in {}'.format(energy, datetime))
        return round(energy, 2)


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
        delta_de_tempo = datetime - self.datetime
        delta_em_horas = delta_de_tempo.seconds / (60.0 * 60.0)

        self.datetime = datetime
        self.demand = np.interp(datetime.hour + datetime.minute / 60.0,
                                np.arange(24),
                                self.load_curve)
        self.energy = round(self.demand * delta_em_horas, 3)
        return self.demand

    def forecast(self, datetime):
        datetime_list = [datetime + dt.timedelta(0, 15.0 * 60.0 + i * 60) for i in range(1, 16)]
        hours = [round(i.hour + i.minute / 60.0, 2) for i in datetime_list]
        self.demand_forecast = np.mean(np.interp(hours, np.arange(24), self.load_curve))
        self.energy_forecast = round(self.demand_forecast * 15.0 / 60.0, 3)
        return self.demand_forecast

    def __repr__(self):
        return 'Load'


class DieselGeneration(object):

    OFF = 0
    ON = 1

    def __init__(self, datetime, power_kva):
        self.datetime = datetime
        self.power_kva = power_kva
        self.status = self.OFF


    def step(self, datetime):
        exec_time = 0.0

        if self.status == self.ON:
            self.delta = datetime - self.datetime
            if self.delta.seconds <= self.time_left_in_sec:
                self.time_left_in_sec -= self.delta.seconds
                exec_time = self.delta.seconds
            else:
                exec_time = self.time_left_in_sec
                self.time_left_in_sec = 0
                self.start_datetime += dt.timedelta(hours=24)
                self.status = self.OFF
            
        self.datetime = datetime
        energy = self.power_kva * (exec_time / (60.0 * 60.0))
        
        if energy != 0.0:
            print('Generation Executed: {:.2f} kVA in {}'.format(energy, datetime))
        return round(energy, 2)


class PVGeneration(object):
    """Representa uma classe que a cada passo
    de tempo retorna a produção média de energia 
    para um determinado período de tempo.
    """
    def __init__(self, datetime, power_kva):
        self.power_kva = power_kva
        self.datetime = datetime

    def step(self, datetime):
        delta_de_tempo = datetime - self.datetime
        delta_em_horas = delta_de_tempo.seconds / (60.0 * 60.0)
        self.datetime = datetime

        if datetime.hour >= 18 or datetime.hour < 6:
            self.power_kva = 0.0
        else:
            self.power_kva = round(uniform(0.2, 1.2), 3)
        
        self.energy = round(self.power_kva * delta_em_horas, 3)
        
        return self.power_kva

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
    """Representa uma classe que a cada passo
    de tempo retorna a quantidade de energia
    consumida/armazenada no sistema de armazenamento
    dependendo do modo de operação loading/unloading.
    """
    LOADING = 1
    UNLOADING = 0

    def __init__(self, datetime, power_kva, max_storage_kwh=10.0):
        self.energy = 0.0
        self.max_storage = max_storage
        self.power_kva = power_kva
        self.state = self.LOADING
        self.datetime = self.datetime

    def step(self, energy):
        self.energy += round(energy, 3)
        excess = 0.0
        if self.energy > self.max_storage:
            self.energy = self.max_storage
            excess = self.max_storage - self.energy
        else:
            pass
        return excess

    def __repr__(self):
        return 'Storage'


class BufferingDevice(object):

    def __init__(self, datetime, power_kva):
        self.datetime = datetime
        self.power_kva = power_kva

    def step(self, datetime):
        pass


class Prosumer(object):
    """Esta classe implementa a lógica de consumo/produção
    de energia para cada passo de tempo de um prosumidor
    utilizando para isso instâncias das demais classes
    deste módulo, tais como Load, Generation e Storage
    """
    def __init__(self, datetime, config):
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
        self.datetime = self.datetime
        self.load = Load(self.datetime)

        self.stochastic_gen = None
        self.shiftable_load = None
        self.buffering_device = None
        self.storage_device = None
        self.freely_control_gem = None
        self.user_action_device = None

        for device_name, device_values in config.items():
            if device_name == 'stochastic_gen':
                self.stochastic_gen = PVGeneration(datetime=datetime,
                                                   power_kva=device_values['value'])
            elif device_name == 'shiftable_load':
                self.shiftable_load = ShiftableLoad(datetime=datetime,
                                                    start_datetime=datetime,
                                                    demand=device_values['value'],
                                                    time_delta=0.5)
            elif device_name == 'buffering_device':
                self.shiftable_load = BufferingDevice(datetime=datetime,
                                                      power_kva=device_values['value'])
            elif device_name == 'storage_device':
                self.storage_device = Storage(datetime=datetime,
                                              power_kva=device_values['value'])
            elif device_name == 'freely_control_gem':
                self.freely_control_gem = DieselGeneration(datetime=datetime,
                                                           power_kva=device_values['value'])
            elif device_name == 'user_action_device':
                self.user_action_device = UserLoad(datetime=datetime,
                                                   user_daily_energy=device_values['value'])

        if self.has_der:
            self.generation = Generation(self.datetime)
            self.storage = Storage(self.datetime)
        else:
            self.generation = None
            self.storage = None

        # mosaik simulation controller params
        self.power_input = 0.0
        self.power_forecast = 0.0
        self.load_demand = 0.0
        self.generation_power = 0.0
        self._storage_energy = 0.0

    def step(self, datetime):

        delta_de_tempo = datetime - self.datetime
        delta_em_horas = delta_de_tempo.seconds / (60.0 * 60.0)

        self.datetime = datetime

        self.load_demand = self.load.step(datetime)

        self.forecast(datetime)

        # verifica se o consumidor tem recursos energéticos distribuídos
        if self.has_der:
            self.generation_power = self.generation.step(datetime)
            self.power_input = 0.0
            self.power_input += self.load.demand - self.generation_power
        else:
            self.power_input = self.load_demand

    def forecast(self, datetime):
        self.load.forecast(datetime)
        if self.has_der:
            self.generation.forecast(datetime)
            self.power_forecast = self.load.demand_forecast - self.generation.power_forecast
        else:
            self.power_forecast = self.load.demand_forecast

    @property
    def storage_energy(self):
        if self.has_der:
            return self.storage.energy
        else:
            return 0.0

    @storage_energy.setter
    def storage_energy(self, value):
        if self.has_der:
            self.storage.energy = value
            self._storage_energy = value
        else:
            pass

    def __repr__(self):
        return 'Prosumer'


class Simulator(object):
    """Esta classe cria instâncias da classe
    Prosumer e faz a chamada de seu método step
    para cada passo de tempo de simulação.
    """
    def __init__(self, start_datetime):
        self.prosumers = []
        self.data = []
        self.start_datetime = dt.datetime.strptime(start_datetime, '%d/%m/%Y - %H:%M:%S')

    def add_prosumer(self, has_der):
        prosumer = Prosumer(self.start_datetime, has_der)
        self.prosumers.append(prosumer)
        self.data.append([])

    def step(self, time, storages=None):
        delta = dt.timedelta(0, time)
        datetime = self.start_datetime + delta

        if storages:
            for idx, storage in storages.items():
                self.prosumers[idx].storage = storage

        for i, prosumer in enumerate(self.prosumers):
            prosumer.step(datetime)
            data = {'datetime': datetime.strftime('%D - %T'),
                    'load_demand': prosumer.load_demand,
                    'generation_power': prosumer.generation_power,
                    'storage_energy': prosumer.storage_energy,
                    'forecast_demand': prosumer.power_forecast}
            self.data[i].append(data)


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

