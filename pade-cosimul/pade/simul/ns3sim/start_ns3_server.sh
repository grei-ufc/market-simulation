#!/bin/sh

#---
# Script for launch NS3PadeSim
#---

# export PADE_SIMUL_PATH=/home/lucas/Insync/lucassmelo@dee.ufc.br/GoogleDrive/GDrive/pade-cosimul/pade/simul/ns3sim
# export PATH=$PADE_SIMUL_PATH
PATH="${0%/*}"

# export NS3_LIBRARY_PATH=/home/lucas/ns3-build/debug/lib
LD_LIBRARY_PATH=$NS3_LIBRARY_PATH

echo "NS_LOG environment variable: $NS_LOG"
echo "NS3_LIBRARY_PATH environment variable: $NS3_LIBRARY_PATH"
echo "PATH environment variable: $PATH"

LD_LIBRARY_PATH=$LD_LIBRARY_PATH NS_LOG=$NS_LOG $PATH/ns3_server 127.0.0.1:8005
