import mosaik_api
import bess
from time import sleep

META = {
    'models': {
        'BESS': {
            'public': True,
            'params': ['grid_dict', 'bess_dist'],
            'attrs': ['demand', 'p_out'],
        },
        'Storage': {
            'public': False,
            'params': [],
            'attrs': [
                'p_out',
            ],
        },
    }
}


class BESSSim(mosaik_api.Simulator):

    def __init__(self):
        super().__init__(META)
        self.eid_prefix = 'BESS_'
        self.entities = {}

    def init(self, sid, eid_prefix, start, step_size, debug=False):
        self.simulator = bess.Simulator(start)
        self.step_size = step_size
        self.debug = debug
        self.eid_prefix = eid_prefix
        return self.meta

    def create(self, num, model, grid_dict, bess_dist):
        entities = self.simulator.add_bess(grid_dict, bess_dist)
        return entities

    def step(self, time, inputs):
        """
        BESS simulator step method
        :param time:
        :param inputs:
        :return:
        """

        for eid_to, attrs in inputs.items():
            for attr, values in attrs.items():
                if attr == 'commands':
                    for eid_from, device_dict in values.items():
                        pass
                        # print('---------\n>>>eid_from: {}\ncommands: {}'.format(eid_from, device_dict))
        self.simulator.step(time, inputs)

        return time + self.step_size

    def get_data(self, outputs):
        data = {}
        val = None
        for eid, attrs in outputs.items():
            try:
                bess_eid, device_name = eid.split(':')
            except ValueError:
                bess_eid, device_name = eid, None

            for attr in attrs:
                try:
                    if device_name is not None:
                        device_obj = getattr(self.simulator.bess[bess_eid], 'storage_devices')[device_name]
                        val = getattr(device_obj, attr)
                    else:
                        val = getattr(self.simulator.bess[bess_eid], attr)
                except KeyError:
                    pass
                finally:
                    data.setdefault(eid, {})[attr] = val
        return data


def main():
    return mosaik_api.start_simulation(BESSSim())

if __name__ == '__main__':
    main()
