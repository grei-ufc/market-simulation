# market-simulation

> Simulation models to analyses in a electric energy market based in multi-agent systems.

## Explanation

This repository will contain the simulation files referring to an electric energy market system based on the concept of multi-agents. The multi-agent system will be implemented using the framework [PADE](https://pade-docs-en.readthedocs.io/en/latest/) and the simulation time, as well as the implementation of some models will be realized using the software [Mosaik](https://mosaik.readthedocs.io/en/latest/).


| **directory**                   | **content**                                                     |
|---------------------------------|-----------------------------------------------------------------|
| .                               | main directory with the majority of the code files              |
| 1-MVLV-urban-5.303-1-no_sw      | data like load and generatio profiles (from Simbech project)    |
| force                           | algorithm for grid topology generation                          |
| mosaik-mygrid                   | mygrid mosaik simulator package                                 |
| stochastic_model                | stochastic optimization models                                  |


| **Files in . directory**        | **Content**                                                     |
|---------------------------------|-----------------------------------------------------------------|
| start_mosaik_sim.py             | starts, instantiates, connects and runs the simulators          |
| start_pade_agents.py            | instantiates, starts and runs the agents                        |
| pade_config.json                | stores the pade runtime configurations                          |
| launcher.py                     | start the agents and the mosaik co-simulation process           |
| prosumer.py                     | defines the prosumers behaviour                                 |
| prosumer_sim_with_mosaik_api.py | connects the prosumer simualtor to mosaik                       |
| prosumer_agent.py               | defines the prosumer agent                                      |
| bess.py                         | defines the bess behaviour                                      |
| bess_sim_with_mosaik_api.py     | connects the bess simulator to mosaik                           |
| bess_agent.py                   | defines the bess agent                                          |
| dso_agent.py                    | defines the dso agent                                           |
| solver_agent.py                 | defines the solver agent to solve the MILP models               |
| plot_results.py                 | some scripts to visualize the co-simulation results             |
| load_data.py                    | generate the load and generation profiles from simbench package |
| grid_optimization.py            | optimization models to grid secure operation                    |
| force.json                      | grid topology information                                       |
| config.json                     | prosumers and devices information                               |
| epex_sample.xlsx                | day-ahead market prices data from epex-spot                     |
| storage_optimization.py         | optimization models to storage operation                        |
| storage_optimization_2.py       | optimization models to storage operation 2                      |
| calc_methods.py                 | defines the demand curves                                       |


| **Files in force directory** | **description**                                   |
|------------------------------|---------------------------------------------------|
| force.py                     | script to create config.json and force.json files |


| **Files in mosaik-mygrid directory** | **description**                                              |
|--------------------------------------|--------------------------------------------------------------|
| mosaik_mygrid                        | a directory with the code for mygrid integration with mosaik |


| **Files in mosaik-mygrid directory** | **description**                                                |
|--------------------------------------|----------------------------------------------------------------|
| config.json                          | configurations for stochastic optimization model               |
| generate_scenarios.py                | script to generate and reduce scenarios for optimization model |
| ReferenceModel.py                    | optimization deterministic model in pyomo                      |
| run_stochastic_model.py              | script to run the stochastic deterministic model               |
| ScenarioStructure.dat                | file to describe the stochastic topology of the problem        |


## Description

This repository contain the simulation files referring to the simulation of an *electric energy market system* based on the concept of multi-agents (SMA) and Transactive Energy (TES) Systems.

The core softwares used in the simulation are:
- [PADE](https://pade-docs-en.readthedocs.io/en/latest/): a framework for SMA development in Python language with a FIPA based library, a execution runtime and a management GUI;
- [Mosaik](https://mosaik.readthedocs.io/en/latest/): a framework for co-simulation development with API for simulators integration, scenarios description and simulation coordination.

Developers who contribute to this project should follow the git working model based on *branches* following the methodology described in this [article](https://nvie.com/posts/a-successful-git-branching-model/).

## Install

To run the simulation the following steps should be performed:

Download the simulation files contained in this repository by entering the following command in your terminal:

```sh
$ git clone https://gitlab.com/grei-ufc/market-simulation.git
```

Then, go to the folder where the files are stored:

```sh
$ cd market-simulation
```

It is desirable to run the simulation in a [virtual python environment](https://docs.python.org/3/tutorial/venv.html) so there will be no dependency conflict. For this, it's strict recommended the [Anaconda's](https://www.anaconda.com/products/individual) package management: *conda*.

Conda can be to be used for create and manage the virtual environment:

```sh
$ conda create --name = market1 python=3.7
$ source activate market1
```

Once the python virtual environment has been activated, run the dependencies installation command:

```sh
$ pip install -r requirements.txt
```

## External dependencies

To run the simulation it's necessary the installation of some external software tools, they are:
- **PADE with ns-3 simulator integration**: run the command `python setup install` insyde the *pade-cosimul* folder, present in this directory;
- **MyGrid-Mosaik**: run the command `python setup install` insyde the *mosaik-mygrid* folder, present in this directory; 
- [CPLEX](https://drive.google.com/file/d/1K_xpbnIdCkYcMO8UzV5xTBKYvtku8puz/view?usp=drivesdk) optimization solver ;
- [ns-3](https://www.nsnam.org/releases/ns-allinone-3.30.1.tar.bz2) communication simulation;
- [ns-3 Smartgrid Simulator](https://github.com/lucassm/CoSimul_Platform);


## Tips

Some tips are:
- To integrate CPLEX with pyomo in a linux environment, follow [this](https://stackoverflow.com/questions/56667205/cplex-executable-not-found) steps;
- To use the *ns-3 Smartgrid Simulator* install *ns-3* and follow all the instructions described in its GitHub README.md page;
- For *PADE with ns-3 simulator integration* work, two things need to be done:
1. After `python setup install` in the PADE source code directory, set correctly the enviroment variables defined in the CONFIG_NS3_SIMUL.sh file;  
2. use the command `source CONFIG_NS3_SIMUL.sh`.

## Running the co-simulation model

To run the co-simulation will be necessary two terminal sessions:
- In the first terminal session run the agents, executing the following: `pade start-runtime --config_file pade_config.json`. 
- Wait the agents be launched, and then execute the command: `python start_mosaik_sim.py`. The mosaik will start and coordinate the simulator.
- The results of the co-simulation process will be stored in the *data.hdf5* file.


## Description of the whole co-simulation process

The main objective of this co-simulation is to analyses the integration of several prosumers with different Distributed Energetic Resources into the electric distribution grid. 

To coordinate the balance of energy production and consumption a model to market interactions has been defined, and the prosumer has to follow its rules.

The prosumer model is an aggregation of some devices with different characteristics, like:
- random loads
- random distributed generations;
- controlled loads;
- controls generations;
- storage devices.
