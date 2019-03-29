import mosaik_api
import prosumer
from time import sleep

META = {
    'models': {
        'Prosumer': {
            'public': True,
            'params': ['config_dict'],
            'attrs': ['device_status'],
        }
    }
}


class ProsumerSim(mosaik_api.Simulator):

    def __init__(self):
        super().__init__(META)
        self.eid_prefix = 'Prosumer_'
        self.entities = {}

    def init(self, sid, eid_prefix, start, step_size, debug=False):
        self.simulator = prosumer.Simulator(start)
        self.step_size = step_size
        self.debug = debug
        self.eid_prefix = eid_prefix
        return self.meta

    def create(self, num, model, config_dict):
        '''O parametro prosumers_id é uma tupla em que a posição 0 contém
        o nome do nó considerado e a posição 1 contém um valor booleano
        para indicar ou não a presença de DER no consumidor
        '''
        next_eid = len(self.entities)
        entities = []

        for i, j in zip(range(next_eid, next_eid + num), config_dict):
            eid = '{}{}'.format(self.eid_prefix, j)
            self.entities[eid] = i
            entities.append({'eid': eid, 'type': model})

        self.simulator.add_prosumers(config_dict)
        return entities

    def step(self, time, inputs):
        # for eid, attrs in inputs.items():
        #     for attr, values in attrs.items():
        #         model_idx = self.entities[eid]
        #         storage = [i for i in values.values()][0]  # analisar esse ponto
        #         storages[model_idx] = storage
        
        '''The inputs dictionary has the folowing form:
            {'Prosumer_4': {
                'commands': {
                    'DeviceAgent_4': {
                        'stochastic_gen': {'power': 5.41, 'status': None, 'demand': None},
                        'shiftable_load': {'power': 2.02, 'status': None, 'demand': None},
                        'buffering_device': {'power': 2.1, 'status': None, 'demand': None},
                        'user_action_device': {'power': 5.55, 'status': None, 'demand': None}
                    }
                }
            },
            'Prosumer_6': {
                'commands': {
                    'DeviceAgent_6': {
                        'shiftable_load': {'power': 0.03, 'status': None, 'demand': None},
                        'buffering_device': {'power': 2.41, 'status': None, 'demand': None},
                        'user_action_device': {'power': 1.82, 'status': None, 'demand': None}
                    }
                }
            },
            ...
        }
        '''

        # -----------------------
        # inserido somente para não sobrecarregar os comportamentos
        # do Pade. Quando a dinâmica dos devices ficar mais complexa
        # deve ser retirado para não atrasar a simulação desnecessariamente
        # -----------------------
        if time >= (7 * 24 * 60 * 60): # só é acionado após uma semana de simulação
            sleep(0.1)

        for eid_to, attrs in inputs.items():
            for attr, values in attrs.items():
                if attr == 'commands':
                    for eid_from, device_dict in values.items():
                        pass
                        # print(eid_from)
                        # print(device_dict)
                        # print('---------')
                    # print(eid_to)
                    # print(values)
                    # print(self.simulator.prosumers[eid_to])
                    # print('-------')
        self.simulator.step(time, inputs)
        return time + self.step_size

    def get_data(self, outputs):
        data = {}
        for eid, attrs in outputs.items():
            data[eid] = {}
            for attr in attrs:
                if attr not in self.meta['models']['Prosumer']['attrs']:
                    raise ValueError('Unknown output attribute: {}'.format(attr))
                data[eid][attr] = getattr(self.simulator.prosumers[eid], attr)
        return data


def main():
    return mosaik_api.start_simulation(ProsumerSim())

if __name__ == '__main__':
    main()
