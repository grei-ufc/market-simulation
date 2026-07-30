import mosaik_api
import prosumer
from time import sleep

META = {
    'models': {
        'Prosumer': {
            'public': True,
            'params': ['config_dict'],
            'attrs': ['demand', 'p_out'],
        },
        'ShiftableLoad': {
            'public': False,
            'params': [],
            'attrs': [
                'p_out',
            ],
        },
        'UserLoad': {
            'public': False,
            'params': [],
            'attrs': [
                'p_out',
            ],
        },
        'DieselGeneration': {
            'public': False,
            'params': [],
            'attrs': [
                'p_out',
            ],
        },
        'PVGeneration': {
            'public': False,
            'params': [],
            'attrs': [
                'p_out',
            ],
        },
        'Storage': {
            'public': False,
            'params': [],
            'attrs': [
                'p_out',
            ],
        },
        'BufferingDevice': {
            'public': False,
            'params': [],
            'attrs': [
                'p_out',
            ],
        },
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
        entities = self.simulator.add_prosumers(config_dict)
        return entities

    def step(self, time, inputs):
        """
        Prosumer simulator step method
        :param time:
        :param inputs:
        :return:
        """
        # for dest_eid, attrs in inputs.items():
        #     attr = attrs.get('commands', {})
        #     print('---> {}: data received from:'.format(dest_eid))
        #     for src_fullid, val in attr.items():
        #         print('    {} --> commands: {}'.format(src_fullid, val))

        self.simulator.step(time, inputs)
        return time + self.step_size

    def get_data(self, outputs):
        data = {}
        val = None
        for eid, attrs in outputs.items():
            try:
                prosumer_eid, device_name = eid.split(':')
            except ValueError:
                prosumer_eid, device_name = eid, None

            for attr in attrs:
                try:
                    if device_name is not None:
                        device_obj = getattr(self.simulator.prosumers[prosumer_eid], device_name)
                        val = getattr(device_obj, attr)
                    else:
                        val = getattr(self.simulator.prosumers[prosumer_eid], attr)
                except KeyError:
                    pass
                finally:
                    data.setdefault(eid, {})[attr] = val
        return data


def main():
    return mosaik_api.start_simulation(ProsumerSim())


if __name__ == '__main__':
    main()
