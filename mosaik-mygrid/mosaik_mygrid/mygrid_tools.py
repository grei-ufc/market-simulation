# mygrid imports
import json

from mygrid.grid import GridElements, ExternalGrid, Section, LoadNode
from mygrid.grid import Conductor, Switch, TransformerModel, LineModel
from mygrid.util import p2r, r2p


def create_mygrid_model(file):

    data = json.load(file)
    
    vll_mt = p2r(13.8e3, 0.0)
    vll_bt = p2r(380.0, 0.0)
    eg1 = ExternalGrid(name='extern grid 1', vll=vll_mt)

    # switchs
    sw1 = Switch(name='sw_1', state=1)

    # transformers
    t1 = TransformerModel(name="T1",
                          primary_voltage=vll_mt,
                          secondary_voltage=vll_bt,
                          power=225e3,
                          impedance=0.01 + 0.2j)

    phase_conduct = Conductor(id=57)
    neutral_conduct = Conductor(id=44)

    spacing = [0.0 + 29.0j, 2.5 + 29.0j, 7.0 + 29.0j, 4.0 + 25.0j]

    line_model_a = LineModel(loc=spacing,
                             phasing=['a', 'b', 'c', 'n'],
                             conductor=phase_conduct,
                             neutral_conductor=neutral_conduct)

    phase_conduct_bt = Conductor(id=32)
    line_model_b = LineModel(loc=spacing,
                             phasing=['a', 'b', 'c', 'n'],
                             conductor=phase_conduct_bt,
                             neutral_conductor=neutral_conduct)

    nodes = dict()
    for node in data['nodes']:
        p = node['active_power'] * 1e3
        q = node['reactive_power'] * 1e3
        s = p + 1j * q
        if node['voltage_level'] == 'medium voltage':
            node_object = LoadNode(name=str(node['name']),
                                   power=s,
                                   voltage=vll_mt)

            if node['name'] == 0:
                node_object = LoadNode(name=str(node['name']),
                                       power=s,
                                       voltage=vll_mt,
                                       external_grid=eg1)                
        elif node['voltage_level'] == 'low voltage':
            if node['phase'] == 'abc':
                node_object = LoadNode(name=str(node['name']),
                                       power=s,
                                       voltage=vll_bt)
            elif node['phase'] == 'a':
                node_object = LoadNode(name=str(node['name']),
                                       ppa=s,
                                       voltage=vll_bt)
            elif node['phase'] == 'b':
                node_object = LoadNode(name=str(node['name']),
                                       ppb=s,
                                       voltage=vll_bt)
            elif node['phase'] == 'c':
                node_object = LoadNode(name=str(node['name']),
                                       ppc=s,
                                       voltage=vll_bt)
        nodes[node['name']] = node_object

    sections = dict()
    for link in data['links']:
        if link['type'] == 'line':
            if data['nodes'][link['source']]['voltage_level'] == 'medium voltage':
                if link['switch'] != None:
                    sec_object = Section(name=link['name'],
                                         n1=nodes[link['source']],
                                         n2=nodes[link['target']],
                                         line_model=line_model_a,
                                         switch=sw1,
                                         length=link['length'])
                else:
                    sec_object = Section(name=link['name'],
                                         n1=nodes[link['source']],
                                         n2=nodes[link['target']],
                                         line_model=line_model_a,
                                         length=link['length'])
            if data['nodes'][link['source']]['voltage_level'] == 'low voltage':
                sec_object = Section(name=link['name'],
                                     n1=nodes[link['source']],
                                     n2=nodes[link['target']],
                                     line_model=line_model_b,
                                     length=link['length'])
        elif link['type'] == 'transformer':
            sec_object = Section(name=link['name'],
                                  n1=nodes[link['source']],
                                  n2=nodes[link['target']],
                                  transformer=t1)
        sections[link['name']] = sec_object

    grid_elements = GridElements(name='my_grid_elements')

    grid_elements.add_switch([sw1])
    grid_elements.add_load_node(list(nodes.values()))
    grid_elements.add_section(list(sections.values()))
    grid_elements.create_grid()

    # inicializa o dicionario que irá armazenar os dados das simulações
    grid_data = dict()
    for i in nodes.keys():
        grid_data[str(i)] = dict(voltage={}, power={})

    for i in sections.keys():
        grid_data[str(i)] = dict(current={})

    return grid_elements, grid_data
