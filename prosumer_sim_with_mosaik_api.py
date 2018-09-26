import mosaik_api
import prosumer

META = {
    'models': {
        'Prosumer': {
            'public': True,
            'params': ['config_dict'],
            'attrs': ['datetime', 'demand'],
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
        self.simulator.step(time)
        return time + self.step_size

    def get_data(self, outputs):
        data = {}
        for eid, attrs in outputs.items():
            model_idx = self.entities[eid]
            data[eid] = {}
            for attr in attrs:
                if attr not in self.meta['models']['Prosumer']['attrs']:
                    raise ValueError('Unknown output attribute: {}'.format(attr))
                data[eid][attr] = getattr(self.simulator.prosumers[model_idx], attr)
        return data


def main():
    return mosaik_api.start_simulation(ProsumerSim())

if __name__ == '__main__':
    main()
