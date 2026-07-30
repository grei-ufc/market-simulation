"""Integration between MyGrid module 
and the mosaik interface to simulation
"""

import datetime as dt
import json

import mosaik_api
from mosaik_mygrid import model
import numpy as np
# from time import sleep


meta = {
    'models': {
        'Grid': {
            'public': True,
            'any_inputs': True,
            'params': [
                'gridfile'
            ],
            'attrs': [
                'device_status', 'load_nodes',
            ],
        },
        'RefBus': {
            'public': False,
            'params': [],
            'attrs': [
                'ppa',  # potencia complexa da fase a na barra [kVA]
                'ppb',  # potencia complexa da fase b na barra [kVA]
                'ppc',  # potencia complexa da fase c na barra [kVA]
                'vn',  # valor de tensão nominal da barra [kV]
                'vpa',  # tensão complexa na fase a da barra [kV]
                'vpb',  # tensão complexa na fase b da barra [kV]
                'vpc',  # tensão complexa na fase c da barra [kV]
            ],
        },
        'PQBus': {
            'public': False,
            'params': [],
            'attrs': [
                'ppa',  # potencia complexa da fase a na barra [kVA]
                'ppb',  # potencia complexa da fase b na barra [kVA]
                'ppc',  # potencia complexa da fase c na barra [kVA]
                'vn',  # valor de tensão nominal da barra [kV]
                'vpa',  # tensão complexa na fase a da barra [kV]
                'vpb',  # tensão complexa na fase b da barra [kV]
                'vpc',  # tensão complexa na fase c da barra [kV]
            ],
        },
        'Transformer': {
            'public': False,
            'params': [],
            'attrs': [
                'power',    # corrente passante na linha [A]
                'imax',  # limite de corrente máxima suportada pelo transformador [A]
                'vp',    # valor de tensão no primário do transformador [kV]
                'vs',    # valor de tensão no secundário do transformador [kV]

            ],
        },
        'Branch': {
            'public': False,
            'params': [],
            'attrs': [
                'ip',      # corrente passante na linha [A]
                'imax',    # limite de corrente máxima suportada pela linha [A]
                'length',  # Comprimento da linha [km]
            ],
        },
    }
}


class MyGrid(mosaik_api.Simulator):
    def __init__(self):
        super(MyGrid, self).__init__(meta)
        self.step_size = None
        self.start_datetime = None
        self.eid_prefix = None
        self.debug = None

        self.entities = {}
        self.relations = []  # List of pair-wise related entities (IDs)
        self.grids = []  # The MyGrid cases
        self.cache = {}  # Cache for load flow outputs
        self.grid_data = None

    def init(self, sid, step_size, start, eid_prefix, debug=False):
        self.step_size = step_size
        self.start_datetime = dt.datetime.strptime(start, '%d/%m/%Y - %H:%M:%S')
        self.eid_prefix = eid_prefix
        self.debug = debug
        return self.meta

    def create(self, num, modelname, gridfile):
        if modelname != 'Grid':
            raise ValueError('Unknown model: {}'.format(modelname))

        # Processo de criação do modelo da rede elétrica
        # por meio do software MyGrid que gera objetos
        # utilizando os dados contidos no arquivo force.json
        # apontado pela variável gridfile
        # Esse processo de criação está dentro de um laço for
        # mas até aqui só teremos uma entitie para descrição
        # de toda a rede
        grids = []
        for i in range(num):
            eid = '{}{}'.format('Grid_', i)
            grid_elements, entities = model.load_case(gridfile)
            self.grids.append(grid_elements)

            children = []
            for eid, attrs in sorted(entities.items()):
                self.entities[eid] = attrs

                relations = []
                if attrs['etype'] in ['Transformer', 'Branch']:
                    relations = attrs['related']

                children.append({
                    'eid': eid,
                    'type': attrs['etype'],
                    'rel': relations,
                })
            grids.append({
                'eid': 'grid-{}'.format(i),
                'type': 'Grid',
                'rel': [],
                'children': children,
            })

        return grids

    def step(self, time, inputs):

        delta = dt.timedelta(0, time)
        datetime = self.start_datetime + delta

        # if time % (24 * 60 * 60) == 0 and time != 0:
        if True:
            for grid in self.grids:
                model.reset_inputs(grid)

                pp = dict()
                for dest_eid, attrs in inputs.items():
                    pp[dest_eid] = np.zeros(3)
                    print('----')
                    for attr, values in attrs.items():
                        for src_full_id, value in values.items():
                            print('dest_eid: {} src_full_id: {} value: {}'.format(dest_eid, src_full_id, value))
                            if attr == 'ppa':
                                pp[dest_eid][0] += value
                            elif attr == 'ppb':
                                pp[dest_eid][1] += value
                            elif attr == 'ppc':
                                pp[dest_eid][2] += value
                model.reset_inputs(grid)
                model.set_inputs(grid, pp)
                self.grid_data = model.run_power_flow(grid, datetime)

        return time + self.step_size

    def get_data(self, outputs):
        if self.grid_data is None:
            data = {}
            for eid, attrs in outputs.items():
                for attr in attrs:
                    data.setdefault(eid, {})[attr] = 0.0
        else:
            data = {}
            for eid, attrs in outputs.items():
                for attr in attrs:
                    if attr == 'ppa':
                        val = self.grid_data[eid]['power'][0]
                    elif attr == 'ppb':
                        val = self.grid_data[eid]['power'][1]
                    elif attr == 'ppb':
                        val = self.grid_data[eid]['power'][2]
                    elif attr == 'vpa':
                        val = self.grid_data[eid]['voltage'][0]
                    elif attr == 'vpb':
                        val = self.grid_data[eid]['voltage'][1]
                    elif attr == 'vpb':
                        val = self.grid_data[eid]['voltage'][2]
                    else:
                        val = 0.0
                    data.setdefault(eid, {})[attr] = val
        return data

    def finalize(self):
        pass
        # json.dump(self.grid_data, open('grid_data.json','w'))

def main():
    mosaik_api.start_simulation(MyGrid(), 'The mosaik-MyGrid adapter')


if __name__ == '__main__':
    main()
