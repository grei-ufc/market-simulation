import subprocess
import shlex
from time import sleep

commands = 'pade start-runtime --config_file pade_config.json'
commands = shlex.split(commands)
p1 = subprocess.Popen(commands, stdin=subprocess.PIPE)

sleep(15.0)

commands = 'python start_mosaik_sim.py'
commands = shlex.split(commands)
p2 = subprocess.Popen(commands, stdin=subprocess.PIPE)

sleep(120.0)

p1.terminate()
p2.terminate()
