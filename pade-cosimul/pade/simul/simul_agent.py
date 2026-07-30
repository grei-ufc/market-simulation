from pade.misc.utility import display_message, start_loop, defer_to_thread
from pade.core.agent import Agent
from pade.acl.messages import ACLMessage
from pade.acl.aid import AID
from pade.behaviours.protocols import TimedBehaviour

import sys
import pathlib
import time
import json
import socket
import h5py
from pprint import pprint
import datetime as dt
import numpy as np

import random

PATH = pathlib.Path(__file__).parent.absolute().as_posix()
SERVER_NAME = 'localhost'
SERVER_PORT = 8005

TOPOLOGY = None

# tempo de verificação para envio de mensagens ao simulador
STEP_SIMUL_TIME = 1.0

# atributo de tempo da ultima mensagem enviada ao simulador
#  de comunicação
LAST_MESSAGE_SIMUL_TIME = 0

# armazena o valor do tempo de simulação do Mosaik para 
# realizar a verificação da atualização das mensagens
MOSAIK_SIMUL_TIME = 0

# tempo de recebimento da ultima mensagem pelo agente simul
LAST_MESSAGE_TIME = None

# Dicionário das mensagens recebidas juntamente com seu status de simulação:
# chave do diconário: identicador da mensagem dado pelo valor armazenado
#                     na variável SIMULATOR_MESSAGE_ID
# significado do estatos de simulação:
#   0 -> mensagem recebida e não enviada ao ns-3
#   1 -> mensagem enviada e aguardando resposta do ns-3
RECEIVED_MESSAGES = dict()

# armazena as mensagens enviadas para o simulador de comunicação
# e auxilia no processo de re-envio aos agentes destinatários após o
# retorno da resposta do simulador de comunicação
MESSAGES_SENT_TIMES = dict()

# aramazena os tempos de recepção simulados pelo ns-3
# da ultima mensagen recebida por cada um dos agentes.
RECEIVED_MESSAGES_TIMES = dict()

# variável contador, auxiliar para escrita no arquivo .hdf5
ROUND = 0

# identificador único de cada mensagem recebida pelo simulador
SIMULATOR_MESSAGE_ID = 1

NS3_CURRENT_TIME = 0.0

NS3_SENT_MESSAGES_SIZE = 0

SIMULATING = False

def get_id(localname):
    global TOPOLOGY

    if not TOPOLOGY:
        with open('topology.json', 'r') as f:
            TOPOLOGY = json.load(f)

    for i in TOPOLOGY['agents']:
        _localname = i['name'].split('@')[0]
        if localname == _localname:
            return int(i['id'])
    else:
        return None


def get_result(sender, receiver, results):
    result = None
    for r in results:
        if get_id(sender.localname) == int(r['val_s']) and get_id(receiver.localname) == int(r['val_d']):
            result = r
            break
    return result


def recvall(sock):
    BUFF_SIZE = 4096 # 4 KiB
    data = b''
    while True:
        part = sock.recv(BUFF_SIZE)
        data += part
        if len(part) < BUFF_SIZE:
            # either 0 or end of data
            break
    return data


def ns3_comm(data):
    CLIENT_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    CLIENT_SOCKET.connect((SERVER_NAME, SERVER_PORT))
    CLIENT_SOCKET.sendall(data.encode())
    result = recvall(CLIENT_SOCKET)
    CLIENT_SOCKET.close()
    return result


def save_message_data(messages_data):
    """
        messages_data list of tuples with these elements:
            (id_, ns3_time, mosaik_time, message)
    """

    if messages_data:
        with h5py.File('messages_data.hdf5', 'a') as f:
            for data in messages_data:
                id_, ns3_time, mosaik_time, message = data
                id_ = str(id_)

                f.create_group(id_)
                f[id_].attrs['from-agent'] = message.sender.localname
                f[id_].attrs['to-agents'] = [r.localname for r in message.receivers]

                if message.message_length:
                    f[id_].attrs['message-length'] = int(message.message_length)
                else:
                    f[id_].attrs['message-length'] = len(message.get_message())
                
                f[id_].attrs['protocol'] = message.protocol
                f[id_].attrs['performative'] = message.performative
                f[id_].attrs['ns3-time'] = ns3_time
                f[id_].attrs['mosaik-time'] = mosaik_time


def run_simulation(agent):
    global TOPOLOGY, MOSAIK_SIMUL_TIME
    global LAST_MESSAGE_TIME, MESSAGES_SENT_TIMES, LAST_MESSAGE_SIMUL_TIME
    global NS3_CURRENT_TIME, SIMULATING, RECEIVED_MESSAGES, RECEIVED_MESSAGES_TIMES
    global NS3_SENT_MESSAGES_SIZE

    data = list()
    # Se uma mensagem foi recebida, então envia essa mensagem para o simulador
    if not SIMULATING:
        if not TOPOLOGY:
            with open('topology.json', 'r') as f:
                TOPOLOGY = json.load(f)

        last_message_simul_time = LAST_MESSAGE_SIMUL_TIME

        # The RECEIVED_MESSAGES is copied
        # for thread processing questions
        received_messages_copy = dict(RECEIVED_MESSAGES)
        messages_data = list()

        for id_, (status, message) in received_messages_copy.items():
            # caso a mensagem ainda não tenha sido enviada ao ns-3
            if status == 0:
                # Lógica de sincronização de tempos de mensagens
                # do simulador de comunicação com o Mosaik
                if message.sender.name in RECEIVED_MESSAGES_TIMES.keys():
                    message_time = RECEIVED_MESSAGES_TIMES[message.sender.name] + random.randint(10, 100)
                else:
                    message_time = MOSAIK_SIMUL_TIME + random.randint(10, 100)

                messages_data.append((id_, NS3_CURRENT_TIME, message_time, message))

                # caso a estampa de tempo do Mosaik seja menor que o tempo de simulação
                # da ultima mensagem recebida por um nó do simulador ns-3, um alarme
                # é disparado avisando que o simulador ns-3 está a frente do Mosaik e que
                # portanto não será possível simular essa mensagem.
                # Ainda, se a mensagem for envida da forma como está, ocorrerá erro
                # na simulação como um todo
                if message_time < NS3_CURRENT_TIME:
                    # display_message(agent.aid.name, '>>> DISCOORDINATION BETWEEN MOSAIK AND NS-3!!!')
                    message_time = NS3_CURRENT_TIME + random.randint(10, 100)

                if message_time > last_message_simul_time:
                    last_message_simul_time = int(message_time)

                for r in message.receivers:
                    info = dict()
                    info['sender'] = get_id(message.sender.localname)
                    info['receiver'] = get_id(r.localname)

                    # !!! ALTERAÇÃO TEMPORARIA !!!
                    # TAMANHO FIXO DAS MENSAGENS
                    # info['message_length'] = 10
                    # LIMITA O TAMANHO DAS MENSAGENS A 2000 BYTES
                    # if len(message.get_message()) > 2000:
                    #     info['message_length'] = 2000
                    # else:
                    #     info['message_length'] = len(message.get_message())

                    if message.message_length:
                        info['message_length'] = int(message.message_length)
                    else:
                        info['message_length'] = len(message.get_message())
                    
                    info['time'] = message_time

                    data.append(info)
                    MESSAGES_SENT_TIMES[id_] = info['time']
                # FIM: for r in message.receivers

                # altera o status da mensagem para enviada para simulação
                RECEIVED_MESSAGES[id_] = (1, message)
            # FIM: if status == 0
        # FIM: for id_, (status, message) in received_messages_copy.items()

        # salva os dados da mensagem recebida no arquivo messages_data.hdf5
        save_message_data(messages_data)

        # display_message(agent.aid.name, '>>> JSON DATA SENDED TO NS-3 simulator:')
        # pprint(data)

        SIMULATING = True
        # list of ns3 responses
        ns3_response = json.loads(ns3_comm(json.dumps(data)).decode())
        # list of final ns3 responses
        final_ns3_results = list()
        final_ns3_results.extend(ns3_response)
        # ns3_response = json.loads(ns3_comm("[]").decode())

        NS3_CURRENT_TIME = float(final_ns3_results.pop()["CURRENT_NS3_TIME"])
        NS3_SENT_MESSAGES_SIZE = int(final_ns3_results.pop()["SENT_MESSAGES_SIZE"])
        display_message(agent.aid.name, 'NS3_SENT_MESSAGES_SIZE: {}'.format(NS3_SENT_MESSAGES_SIZE))
        SIMULATING = False
        LAST_MESSAGE_TIME = None
        LAST_MESSAGE_SIMUL_TIME = last_message_simul_time

        return final_ns3_results
        # return []
    # FIM: if not SIMULATING

class Time(TimedBehaviour):
    """Time Behaviour"""
    def __init__(self, agent, time):
        super(Time, self).__init__(agent, time)
        self.cont = 0

    def on_time(self):
        super(Time, self).on_time()
        global RECEIVED_MESSAGES

        if RECEIVED_MESSAGES:
            self.cont += 1
            defer_to_thread(run_simulation,
                            self.simulation_result,
                            self.agent)

    def simulation_result(self, results):
        global ROUND, MESSAGES_SENT_TIMES, LAST_MESSAGE_SIMUL_TIME, NS3_CURRENT_TIME
        global RECEIVED_MESSAGES_TIMES, RECEIVED_MESSAGES, MOSAIK_SIMUL_TIME

        if results is not None:

            last_message_simul_time = LAST_MESSAGE_SIMUL_TIME

            # caso o simulador de comunicação devolva resultados válidos
            if results:
                # display_message(self.agent.aid.name, '>>> MESSAGES RETURNED BY NS3 SIMULATOR:')
                # pprint(results)
                data = list()
                for r in results:
                    aux = RECEIVED_MESSAGES.get(int(r['val_id']))
                    if aux:
                        status, message = aux
                        # armazena o maior tempo de recepção entre as mensagens
                        # enviadas pelos pontos de comunicação
                        if int(r['val_t']) > last_message_simul_time:
                            last_message_simul_time = int(r['val_t'])

                        # O resultado armazenado é a  diferença entre o tempo de
                        # envio e o tempo de recepção, e não o tempo de recepção
                        time_snd = MESSAGES_SENT_TIMES.pop(int(r['val_id']))
                        if time_snd:
                            data.append([int(r['val_s']),
                                        int(r['val_d']),
                                        int(r['val_t']) - time_snd,
                                        MOSAIK_SIMUL_TIME,
                                        NS3_CURRENT_TIME])
                        else:
                            print('Key {} not found in MESSAGES STACK'.format(int(r['val_id'])))

                        for receiver in message.receivers:
                            # display_message(
                            #     self.agent.aid.name,
                            #     '>>> SENDING MSG FROM: {} TO: {}'.format(message.sender.name,
                            #                                              receiver.name)
                            # )
                            self.agent.forward(message)
                            RECEIVED_MESSAGES.pop(int(r['val_id']))
                            RECEIVED_MESSAGES_TIMES[receiver.name] = int(r['val_t'])

                # atualiza o valor da variavel LAST_MESSAGE_SIMUL_TIME
                # com o maior tempo de recepção das mensagens envidas 
                # com sucesso
                LAST_MESSAGE_SIMUL_TIME = last_message_simul_time
                if data:
                    with h5py.File('communication.hdf5', 'a') as f:
                        f.create_dataset(str(ROUND), data=np.array(data))
                        ROUND += 1

            # caso se queira proceder a simulação sem os resultados do ns-3
            # basta descomentar o trecho de código abaixo:
            # ||  ||  ||  ||
            # \/  \/  \/  \/
            # else:
            #   pass


class SimulAgent(Agent):
    def __init__(self, host='localhost', port=8002):
        self.simul_agent_aid = AID('simul_agent@' + str(host) + ':' + str(port))
        super(SimulAgent, self).__init__(self.simul_agent_aid)
        display_message(self.aid.name, 'SimulAgent is up...')

        time_behaviour = Time(self, STEP_SIMUL_TIME)
        self.behaviours.append(time_behaviour)

    def react(self, message):
        global LAST_MESSAGE_TIME, RECEIVED_MESSAGES, MOSAIK_SIMUL_TIME
        global RECEIVED_MESSAGES_TIMES, SIMULATOR_MESSAGE_ID

        super(SimulAgent, self).react(message)
        if 'ams' not in message.sender.name:
            # display_message(self.aid.name, 'message received from {}'.format(message.sender.name))

            if not get_id(message.sender.localname):
                display_message(self.aid.name, 'FORWARDING MESSAGE: SEND. NOT IN topology.json FILE')
                self.forward(message)
            elif not all([get_id(r.localname) for r in message.receivers]):
                display_message(self.aid.name, 'FORWARDING MESSAGE: SOME REC. NOT IN topology.json FILE')
                self.forward(message)
            else:
                # atualiza a variavel que armazena o tempo de simulação do Mosaik
                if message.simulation_time_ms:
                    # no caso de um valor de tempo Mosaik atualizado, duas ações
                    # são realizadas:
                    # 1. Atualiza a variável MOSAIK_SIMUL_TIME com o novo valor
                    #    de tempo do simulador Mosaik
                    # 2. Reinicializa o dicionário da variável RECEIVED_MESSAGES_TIMES
                    #    pois se o Mosaik avançou no tempo, não é mais necessário
                    #    calcular os tempos de retorno das mensagens entre os agentes,
                    #    ou seja uma nova rodada de interações é iniciada.
                    cond_1 = int(message.simulation_time_ms) > MOSAIK_SIMUL_TIME
                    cond_2 = 'bess' in message.sender.name
                    cond_3 = 'dso' in message.sender.name
                    cond_4 = 'market' in message.sender.name
                    if cond_1 and (cond_2 or cond_3 or cond_4):
                        MOSAIK_SIMUL_TIME = int(message.simulation_time_ms)
                        RECEIVED_MESSAGES_TIMES = dict()
                        display_message(self.aid.name, 'MOSAIK_SIMUL_TIME UPDATED TO {}'.format(MOSAIK_SIMUL_TIME))

                # Verifica o tempo mosaik para avaliar
                # a necessidade de simulação da comunicação, em ms.
                if MOSAIK_SIMUL_TIME < 15 * 60 * 1000:
                    display_message(self.aid.name, 'FORWARDING MESSAGE: MOSAIK TIME < 15 MIN.')
                    self.forward(message)
                    return

                # restringe a avaliação dos tempos de envio das mensagens
                # à comunicação entre BESS e prosumers
                # if 'dso' in message.sender.name or 'market' in message.sender.name:
                #     display_message(self.aid.name, 'FORWARDING MESSAGE: DSO or MARKET message.')
                #     self.forward(message)
                #     return

                # for r in message.receivers:
                #     if 'dso' in r.name or 'market' in r.name:
                #         display_message(self.aid.name, 'FORWARDING MESSAGE: DSO or MARKET response message.')
                #         self.forward(message)
                #         return

                # Faz copias da mensagem recebida, criando novas
                # mensagens, cada uma com um único receptor, sendo 
                # uma nova mensagem para cada receptor.
                # Dessa forma é possível simular os atrasos de recepção
                # de cada uma das mensagens e dessa forma refletir no mecanismo 
                # de envio de mensagens do PADE os resultados da simulação ns-3
                xml_message = message.get_message()
                for r in message.receivers:
                    message_copy = ACLMessage()
                    message_copy.set_message(xml_message)
                    message_copy.set_receiver(r)

                    RECEIVED_MESSAGES[SIMULATOR_MESSAGE_ID] = (0, message_copy)
                    SIMULATOR_MESSAGE_ID += 1

                LAST_MESSAGE_TIME = message.datetime


if __name__ == '__main__':
    simul_agent = SimulAgent(port=sys.argv[1])
    start_loop([simul_agent])
