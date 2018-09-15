import subprocess
import shlex
from time import sleep

commands = 'python start_pade_agents.py'
commands = shlex.split(commands)
p1 = subprocess.Popen(commands, stdin=subprocess.PIPE)

sleep(3.0)

commands = 'python start_mosaik_sim.py'
commands = shlex.split(commands)
p2 = subprocess.Popen(commands, stdin=subprocess.PIPE)

sleep(3.0)

p1.kill()
p2.kill()

commands = 'fuser -k 5000/tcp'
commands = shlex.split(commands)
p3 = subprocess.Popen(commands, stdin=subprocess.PIPE,)
sleep(1.0)
p3.kill()
