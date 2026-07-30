r"""Este arquivo contém as classes que implementam os comportamentos
fundamentais dos principais componentes elétricos de uma unidade
consumidora/produtora de energia, tais como:
- Load;
- Generation;
- Storage;
- Prosumer.
"""

from random import uniform, randint, choice, choices
import datetime as dt
import json
import numpy as np
import pandas as pd

from prosumer import Storage, PVGeneration


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


class BESS(object):
    """Esta classe implementa a lógica de consumo/produção
    de energia para cada passo de tempo de um prosumidor
    utilizando para isso instâncias das demais classes
    deste módulo, tais como Load, Generation e Storage
    """
    def __init__(self, datetime, name, config, nodes):
        """
            config is a dictionary like this:
            {
                'stochastic_gen': {
                    'value': value 
                },
                'storage_device': {
                    'value': value
                }
            }
        """
        self.datetime = datetime
        self.name = name
        self.bess_id = int(name.split('_')[1])
        self.storage_devices = dict()
        self.p_out = 0.0
        self.demand = 0.0

        self.bess_entity_data = {
            'eid': self.name,
            'type': 'BESS',
            'rel': [],
            'children': [],
        }

        for n in nodes:
            # =================================================
            # inicialização dos objetos que representam o
            # comportamento de cada um dos devices com suas
            # condições pré-estabelecidas
            # =================================================

            storage_capacity = 10  # uniform(4.0, 100.0) * 1e3

            self.storage_devices['storage{}'.format(n)] = Storage(datetime=datetime,
                                                                  storage_electrical_rate=0.1,
                                                                  storage_capacity=storage_capacity)
            child = {
                'eid': '{}:storage{}'.format(self.name, n),
                'type': 'Storage',
            }
            self.bess_entity_data['children'].append(child)


    def step(self, datetime, inputs_):
        """input_ = 
        {
            'commands': {'BESSAgent_4': {'storage_mode': 'charge'}
        }
        """

        self.datetime = datetime
        self.p_out = 0.0

        for name, s in self.storage_devices.items():
            if inputs_:
                power = s.step(datetime, inputs_[name])
            else:
                power = s.step(datetime, {'power_level': 0.0})
            self.p_out += power

        self.p_out = round(self.p_out, 4)

    def __repr__(self):
        return 'BESS: {}'.format(self.name)


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
        self.bess = dict()
        self.start_datetime = dt.datetime.strptime(start_datetime, '%d/%m/%Y - %H:%M:%S')

    def add_bess(self, grid_dict, bess_dist):
        """Inits the bess

        This method initiate the bess getting as input an dictionary with
        the following format:
        
            {
            '1': [10, 11, 12, 13, 14]
            '2': [16, 17, 18, 19, 20, 21]
            ....
            }

            !!!!!!!!!!!!!!!!
            Ainda não há arquivo de configuração para definir o porte dos
            dispositivos BESS, portanto estes serão escolhidos aleatoriamente
            IMPLEMENTAR: Arquivo de configuração para definição da localização
            e características dos BESS a serem integrados na rede elétrica de BT 
        """

        entity_list = []
        for node, config in grid_dict.items():
            name = 'BESS_{}'.format(node)
            bess = BESS(datetime=self.start_datetime,
                        name=name,
                        config=config,
                        nodes=bess_dist[str(node)])
            self.bess[name] = bess
            entity_list.append(bess.bess_entity_data)
        return entity_list

    def step(self, time, inputs):

        """The inputs dictionary has the folowing form:
            {
            'BESS_4': {
                'commands': {
                    'BESSAgent_4': {'storage_mode': 'charge'}
                }
            },
            'BESS_6': {
                'commands': {
                    'BESSAgent_6': {'storage_mode': 'float'}
                }
            },
            ...
        }
        """
        delta = dt.timedelta(0, time)
        datetime = self.start_datetime + delta

        # for bess_name, bess in self.bess.items():
        #     _input = {}
        #     for dest_eid, attrs in inputs.items():
        #         if bess_name in dest_eid:
        #             _input = list(attrs['commands'].values())[0]
        #     bess.step(datetime, _input)

        for bess_name, bess in self.bess.items():
            _inputs = {}
            for dest_eid, attrs in inputs.items():
                if bess_name in dest_eid:
                    try:
                        bess_eid, device_name = dest_eid.split(':')
                        _inputs[device_name] = list(attrs['commands'].values())[0]
                    except ValueError:
                        pass
            bess.step(datetime, _inputs)

def main():
    """This is a test method.

    This method aims to test some functionalities in
    the classes defined in this module.
    """
    pass


if __name__ == '__main__':
    main()

