"""
Este arquivo carrega perfis de carga e de geração PV para serem utilizadas pelos prosumers
"""
import pandas as pd
import numpy as np
import random
import os

path = os.path.dirname(os.path.abspath(__file__))

GRID_DATA_PATH = path + '/1-MVLV-urban-5.303-1-no_sw'
MARKET_DATA_PATH = path + '/market-data'
DAYS = 30

coordinates_df = pd.read_csv('{}/Coordinates.csv'.format(GRID_DATA_PATH), delimiter=';')  # data frame com as coordenadas da rede
line_df = pd.read_csv('{}/Line.csv'.format(GRID_DATA_PATH), delimiter=';')  # data frame com as linhas da rede de distribuicao
node_df = pd.read_csv('{}/Node.csv'.format(GRID_DATA_PATH), delimiter=';')  # data frame com os nodes da rede de distribuição
line_type = pd.read_csv('{}/LineType.csv'.format(GRID_DATA_PATH), delimiter=';')  # data frame com os tipos de linhas da rede de distribuição
load_df = pd.read_csv('{}/Load.csv'.format(GRID_DATA_PATH), delimiter=';')[138:242]  # data frame com cargas em cada node da rede de distribuição
load_profile_df = pd.read_csv('{}/LoadProfile.csv'.format(GRID_DATA_PATH), delimiter=';')  # perfis de carga associados aos nodes da rede
gen_df = pd.read_csv('{}/RES.csv'.format(GRID_DATA_PATH), delimiter=';')[134:]  # data frame com geradores em cada node da rede de distribuição
gen_profile_df = pd.read_csv('{}/RESProfile.csv'.format(GRID_DATA_PATH), delimiter=';')  # perfis de geração associados aos nodes da rede

spot_prices_df = pd.read_excel('{}/Nordpool_Market_Data-3.xlsx'.format(MARKET_DATA_PATH))


def get_load_data(load_index=None):

    month_delta = 24 * 4 * 30 * 1

    if load_index != None:
        load = load_df.iloc[load_index % 100]
        start_day = 15 * 24 * 4 + month_delta
    else:
        load_index = random.randint(0, len(load_df) - 1)
        load = load_df.iloc[load_index]    
        start_day = random.randint(0, 30) * 24 * 4 + month_delta

    end_day = start_day + 30 * 24 * 4

    load_p_data = load_profile_df['{}_pload'.format(load.profile)][start_day:end_day]
    load_q_data = load_profile_df['{}_qload'.format(load.profile)][start_day:end_day]

    load_p_data = pd.Series(load_p_data.values, index=range(24 * 4 * DAYS))
    load_q_data = pd.Series(load_q_data.values, index=range(24 * 4 * DAYS))

    loads_df = pd.concat([load_p_data, load_q_data], axis=1)
    loads_df.columns = ['pload', 'qload']

    return loads_df


def get_gen_data(gen_index=None):

    month_delta = 24 * 4 * 30 * 1
    if gen_index != None:
        gen = gen_df.iloc[gen_index % 12]
        start_day = 15 * 24 * 4 + month_delta
    else:
        gen_index = random.randint(0, len(gen_df) - 1)
        gen = gen_df.iloc[gen_index]
        start_day = random.randint(0, 30) * 24 * 4 + month_delta

    end_day = start_day + 30 * 24 * 4

    gen_p_data = gen_profile_df[gen.profile][start_day:end_day]
    gen_p_data = pd.Series(gen_p_data.values, index=range(24 * 4 * DAYS))

    gens_df = pd.DataFrame(gen_p_data, columns=['pgen'])

    return gens_df


def get_spot_prices_data(spot_index=None):

    if spot_index:
        month_delta = 24 * 30 * 6
        start_day = spot_index * 24 + month_delta
        end_day = start_day + 30 * 24
    else:
        month_delta = 24 * 30 * 6
        start_day = random.randint(0, 30) * 24 + month_delta
        end_day = start_day + 30 * 24

    spot_p_data = spot_prices_df.SpotPriceEUR[start_day:end_day]

    # converte os dados de preços da base horária para base de 15min 
    aux = np.array([])
    for i in spot_p_data:
        aux = np.concatenate((aux, np.ones(4) * i))

    spot_p_data = pd.Series(aux, index=range(24 * 4 * DAYS))
    spot_df = pd.DataFrame(spot_p_data, columns=['Price'])

    return spot_df

if __name__ == '__main__':
    # LOAD DATA
    loads = list()
    for load_idx in range(10):
        loads.append(get_load_data(random.uniform(3.0, 5.0)))

    # PLOT DATA
    for l in loads:
        l.pload[:2 * 24 * 4].plot()

    sum(loads).pload[:2 * 24 * 4].plot()
