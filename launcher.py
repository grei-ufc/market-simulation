import subprocess
import shlex
from time import sleep

commands = 'python agente_teste_1_mosaik.py'
commands = shlex.split(commands)
p1 = subprocess.Popen(commands, stdin=subprocess.PIPE,)

sleep(3)

commands = 'python first.py'
commands = shlex.split(commands)
p2 = subprocess.Popen(commands, stdin=subprocess.PIPE,)

sleep(10)

p1.kill()
p2.kill()

commands = 'fuser -k 5000/tcp'
commands = shlex.split(commands)
p3 = subprocess.Popen(commands, stdin=subprocess.PIPE,)
sleep(2)
p3.kill()
