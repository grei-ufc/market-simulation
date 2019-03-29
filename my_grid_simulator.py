"""MyGrid module to:
- load a grid from a json file to mygrid objects.
- set and reset power inputs
- run power flow
"""
__author__ = """Lucas S Melo <lucassmelo@dee.ufc.br>"""

import json
import numpy as np
import random

 # mygrid imports
from mygrid.grid import GridElements, ExternalGrid, Section, LoadNode
from mygrid.grid import Conductor, Switch, TransformerModel, LineModel
from mygrid.util import p2r, r2p
from mygrid.power_flow.backward_forward_sweep_3p import calc_power_flow

grid_data = dict()

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
    for i in nodes.keys():
        grid_data[str(i)] = dict(voltage=[], power=[])
    
    for i in sections.keys():
        grid_data[str(i)] = dict(current=[])

    return grid_elements

def reset_inputs(grid):
    
    for i, j in grid.load_nodes.items():
        j.pp = np.zeros((3, 1), dtype=complex)
        j.config_voltage(voltage=j.voltage_nom)
        j.ip = np.zeros((3, 1), dtype=complex)

def set_inputs(grid, inputs):
    pf = 0.9 # power factor
    for i, j in inputs.items():
        # i: nome do no
        # j: potencia associada ao no em kVA
        s = j
        p = round(s * np.cos(np.arccos(pf)), 3) * 1e3
        q = round(s * np.sin(np.arcsin(pf)), 3) * 1e3
        s = p + 1j * q
        grid.load_nodes[i].config_load(power=s)
    
    # for name, node in grid.load_nodes.items():
    #     print((name,node.pp))

def run_power_flow(grid):
    f0 = grid.dist_grids['F0']
    calc_power_flow(f0)

    for name, node in grid.load_nodes.items():
        grid_data[name]['voltage'].append((abs(node.vp[0, 0]), abs(node.vp[1, 0]), abs(node.vp[2, 0])))
        grid_data[name]['power'].append((abs(node.pp[0, 0]), abs(node.pp[1, 0]), abs(node.pp[2, 0])))

    for name, section in grid.sections.items():
        p1 = int(f0.load_nodes_tree.rnp_dict()[section.n1.name])
        p2 = int(f0.load_nodes_tree.rnp_dict()[section.n2.name])

        if p1 > p2:
            node = section.n2
        else:
            node = section.n1

        grid_data[name]['current'].append((abs(node.ip[0, 0]), abs(node.ip[1, 0]), abs(node.ip[2, 0])))

    return grid_data

def main():
    grid = create_mygrid_model(open('force.json', 'r'))
    reset_inputs(grid)

    # simulation of a dictionary with power 
    nodes = list()
    for i, j in grid.load_nodes.items():
        nodes.append({'name': i, 'power': 3.0 * random.random() + 1j * random.random()})
    
    set_inputs(grid, nodes)
    run_power_flow(grid)

if __name__ == '__main__':
    for i in range(10):
        main()
