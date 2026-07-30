import numpy as np
import matplotlib.pyplot as plt
import h5py
import json
import random
import datetime as dt
import os


def plot_from_hdf5(path, qtd_medium_voltage_nodes):

    date = dt.datetime.now()
    folder_name = 'Graficos/{}'.format(date.strftime('%d_%m_%Y - %H:%M:%S'))
    os.mkdir(folder_name)

    f = h5py.File(path, 'r')
    s = f['Series']

    attrs = ['ppa', 'vpa']
    for attr in attrs:
        plt.figure(random.randint(1, 1000))
        for i, j in s.items():
            if 'MyGridSim0-0' in i:
                node = int(i.split('.')[1])
                # nós da média tensão
                if node < qtd_medium_voltage_nodes:
                    print(i)
                    data = j[attr][:]
                    plt.step([k / 4 for k in range(data.shape[0])], data)
        plt.title('Atributo: {}'.format(attr))
        plt.grid(True)
        plt.savefig('{}/{}-medium-voltage-grid.png'.format(folder_name, attr))

        plt.figure(random.randint(1, 1000))
        for i, j in s.items():
            if 'MyGridSim0-0' in i:
                node = int(i.split('.')[1])
                # nós da baixa tensão
                if node >= qtd_medium_voltage_nodes:
                    print(i)
                    data = j[attr][:]
                    plt.step([k / 4 for k in range(data.shape[0])], data)
        plt.title('Atributo: {}'.format(attr))
        plt.grid(True)
        plt.savefig('{}/{}-low-voltage-grid.png'.format(folder_name, attr))

        if attr == 'ppa':
            plt.figure(random.randint(1, 1000))
            ppa = list()
            for i, j in s.items():
                if 'MyGridSim0-0' in i:
                    print(i)
                    ppa.append(j[attr][:])
            data = np.sum(ppa, axis=0)
            plt.step([k / 4 for k in range(data.shape[0])], data)
            plt.title('Atributo: {} aggregated'.format(attr))
            plt.grid(True)
            plt.savefig('{}/aggregated_net_demand.png'.format(folder_name))


def plot_from_hdf5_for_article(path, qtd_medium_voltage_nodes):

    f = h5py.File(path, 'r')
    s = f['Series']

    attrs = ['ppa', 'vpa']
    plt.figure(random.randint(1, 1000))
    for k, attr in enumerate(attrs):
        plt.subplot(2, 1, k+1)
        for i, j in s.items():
            if 'MyGridSim0-0' in i:
                node = int(i.split('.')[1])
                # nós da média tensão
                if node >= qtd_medium_voltage_nodes:
                    print(i)
                    data = j[attr][:]
                    plt.step([k / 4 for k in range(data.shape[0])], data)
        plt.title('Atributo: {}'.format(attr))
        plt.grid(True)
    plt.show()


def traverse_datasets(hdf_file):
    """Traverse all datasets across all groups in HDF5 file."""
    def h5py_dataset_iterator(g, prefix=''):
        for key in g.keys():
            item = g[key]
            path = '{}/{}'.format(prefix, key)
            if isinstance(item, h5py.Dataset): # test for dataset
                yield (path, item)
            elif isinstance(item, h5py.Group): # test for group (go down)
                yield from h5py_dataset_iterator(item, path)

    with h5py.File(hdf_file, 'r') as f:
        for (path, dset) in h5py_dataset_iterator(f):
            print(path, dset)

    # with h5pyFile('file.h5', 'r') as f:
    #     arr = f['/DataSet1'][:]  # read entire dataset into memory

    return None

def plot_schedule_results(hdf5_file, medium_voltage_nodes_qtd):

    medium_voltage_nodes_qtd = medium_voltage_nodes_qtd

    with h5py.File('{}-bus.hdf5'.format(hdf5_file), 'r') as f:
        nodes_qtd = len(f['t0']['table'])
        voltage_data = {i: [] for i in range(medium_voltage_nodes_qtd, nodes_qtd)}
        active_power_data = {i: [] for i in range(medium_voltage_nodes_qtd, nodes_qtd)}

        for i in range(medium_voltage_nodes_qtd, nodes_qtd):
            for j in range(len(f)):
                voltage_data[i].append(f['t{}'.format(j)]['table'][i]['vm_pu'])
                active_power_data[i].append(f['t{}'.format(j)]['table'][i]['p_mw'] * 1e6/3.0)

    with h5py.File('{}-branch.hdf5'.format(hdf5_file), 'r') as f:
        branch_qtd = len(f['t0']['table'])
        load_data = {i: [] for i in range(medium_voltage_nodes_qtd, branch_qtd)}
        current_data = {i: [] for i in range(medium_voltage_nodes_qtd, branch_qtd)}

        for i in range(medium_voltage_nodes_qtd, branch_qtd):
            for j in range(len(f)):
                load_data[i].append(f['t{}'.format(j)]['table'][i]['loading_percent'])
                current_data[i].append(f['t{}'.format(j)]['table'][i]['i_ka'] * 1e3)

    v_array = np.array([voltage_data[i] for i in voltage_data.keys()], dtype=float)
    p_array = np.array([active_power_data[i] for i in active_power_data.keys()], dtype=float)
    l_array = np.array([load_data[i] for i in load_data.keys()], dtype=float)
    c_array = np.array([current_data[i] for i in current_data.keys()], dtype=float)

    plt.subplot(2, 1, 1)
    plt.step([i / 4 for i in range(p_array.shape[1])], p_array.transpose())
    plt.grid(True)

    plt.subplot(2, 1, 2)
    plt.step([i / 4 for i in range(v_array.shape[1])], v_array.transpose())
    plt.grid(True)

    plt.show()

def plot_diff_demand(hdf5_file):
    with h5py.File(hdf5_file, 'r') as f:
        for name, s in f['Series'].items():
            if 'ProsumerAgent' in name:
                plt.plot(s['demand_diff'][:])
        plt.grid(True)

def plot_communications(hdf5_file):
    with h5py.File(hdf5_file, 'r') as f:
        latencies = list() # armazena todos os valores de latencia das mensagens enviadas
        time_delay_inf_limite = -100 # ms
        time_delay_sup_limite = 60000 # ms

        # loop in all hdf5 groups inside hdf5 file
        for round in range(len(f)):
            # loop in all hdf5 datasets inside a hdf55 group
            for data in f[str(round)]:
                # carrega o valor associado ao time delay
                # de recebimento das mensagens
                time_delay = data[2]
                # verifica os limites de tempo estabelecidos
                if time_delay > time_delay_inf_limite and time_delay < time_delay_sup_limite:
                    latencies.append(time_delay/1e3)
        
        # configura e plota o histograma das latencias
        n, bins, patches = plt.hist(x=latencies, bins=15, facecolor='g', alpha=0.7, rwidth=0.92)
        # n, bins, patches = plt.hist(x=latencies, color='#0504aa', alpha=0.7, rwidth=0.85)
        
        # plt.grid(axis='y', alpha=0.75)
        plt.grid(alpha=0.75)
        plt.xlabel('latency in seconds')
        plt.ylabel('Frequency (number of messages)')
        plt.text(30, 3100, 'Total number\n of messages: {}'.format(len(latencies)))
        maxfreq = n.max()
        plt.ylim(ymax=np.ceil(maxfreq / 10) * 10 if maxfreq % 10 else maxfreq + 10)


def plot_lagrangian(file_name):
    with open(file_name, 'r') as f:
        data = json.load(f)
        for i, j in data.items():
            t = np.arange(len(j))
            y = [i*1e3 for i in j.values()]
            plt.step(t, y)
            plt.grid(True)


if __name__ == '__main__':
    plt.figure(1)
    plot_schedule_results('power_flow_data', medium_voltage_nodes_qtd=7)
    plt.figure(2)
    plot_schedule_results('new_power_flow_data', medium_voltage_nodes_qtd=7)

    # plot_from_hdf5('data.hdf5', qtd_medium_voltage_nodes=7)

    # plot_communications('communication.hdf5')

    # plot_diff_demand(hdf5_file='data.hdf5')

    # traverse_datasets(hdf_file='data.hdf5')
