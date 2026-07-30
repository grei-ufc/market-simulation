"""MyGrid module to:
- load a grid from a json file to mygrid objects.
- set and reset power inputs
- run power flow
"""
__author__ = """Lucas S Melo <lucassmelo@dee.ufc.br>"""

import json
import numpy as np
import random
from mosaik_mygrid.mygrid_tools import create_mygrid_model
from mygrid.power_flow.backward_forward_sweep_3p import calc_power_flow

grid_data = None

def load_case(file):
    global grid_data
    grid_elements, grid_data = create_mygrid_model(file)
    entity_map = dict()

    # ---------------------------------------------------
    # cria o dicionario de entity_map sendo as chaves os
    # nomes das barras, trafos ou linhas e os valores os
    # seus atributos.
    # ---------------------------------------------------

    # create load nodes entries in entity_map dictionary
    for idx, (node_name, node_obj) in enumerate(grid_elements.load_nodes.items()):
        eid = node_name
        if eid == '0':
            entity_map[eid] = {
                'etype': 'RefBus',
                'idx': idx,
                'static': {
                    'vn': abs(node_obj.voltage) / 1e3,
                }
            }
        else:
            entity_map[eid] = {
                'etype': 'PQBus',
                'idx': idx,
                'static': {
                    'vn': abs(node_obj.voltage) / 1e3,
                }
            }

    # create branchs and transformers nodes entries in entity_map dictionary
    for idx, (branch_name, branche_obj) in enumerate(grid_elements.sections.items()):
        eid = branch_name
        if branche_obj.transformer != None:
            entity_map[eid] = {
                'etype': 'Transformer',
                'idx': idx,
                'static': {
                    'power': abs(branche_obj.transformer.power),
                    'vp': abs(branche_obj.transformer.VLL),
                    'vs': abs(branche_obj.transformer.Vll),
                },
                'related':
                    [branche_obj.n1.name, branche_obj.n2.name],
            }
        else:
            entity_map[eid] = {
                'etype': 'Branch',
                'idx': idx,
                'static': {
                    'imax': None,
                    'length': abs(branche_obj.length),
                },
                'related':
                    [branche_obj.n1.name, branche_obj.n2.name],
            }

    return grid_elements, entity_map


def reset_inputs(grid):
    for i, j in grid.load_nodes.items():
        j.pp = np.zeros((3, 1), dtype=complex)
        j.config_voltage(voltage=j.voltage_nom)
        j.ip = np.zeros((3, 1), dtype=complex)


def get_pq(p_kw, pf):
    p_w = round(p_kw/3.0, 3) * 1e3
    s_w = round(p_w / pf, 3)
    q_w = round(s_w * np.sin(np.arccos(pf)), 3)
    return p_w + 1j * q_w


def set_inputs(grid, inputs):
    pf = 0.9  # power factor
    for i, k in inputs.items():
        # i: nome do no
        # k: array de potencias associada ao no em kW
        grid.load_nodes[i].config_load(ppa=get_pq(k[0], pf),
                                       ppb=get_pq(k[1], pf),
                                       ppc=get_pq(k[2], pf))
    # for name, node in grid.load_nodes.items():
    #     print((name, node.pp))


def run_power_flow(grid, datetime):
    global grid_data

    f0 = grid.dist_grids['F0']
    calc_power_flow(f0)

    for name, node in grid.load_nodes.items():
        grid_data[name]['voltage'] = (
            abs(node.vp[0, 0]),
            abs(node.vp[1, 0]),
            abs(node.vp[2, 0])
        )

        grid_data[name]['power'] = (
            node.pp[0, 0].real,
            node.pp[1, 0].real,
            node.pp[2, 0].real
        )

    for name, section in grid.sections.items():
        p1 = int(f0.load_nodes_tree.rnp_dict()[section.n1.name])
        p2 = int(f0.load_nodes_tree.rnp_dict()[section.n2.name])

        if p1 > p2:
            node = section.n2
        else:
            node = section.n1

        grid_data[name]['current'] = (
            abs(node.ip[0, 0]),
            abs(node.ip[1, 0]),
            abs(node.ip[2, 0])
        )

    return grid_data


def main():
    grid = create_mygrid_model(open('force.json', 'r'))
    reset_inputs(grid)


if __name__ == '__main__':
    main()
