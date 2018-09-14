# market-simulation

> Simulation models to analyse in a electric energy market based in multiagent.

## Explanation

This repository will contain the simulation files referring to an electric energy market system based on the concept of multiagents. The multi-agent system will be implemented using the framework [PADE](https://pade-docs-en.readthedocs.io/en/latest/) and the simulation time, as well as the implementation of some models will be realized using software [ Mosaik](https://mosaik.readthedocs.io/en/latest/).

Developers who contribute to this project should follow the git working model based on * branchs * following the methodology described in this [article](https://nvie.com/posts/a-successful-git-branching-model/) .

## Install

To run the simulation the following steps should be performed:

Download the simulation files contained in this repository by entering the following command in your terminal:

    $ git clone https://github.com/grei-ufc/market-simulation.git

Then, enter the folder where the files were stored:
    
    $ cd market-simulation

It is advisable to run the simulation in a virtual python environment so there is no dependency conflict. It is also advised that Anaconda's package management, the conda, be used in creating and managing the virtual environment:

    $ conda create --name = market1 python
    $ source activate market1

Once the python virtual environment has been activated, run the dependencies installation command:

    $ pip install -r requirements.txt

Now, just run the simulation, using the launcher.py command

    $ python launcher.py
