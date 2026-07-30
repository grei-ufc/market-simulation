#! /bin/sh
cd pade-cosimul
#./CONFIG_NS3_SIMUL_LABPLAN.sh
python setup.py install
cd /home/labplan603/anaconda3/envs/tese-1/lib/python3.7/site-packages/pade-2.2.2-py3.7.egg/pade/simul/ns3sim/
chmod +x start_ns3_server.sh
cd ~/GDrive/workspace/tese/market-simulation
#cd ..
pade create-pade-db
pade start-runtime --config_file pade_config.json

