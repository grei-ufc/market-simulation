import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import json
import pathlib

import sys
sys.path.append('../')

from load_data import get_load_data, get_gen_data, get_spot_prices_data


def pick_load_scenarios_from_db(n, data=None):
    loads = list()

    if data:
        node_id = data['node_id']
        for scenario in range(n):
            load_df = get_load_data(load_index=node_id)[:96]
            normalized_df = (load_df-load_df.min())/(load_df.max()-load_df.min())
            load_df = data['load_kw'] * normalized_df
            loads.append(load_df.pload.values)
            node_id += 1
    else:
        for scenario in range(n):
            some_load_max_value = 2.5
            load_df = get_load_data()[:96]
            normalized_df = (load_df-load_df.min())/(load_df.max()-load_df.min())
            load_df = some_load_max_value * normalized_df
            loads.append(load_df.pload.values)
    return loads


def pick_gen_scenarios_from_db(n, data=None):
    gens = list()

    if data:
        node_id = data['node_id']
        for scenario in range(n):
            gen_df = get_gen_data(gen_index=node_id)[:96]
            normalized_df = (gen_df-gen_df.min())/(gen_df.max()-gen_df.min())
            gen_df = data['gen_kw'] * normalized_df
            gens.append(gen_df.pgen.values)
            node_id += 1
    else:
        for scenario in range(n):
            some_gen_max_value = 1.5
            gen_df = get_gen_data()[:96]
            normalized_df = (gen_df-gen_df.min())/(gen_df.max()-gen_df.min())
            gen_df = some_gen_max_value * normalized_df
            gens.append(gen_df.pgen.values)
    return gens


def pick_spot_prices_scenarios_from_db(n, data=None):
    prices = list()

    if data:
        node_id = data['node_id']
        for scenario in range(n):
            prices.append(get_spot_prices_data(spot_index=node_id).Price.values[:96])
            node_id += 1
    else:
        for scenario in range(n):
            prices.append(get_spot_prices_data().Price.values[:96])
    return prices


def reduce_scenarios(scenarios, reduced_scenarios_qtd, probs = None):
    # ---------------------------------------------
    # Definição das variaveis utilizadas
    # ---------------------------------------------
    
    # probabilidade associada a cada um dos cenarios
    scenarios_qtd = len(scenarios)
    if not probs:
        probs = [1 / scenarios_qtd for i in range(scenarios_qtd)]

    reduced_load_scenarios = list()
    scenarios_reduced_index = list()
    costs = list()
    kant_distances = list()

    # ---------------------------------------------
    # Compute a matriz de custos entre os cenarios
    # Step 0
    # ---------------------------------------------
    for l in scenarios:
        aux = list()
        for k in scenarios:
            aux.append(np.linalg.norm(l - k))
        costs.append(aux)
    costs = np.array(costs)

    # ---------------------------------------------
    # Compute das distancias de Kantorovich para
    # cada cenario
    # Step 1
    # ---------------------------------------------
    for line in costs:
        aux = 0.0
        for i, j in enumerate(line):
            aux += j * probs[i]
        kant_distances.append(aux)
    kant_distances = np.array(kant_distances)

    # Select o cenario com a minima distancia de Kantorovich 
    min_kant_dist_index = np.argmin(kant_distances)
    # Set e exclui o cenario para a lista de cenários reduzida
    reduced_load_scenarios.append(scenarios[min_kant_dist_index])
    # Set os custos do cenario encontrado 
    cost = costs[min_kant_dist_index, :]

    # Store o indice escolhido
    scenarios_reduced_index.append(min_kant_dist_index)

    # ---------------------------------------------
    # Compute a nova matriz de custos: step 2
    # ---------------------------------------------
    new_costs = costs
    new_kant_distances = kant_distances

    for _i in range(reduced_scenarios_qtd - 1):
        aux = list()
        for i, l in enumerate(costs):
            new_costs_line = list()
            if i not in scenarios_reduced_index:
                for k in l:
                    new_costs_line.append(min(cost[i], k))
            else:
                new_costs_line = new_costs[i, :]
            aux.append(new_costs_line)
        new_costs = np.array(aux)

        # Compute as novas distancias de Kantorovich
        aux1 = list()
        for scn_numb, line in enumerate(new_costs):
            aux2 = 0.0
            for i, j in enumerate(line):
                aux2 += j * probs[i]
            if scn_numb not in scenarios_reduced_index:
                aux1.append(aux2)
            else:
                aux1.append(np.inf)
        new_kant_distances = np.array(aux1)

        # Select o cenario com a minima distancia de Kantorovich 
        min_kant_dist_index = np.argmin(new_kant_distances)
        # Set e exclui o cenario para a lista de cenários reduzida
        reduced_load_scenarios.append(scenarios[min_kant_dist_index])
        # Set os custos do cenario encontrado 
        cost = new_costs[min_kant_dist_index, :]

        # Store o indice escolhido
        scenarios_reduced_index.append(min_kant_dist_index)

    # ---------------------------------------------
    # Compute as novas probabilidades dos cenarios: 
    # selecionados: Step 3
    # ---------------------------------------------
    probs_ = {i: probs[i] for i in scenarios_reduced_index}
    # loop entre os cenarios selecionados:
    for i in scenarios_reduced_index:
        # loop entre todos os cenarios:
        for j in range(scenarios_qtd):
            # se o cenario não é um dos cenarios escolhidos, então:
            if j not in scenarios_reduced_index:
                # loop entre os cenarios mais proximos de algum outro cenario, exceto ele mesmo
                for k in np.argsort(costs[j,:])[1:]:
                    # se o cenario mais proximo é o cenário atual, então atualiza a sua probabilidade
                    if k in scenarios_reduced_index: 
                        if k == i:
                            probs_[i] += probs[j]
                        break

    return probs_


def merge_scenarios(scenarios_data):
    merged_scenarios = list()
    dt1 = scenarios_data.pop(0)
    while scenarios_data:
        dt2 = scenarios_data.pop(0)
        for i1, i2 in dt1['probs'].items():
            for j1, j2 in dt2['probs'].items():
                new_scenario = {'name': 'Scenario-{}{}_{}{}'.format(dt1['prefix'], i1, dt2['prefix'], j1),
                                'prob': i2 * j2,
                                'data': [dt1['data'][i1], dt2['data'][j1]]}
                merged_scenarios.append(new_scenario)
    return merged_scenarios


def write_scenario_struct(data):
    has_storage = data['has_storage']
    data = data['scenarios']

    path = str(pathlib.Path(__file__).parent.absolute())

    with open(path + '/ScenarioStructure.dat', 'w') as f:
        f.write('set Stages := FirstStage SecondStage ;\n\n')

        f.write('set Nodes := RootNode\n')
        f.writelines(['{}-Node\n'.format(i) for i in data.keys()])
        f.write(' ;\n\n')

        f.write('param NodeStage := RootNode FirstStage\n')
        f.writelines(['{}-Node SecondStage\n'.format(i) for i in data.keys()])
        f.write(' ;\n\n')

        f.write('set Children[RootNode] := ')
        f.writelines(['{}-Node\n'.format(i) for i in data.keys()])
        f.write(' ;\n\n')

        f.write('param ConditionalProbability := RootNode 1.0\n')
        f.writelines(
            ['{}-Node {}\n'.format(i, round(data[i]['prob'], 8))
             for i in data.keys()])
        f.write(' ;\n\n')

        f.write('set Scenarios :=\n')
        f.writelines(['{}\n'.format(i) for i in data.keys()])
        f.write(' ;\n\n')

        f.write('param ScenarioLeafNode :=\n')
        f.writelines(['{} {}-Node\n'.format(i, i) for i in data.keys()])
        f.write(' ;\n\n')

        if has_storage:
            f.write('set StageVariables[FirstStage] := p_bilateral\nsoc[*] ;\n\n')
        else:
            f.write('set StageVariables[FirstStage] := p_bilateral ;\n\n')

        f.write('set StageVariables[SecondStage] := p_spot[*] ;\n\n')

        f.write('param StageCost := FirstStage  StageCost\nSecondStage StageCost ;')


def main(scenarios_qtd, reduced_scenarios_qtd, data=None):
    scenarios_qtd = scenarios_qtd  # numero de cenarios carregados
    reduced_scenarios_qtd = reduced_scenarios_qtd  # numero de cenarios reduzidos
    # ---------------------------------------------
    # carrega os dados dos cenarios de carga,
    # geração e preços do mercado spot
    # ---------------------------------------------
    if data:
        load_scenarios = pick_load_scenarios_from_db(scenarios_qtd, data)
        gen_scenarios = pick_gen_scenarios_from_db(scenarios_qtd, data)
        spot_prices_scenarios = pick_spot_prices_scenarios_from_db(scenarios_qtd, data)
    else:
        load_scenarios = pick_load_scenarios_from_db(scenarios_qtd)
        gen_scenarios = pick_gen_scenarios_from_db(scenarios_qtd)
        spot_prices_scenarios = pick_spot_prices_scenarios_from_db(scenarios_qtd)

    # ---------------------------------------------
    # reduz os cenarios de carga, geração e preços
    # ---------------------------------------------
    load_probs = reduce_scenarios(load_scenarios, reduced_scenarios_qtd)
    gen_probs = reduce_scenarios(gen_scenarios, reduced_scenarios_qtd)
    spot_prices_probs = reduce_scenarios(spot_prices_scenarios, reduced_scenarios_qtd)

    # ---------------------------------------------
    # combina os cenarios de carga e de geração (demanda)
    # ---------------------------------------------
    scenarios_data = [{
        'prefix': 'load',
        'data': load_scenarios,
        'probs': load_probs,
    },
        {
            'prefix': 'gen',
            'data': gen_scenarios,
            'probs': gen_probs,
        }]
    merged_scenarios_data = merge_scenarios(list(scenarios_data))

    demand_scenarios = list()
    demand_probs = list()
    for i in merged_scenarios_data:
        i['data'] = i['data'][0] - i['data'][1]
        demand_scenarios.append(i['data'])
        demand_probs.append(i['prob'])
    demand_probs = {i: j for i, j in enumerate(demand_probs)}

    # ---------------------------------------------
    # reduz os cenarios de carga combinados com geração (demanda)
    # ---------------------------------------------
    reduced_demand_probs = reduce_scenarios(demand_scenarios,
                                            reduced_scenarios_qtd,
                                            demand_probs)

    # ---------------------------------------------
    # combina os cenarios de demanda e de preços spot
    # ---------------------------------------------
    scenarios_data = [{
        'prefix': 'demand',
        'data': demand_scenarios,
        'probs': reduced_demand_probs,
    },
        {
            'prefix': 'spot',
            'data': spot_prices_scenarios,
            'probs': spot_prices_probs,
        }]

    merged_scenarios_data = merge_scenarios(list(scenarios_data))


    if not data:
        data = dict()
        data['bilatral_price'] = 40.0
        data['bilateral_max'] = 2.0
        data['has_storage'] = True
        data['storage_rate'] = 0.1
        data['storage_size'] = 2.0
        data['max_energy_flow'] = 0.2
        data['max_soc'] = 2.0
        data['min_soc'] = 0.2

    data['scenarios'] = {}
    for i in merged_scenarios_data:
        data['scenarios'][i['name']] = {
            'prob': i['prob'],
            'demand_data': list(np.round(i['data'][0], 4)),
            'spot_price_data': list(np.round(i['data'][1], 4))
        }

    path = str(pathlib.Path(__file__).parent.absolute())
    with open(path + '/config.json', 'w') as f:
        json.dump(data, f)

    write_scenario_struct(data)

    del data
    del load_scenarios
    del gen_scenarios
    del spot_prices_scenarios
    del demand_scenarios

    del load_probs
    del gen_probs
    del spot_prices_probs
    del demand_probs

    del merged_scenarios_data


if __name__ == "__main__":
    main(scenarios_qtd=10, reduced_scenarios_qtd=3)
