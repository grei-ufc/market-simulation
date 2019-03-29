import json
import matplotlib.pyplot as plt

'''
{
    'stochastic_gen': {'0': 0.09, '1': 0.05, '2': 0.32, ....},
    'shiftable_load': {'0': 0.09, '1': 0.05, '2': 0.32, ....},
    'buffering_device': {'0': 0.09, '1': 0.05, '2': 0.32, ....},
    'user_action_load': {'0': 0.09, '1': 0.05, '2': 0.32, ....},
}
'''
data = json.load(open('data/ProsumerSim0-0.Prosumer_4.json'))

# plota a demanda de cada device separadamente
for i, j in data.items():
    plt.plot(j.values(), 'o-')

# plota a demanda total do prosumer

for i, j in data.items():
    
plt.plot(j.values(), 'o-')

plt.grid(True)
plt.show()