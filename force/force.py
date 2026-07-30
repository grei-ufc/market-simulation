"""This script file generate a random feeder with medium and 
low voltage nodes, write the graph to a networkx graph object
then write the graph to a json file named force.json with some
 grid informations. 

 This file is loaded and used to create 
 mygrid objects and can be used to visualize the grid in a html
 page. For this just open the force.html in a web browser. 
"""

#    Copyright (C) 2018 by
#    Lucas S Melo <lucassmelo@dee.ufc.br>
#    All rights reserved.
#    MIT license.

__author__ = """Lucas S Melo <lucassmelo@dee.ufc.br>"""
import json
import networkx as nx
from networkx.readwrite import json_graph
import random
import numpy as np
from tqdm import tqdm
from terminaltables import AsciiTable

 # mygrid imports
from mygrid.grid import GridElements, ExternalGrid, Section, LoadNode
from mygrid.grid import Conductor, Switch, TransformerModel, LineModel
from mygrid.util import p2r, r2p
from mygrid.power_flow.backward_forward_sweep_3p import calc_power_flow #, calc_power_flow_profiling


def _search_tree(node, stack, prob, max_nodes, visit, tree):
    """Este metodo tem por objetivo gerar uma árvore de grafo
    aleatoria sem utilizar um processo recursivo

    node: no a ser analisado.
    stack: pilha que indica a posicao atual na arvore de grafo.
    prob: probabilidade para criacao de novos nós.
    max_nodes: numero maximo de nós na árvore de grafo.
    visit: nós já visitados.
    tree: dicionário que representa a árvore de grafo, em que
          as chaves representam os nós e os valores são uma lista
          com todos os vizinhos do nó.
    """

    # se o nó atial não foi visitado ele é acrescentado na
    # lista de nós não visitados 
    if node not in visit:
        visit.append(node)
        # se o nó não está presente no dicionário que representa
        # a árvore de grafo ele é acrecentado
        if node not in tree.keys():
            tree[node] = list()

    # verifica se a árvore de grafo já tem a quantidade máxima
    # admissível de nós
    if len(visit) < max_nodes:

        # calcula um número aleatorio e compara a uma probabilidade
        # pré-estabelecida para que um novo nó seja criado.
        # Também limita o numero máximo de arestas de cada nó em 4
        if random.random() < prob and len(tree[node]) < 4:
            stack.append(node)
            new_node = max(visit) + 1
            tree[node].append(new_node)
            tree[new_node] = [node]
            return (new_node, stack, max_nodes, visit, tree)
        # esta condição foi acrescentada para melhorar o espalhamento
        # da verificação nos nós da árvore de grafo
        elif len(tree[node]) == 4:
            new_node = random.sample(tree[node], 1)[0]
            if new_node in stack:
                stack.pop()
            else:
                stack.append(new_node)
            return (new_node, stack, max_nodes, visit, tree)
        # caso não seja gerado um novo nó a partir do nó atual
        # e o número de vizinhos seja maior que 4 então volta-se
        # um nível na pilha do grafo
        else:
            if stack != []:
                new_node = stack.pop()
            else:
                new_node = node
            
            # if new_node not in tree[node]:
            #     tree[node].append(new_node)
            
            # if node not in tree[new_node]:
            #     tree[new_node].append(node)
            return (new_node, stack, max_nodes, visit, tree)
    
    # caso o número máximo de nós estabelecidos para o grafo seja atingido
    # então encerra-se o processo de busca
    elif len(visit) == max_nodes:
        return (new_node, stack, max_nodes, visit, tree)


def generate_tree_graph(node, tree, max_nodes, prob):
    """Este método tem como objetivo realizar as chamadas pelo método
    _serach_tree_n_recursive uma vez que este é resultado de uma adaptação
    do método _search_tree para retirar a recursividade. 
    """
    stack = []
    visit = []
    nodes_count = dict()
    prob_ = prob

    # loço principal, realiza as chamadas ao método _search_tree
    # enquanto o número de nós da árvore gerada for inferior ao número máximo
    # pré-estabelecido.
    while len(tree.keys()) < max_nodes:
        data = _search_tree(node, stack, prob_, max_nodes, visit, tree)
        node = data[0]
        stack = data[1]
        max_nodes = data[2]
        visit = data[3]
        tree = data[4]

        # lógica para atualizacao do valor de probabilidade
        # esta lógica é realizada para impedir que o estabelecimento
        # de uma probabilidade muito baixa cause demora no processo
        # de busca para gerar a árvore de grafo.
        
        # adiciona o nó atual no dicionário de verificação
        if node not in nodes_count.keys():
            nodes_count[node] = 0
        # caso o nó seja reincidente, acrescenta-se 1 à contagem
        else:
            nodes_count[node] += 1

        # loop para verificação de incidencias
        for i, j in nodes_count.items():
            # caso o nó tenha uma incidencia de 20
            # a probabilidade de geração é aumentada
            if j >= 20:
                nodes_count[i] = 0
                prob_ += 0.02
                if prob_ >= 1:
                    prob_ = prob
                break

    return tree


def generate_grid(nodes_mv):
    """Este método tem por objetivo montar a árvore de grafo que irá
    representar a rede elétrica de média e de baixa tensão, neste método
    é chamado o método generate_tree_graph para gerar o alimentador de média
    e também cada um de seus dos ramos de baixa tensão, de acordo com o
    parâmetro nodes_mv.

    Neste método também é gerado um objeto graph do módulo python de análise
    de grafos nxnetwork e a partir dele armazenado criado um dicionário com
    outras especificações para que possa ser escrito o arquivo force.json com
    todos os detalhes necessários para montagem da rede elétrica com o módulo
    My_Grid.
    """

    # -------------------------------------
    # gera o grafo da rede de média tensão
    # -------------------------------------
    prob_ = 0.6
    max_nodes_ = nodes_mv
    tree_ = {0: [1], 1: [0, 2], 2: [1]}
    t = generate_tree_graph(node=2, tree=tree_, max_nodes=max_nodes_, prob=prob_)
    graph = nx.Graph()
    graph.add_nodes_from(t.keys())
    for i, j in t.items():
        for k in j:
            graph.add_edge(i, k)

    # --------------------------------------------------
    # gera os grafos dos ramais da rede de baixa tensão
    # --------------------------------------------------
    # lv_grids armazena em estrut. de dict. a topologia da rede
    # keys: medium voltages nodes - values: list with low voltages nodes
    lv_grids = {}  # armazena os nos de baixa tensao ligados a cada no de media tensao da rede
    start_node = nodes_mv

    # quantidade de consumidores conectados a um transformador
    # de distribuição
    
    nodes_qtd_list = [8, 12, 20]
    # nodes_qtd_list = [4, 6, 8]

    for medium_voltage_node in tqdm(range(2, nodes_mv)):
        prob_ = 0.6
        max_nodes_ = random.choice(nodes_qtd_list)
        branch = generate_tree_graph(node=start_node, tree=dict(), max_nodes=max_nodes_, prob=prob_)
        graph.add_nodes_from(branch.keys())
        graph.add_edge(medium_voltage_node, start_node)

        for i, j in branch.items():
            for k in j:
                graph.add_edge(i, k)

        lv_grids[medium_voltage_node] = list(branch.keys())
        
        start_node += max_nodes_

    # acréscimo ao dicionário json para indicar nos nós o seu 
    # nome, nível de tensão, cor para representação gráfica 
    # e potências ativas e reativas.
    pf = 0.9 # power factor
    for k, n in enumerate(graph):
        graph.node[n]['name'] = n
        if n >= nodes_mv:

            mv_node = [mv for mv, lv in lv_grids.items() if n in lv][0]

            graph.node[n]['color'] = 'rgb(255, 127, 14)'
            graph.node[n]['voltage_level'] = 'low voltage'
            graph.node[n]['medium_voltage_conn_node'] = mv_node
            # demanda diversificada dos consumidores conectados em baixa tensão
            s = ((1.5 - 0.8) * random.random() + 0.8) * (1.0 / (k * 0.001 + 1.0)) 

            graph.node[n]['active_power'] = round(s * np.cos(np.arccos(pf)), 3)
            graph.node[n]['reactive_power'] = round(s * np.sin(np.arcsin(pf)), 3)
            if s < 2.0:
                graph.node[n]['phase'] = random.choice(['a', 'b', 'c'])
            else:
                graph.node[n]['phase'] = 'abc'
        else:
            graph.node[n]['voltage_level'] = 'medium voltage'
            graph.node[n]['color'] = 'rgb(31, 119, 180)'
            graph.node[n]['active_power'] = 0.0
            graph.node[n]['reactive_power'] = 0.0
           

    # acréscimo ao dicionário json para indicar nas linhas o seu 
    # nome, comprimento, indicação se linha ou transformador e 
    # presença ou não de chave
    for i, j in graph.edges.items():
        source, target = i
        graph.edges[i]['name'] = 'Section_%s_%s' % (source, target)

        if graph.node[source]['voltage_level'] != graph.node[target]['voltage_level']:
            graph.edges[i]['type'] = 'transformer'
        else:
            graph.edges[i]['type'] = 'line'

            if graph.node[source]['voltage_level'] == 'medium voltage':
                # a = 0.05
                a = 0.1
                # b = 0.1  
                b = 0.8
                graph.edges[i]['length'] = round((b - a) * random.random() + a, 3)
            else:
                # a = 0.006
                a = 0.01
                # b = 0.01
                b = 0.1
                graph.edges[i]['length'] = round((b - a) * random.random() + a, 3)

        if source == 0 and target == 1:
            graph.edges[i]['switch'] = 'sw_1'
        else:
            graph.edges[i]['switch'] = None

    # write json formatted data
    d = json_graph.node_link_data(graph) # node-link format to serialize

    d['transformers'] = []
    # percentual de transformadores com base no Critério de Projetos 001 da
    # ENEL: Rede de distribuição aérea de média e baixa tensão.
    transformers_powers = {15.0: 5,
                           45.0: 25,
                           75.0: 25,
                           112.5: 25,
                           150.0: 10,
                           225.0: 5,
                           300.0: 5}

    powers_list = []
    for i, j in transformers_powers.items():
        for k in range(j):
            powers_list.append(i)
    random.shuffle(powers_list)

    for i, j in graph.edges.items():
        source, target = i
        if graph.node[source]['voltage_level'] != graph.node[target]['voltage_level']:
            tr = {}
            tr['name'] = 'trafo_%s_%s' % (graph.node[source]['name'], graph.node[target]['name'])
            tr['source'] = source
            tr['target'] = target
            tr['power'] = random.choice(powers_list)
            tr['nodes'] = lv_grids[min(source, target)]
            tr['bess_nodes'] = random.sample(tr['nodes'], int(len(tr['nodes']) * 0.3))
            tr['prosumer_bess_nodes'] = random.sample(tr['nodes'], int(len(tr['nodes']) * 0.3))
            tr['dg_nodes'] = random.sample(tr['nodes'], int(len(tr['nodes']) * 0.3))

            d['transformers'].append(tr)

    # write json
    json.dump(d, open('force.json', 'w'))
    print('\nWrote node-link JSON data to force/force.json')

    return d


def create_mygrid_model(file):
    data = json.load(file)

    vll_mt = p2r(13.8e3, 0.0)
    vll_bt = p2r(380.0, 0.0)
    eg1 = ExternalGrid(name='extern grid 1', vll=vll_mt)

    # switchs
    sw1 = Switch(name='sw_1', state=1)

    # transformers
    zpu = 3.5 / 100.0 # zpu = z% / 100.0
    vbase = 220.0 # Volts
    sbase = 112.5 # kVA
    zbase = (vbase ** 2) / (sbase * 1e3)
    z = zpu * zbase # impedancia do trafo referica a baixa tensao

    a = 3.5 # relação x/r, valor adotado
    r = z / np.sqrt(1 + a**2)
    x = a * r
    
    t1 = TransformerModel(name="T1",
                          primary_voltage=vll_mt,
                          secondary_voltage=vll_bt,
                          power=225e3,
                          impedance=r + 1j*x)

    phase_conduct = Conductor(id=44)
    neutral_conduct = Conductor(id=31)

    line_model_a = LineModel(loc_a=0.0 + 29.0j,
                             loc_b=2.5 + 29.0j,
                             loc_c=7.0 + 29.0j,
                             loc_n=4.0 + 25.0j,
                             conductor=phase_conduct,
                             neutral_conductor=neutral_conduct,
                             neutral=False)

    phase_conduct_bt = Conductor(id=31)
    line_model_b = LineModel(loc_a=0.0 + 29.0j,
                             loc_b=2.5 + 29.0j,
                             loc_c=7.0 + 29.0j,
                             loc_n=4.0 + 25.0j,
                             conductor=phase_conduct_bt,
                             neutral_conductor=neutral_conduct,
                             neutral=False)

    nodes = dict()
    for node in data['nodes']:
        p = node['active_power'] * 1e3
        q = node['reactive_power'] * 1e3
        s = p + 1j * q
        if node['voltage_level'] == 'medium voltage':
            node_object = LoadNode(name='Node_' + str(node['name']),
                                   power=s,
                                   voltage=vll_mt)

            if node['name'] == 0:
                node_object = LoadNode(name='Node_' + str(node['name']),
                                       power=s,
                                       voltage=vll_mt, external_grid=eg1)                
        elif node['voltage_level'] == 'low voltage':
            if node['phase'] == 'abc':
                node_object = LoadNode(name='Node_' + str(node['name']),
                                       power=s,
                                       voltage=vll_bt)
            elif node['phase'] == 'a':
                node_object = LoadNode(name='Node_' + str(node['name']),
                                       ppa=s,
                                       voltage=vll_bt)
            elif node['phase'] == 'b':
                node_object = LoadNode(name='Node_' + str(node['name']),
                                       ppb=s,
                                       voltage=vll_bt)
            elif node['phase'] == 'c':
                node_object = LoadNode(name='Node_' + str(node['name']),
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
    return grid_elements


def display_data(grid):
    headings = ['node', 'voltage (V)']
    datas = [headings]
    for i, j in grid.load_nodes.items():
        v = j.vp
        v = r2p(v)
        m = v[0]
        a = v[1]
        text = ''
        for k, q in zip(m, a):
            text += '{r} ∠ {i}º '.format(r=round(k[0], 2), i=round(q[0], 2))
        datas.append([i, text])
    table_data = datas
    table = AsciiTable(table_data)    
    print(table.table)

    headings = ['line', 'length (milhas)']
    datas = [headings]
    for i, j in grid.sections.items():
        if j.transformer is None:
            l = j.length
            datas.append([i, str(l)])
    table_data = datas
    table = AsciiTable(table_data)
    #print(table.table)

def generate_nodes_and_values(device, pu_consumers, pu_load, max_dem_kva, nodes_lv):

    nodes = random.sample(nodes_lv, int(pu_consumers * len(nodes_lv)))
    # gera quantias aleatórias de geração tal que a soma será max_gen_kva
    load_values = list(np.around(np.random.uniform(2, 4, len(nodes)), 4))
    gen_values = list(np.around(np.random.uniform(1, 2, len(nodes)), 4))
    params = list()

    for n in range(len(nodes)):
        param = {}
        if device == 'stochastic_gen':
            param = {'size': gen_values[n]}
            # param = {'size': v}
        elif device == 'shiftable_load':
            param = {'size': load_values[n]}
        elif device == 'buffering_device':
            param = {'size': load_values[n]}
        elif device == 'storage_device':
            s = float(random.randint(5, 10))
            r = random.sample([0.1, 0.2, 0.3], 1)[0]
            param = {'size': s,
                     'rate': r,
                     'max_energy_flow': round(s * r, 2),
                     'max_soc': s,
                     'min_soc': round(0.1 * s, 2)}
        elif device == 'freely_control_gen':
            param = {'size': gen_values[n]}
        elif device == 'user_action_device':
            param = {'size': load_values[n]}
        
        params.append(param)

    return nodes, params


if __name__ == '__main__':
    '''
        Para a geração do arquivo base de simulação, o force.json, que descreve
        o tipo de cada nó de carga no sistema e como esses nós estão conectados
        serão especificados 6 tipos de dispositivos e suas respectivas 
        representatividades percentuais na rede. São eles:
        - D1: Dispositivos de operação estocástica, no caso, consideraremos
        geração eólica e geração foto-voltáica;
        - D2: Dispositivos de operação deslocável, pode ser qualquer tipo de carga
        que possa ser deslocável no tempo, dentro de certos limites, como por 
        exemplo, máquinas de lavar, sistemas de irrigação, bombas de pscina e de
        reservatórios de água, entre outros.
        - D3: Dispositivos que geram algum tipo de insumo, que não seja eletricidade,
        e que pode ser armazenado, dentro de certas limitações. Por exemplo um sistema
        de refrigeração/aquecimento que precisa manter a temperatura dentro de uma 
        faixa pré-estabelecida. Assim, enquanto dentro da faixa aceitável de 
        temperatura é possível deslocar o consumo para momentos de baixa no preço
        da energia.
        - D4: Dispositivos armazenadores de energia, como por exemplo baterias,
        fly-wheels ou super-capacitores.
        - D5: Dispositivos livremente controláveis, são exemplos destes dispositivos,
        geradores à algum combustivel que poder ser armazenado.
        - D6: Dispositivos de acionamento pelo usuário, são dispositivos diretamente 
        controláveis pelos usuário, que até possuem um determinado padrão que pode
        variar muito facilamente, tendo no final das contas um comportamento parecidos
        aos dispositivos do tipo D1 
    '''

    # ================================
    # System Configuration Variables #
    # ================================
    config = {
        'qtd_nodes_mv': 7,
        'max_demand_kva': 100.0,
        'devices': {
            # 'stochastic_gen': {
            #     'pu_load': 0.3,
            #     'pu_consumers': 0.5,
            # },
            'shiftable_load': {
                'pu_load': 0.2,
                'pu_consumers': 1.0,
            },
            'buffering_device': {
                'pu_load': 0.3,
                'pu_consumers': 0.8,
            },
            # 'storage_device': {
            #     'pu_load': 0.2,
            #     'pu_consumers': 0.3,
            # },
            'freely_control_gen': {
                'pu_load': 0.2,
                'pu_consumers': 0.05,
            },
            'user_action_device': {
                'pu_load': 0.5,
                'pu_consumers': 1.0,
            },
        },
    }

    total = 0.0
    total += config['devices']['shiftable_load']['pu_load']
    total += config['devices']['buffering_device']['pu_load']
    total += config['devices']['user_action_device']['pu_load']

    # A soma dos valores atribuidos à carga de shift-load, buffer-load e user-load
    # não pode ser maior que 1,0 pu.
    if total != 1.0:
        raise IOError('The sum of percent loads need to be 1.0')

    # ===============
    # make the grid #
    # ===============
    # armazena a estrutura da rede gerada no arquivo force.json
    graph = generate_grid(nodes_mv=config['qtd_nodes_mv']) 

    nodes_lv = [i['name'] for i in graph['nodes'] if i['voltage_level'] == 'low voltage']
    nodes_mv = [i['name'] for i in graph['nodes'] if i['voltage_level'] == 'medium voltage']

    qtd_nodes_lv = len(nodes_lv)
    qtd_nodes_mv = len(nodes_mv)

    print('Grid created with {} mv nodes and {} lv nodes'.format(qtd_nodes_mv, qtd_nodes_lv))

    config['nodes_lv'] = nodes_lv
    config['nodes_mv'] = nodes_mv

    for device in config['devices'].keys():
        nodes, values = generate_nodes_and_values(device,
                                                  config['devices'][device]['pu_consumers'],
                                                  config['devices'][device]['pu_load'],
                                                  config['max_demand_kva'],
                                                  nodes_lv)
        params = {i: j for i, j in zip(nodes, values)}
        config['devices'][device]['params'] = params

    # -----------------------------------------------
    # configuração dos devices dso_storage_device
    bess_nodes = [j for i in graph['transformers'] for j in i['bess_nodes']]
    params = list()
    for i in bess_nodes:
        s = float(random.randint(15, 20))
        r = random.sample([0.1, 0.2, 0.3], 1)[0]
        param = {'size': s,
                 'rate': r,
                 'max_energy_flow': round(s * r, 2),
                 'max_soc': s,
                 'min_soc': round(0.1 * s, 2)}
        params.append(param)
    params = {i: j for i, j in zip(bess_nodes, params)}
    config['devices'].setdefault('dso_storage_device', {'params': params})

    # -----------------------------------------------
    # configuração dos devices prosumer_storage_device
    prosumer_bess_nodes = [j for i in graph['transformers'] for j in i['prosumer_bess_nodes']]
    params = list()
    for i in prosumer_bess_nodes:
        s = float(random.randint(5, 10))
        r = random.sample([0.1, 0.2, 0.3], 1)[0]
        param = {'size': s,
                 'rate': r,
                 'max_energy_flow': round(s * r, 2),
                 'max_soc': s,
                 'min_soc': round(0.1 * s, 2)}
        params.append(param)
    params = {i: j for i, j in zip(prosumer_bess_nodes, params)}
    config['devices'].setdefault('storage_device', {'params': params})

    # -----------------------------------------------
    # configuração dos devices prosumer_storage_device
    dg_nodes = [j for i in graph['transformers'] for j in i['dg_nodes']]
    params = list()
    for i in dg_nodes:
        s = float(random.randint(5, 10))
        param = {'size': s}
        params.append(param)
    params = {i: j for i, j in zip(dg_nodes, params)}
    config['devices'].setdefault('stochastic_gen', {'params': params})

    # salva as configurações geradas em 
    # arquivo json
    json.dump(config, open('config.json', 'w'))

    # create the adj_matrix file
    size = len(graph['nodes'])
    adj_array = np.zeros((size, size))
    for i, line in enumerate(adj_array):
        for j in graph['links']:
            if i == j['source']:
                adj_array[i, j['target']] = 1
                adj_array[j['target'], i] = 1
    np.savetxt('adj_array.txt', adj_array, delimiter=' ', fmt='%d')

    # create the bus xy coordinates file
    coords = list()
    aux = [0, 0]
    for i in graph['nodes']:
        aux[0] += random.randint(10, 100)
        aux[1] += random.randint(10, 100)
        coords.append([i['name'], aux[0], aux[1]])
    coords = np.array(coords)
    np.savetxt('bus_xy.txt', coords, delimiter=',', fmt='%d')

    # grid = create_mygrid_model(open('force.json', 'r'))
    # calc_power_flow(grid.dist_grids['F0'])
