#!/bin/sh

#---
# Script to set the NS3-PADE simulator environment variables
#---


# This is the location of the files: adj_array.txt, bus_xy.txt, devices.txt and topology.json
export PADE_WORK_PATH=/home/labplan603/GDrive/workspace/tese/market-simulation
#export PADE_WORK_PATH=/home/labplan603/GDrive/pade-cosimul/examples

# This is where the ns-3 library is installed
export NS3_LIBRARY_PATH=/home/labplan603/ns3-build/debug2/lib

export TCPUDP="udp"

# This is the NS3 log variable config
# export NS_LOG="SmartgridDefaultSimulatorImpl=level_all"
export NS_LOG=""

echo "[log]: NS3-PADE simulator enviroment variables are set."
echo "PADE_WORK_PATH=$PADE_WORK_PATH"
echo "NS3_LIBRARY_PATH=$NS3_LIBRARY_PATH"
echo "TCPUDP=$TCPUDP"
echo "NS_LOG=$NS_LOG"


