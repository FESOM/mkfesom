# mkfesom

Python tools to simplify creation and testing of [FESOM2](https://github.com/FESOM/fesom2) runs.

## Installation

### latest from source:

Prerequisites are: numpy, pandas, pyyaml, f90nml, tabulate, netCDF4, pytest. If some are missing, they should be installed by `pip`. 
```
git clone https://github.com/FESOM/mkfesom.git
cd mkfesom
pip install -e .
```

### Basic usage

The `mkfesom` will use information from `fesom2/setups/` folder to create FESOM2 setup, based on one of the provided standard setups. In particular it will put proper paths to folders with meshes, forcing and hydrography files and create output directory with `fesom.clock` in it. As a minimum you should provide name of the experiment and name of the base setup to `mkfesom`:

```
mkrun myexperiment core2
```

This will create `work_myexperiment` folder with namelists and job script for current machine. Namelists will have all the settings changed for the curernt machine and setup. Also the output folder `output_myexperiment` will be created with `fesom.clock` file. At this point you are ready to submit the job script and run your experiment.

### More options

The `-f` option allows to change default forcing for the experiment:
```
mkrun myexperiment core2 -f ERA5
```
Available forcings are `CORE2`, `JRA55` and `ERA5`. Some forcings require changes not only in `namelist.forcing`, those changes will be listed.

The `-m` option allow to specify machines if it can't be determined automatically:
```
mkrun myexperiment core2 -m docker
```
Available options are `ollie`, `mistral`, `docker`. One can easilly add the machine (see below).

The `-b` option creates additional `bin` directory and put path to this directory in the jobscript.
```
mkrun myexperiment core2 -n
```
This will create `bin_myexperiment` directory (you have to copy executable there by yourself). One can use it when testing different executables. 

### Add machine or forcing

You can easilly do this by modifying `paths.yml` and `forcings.yml` files from `fesom2/setups/` direcrory. 

To add a machine, just add an entry to the `paths.yml` and change paths to meshes, forcings and climatology data and output paths. The easiest way is to base your setup on `docker` entry. Then you can ether specify your machine with `-m` option when create a setup, or you can provide `lnodename`, that is a list of regular expressions to find your host name.

To add a forcing you should just add another entry to `forcings.yml`. Note that currently all forcing files should be located in the same directory (including runoff and restoring files). You have a possibility to define changes in `namelist.config` and `namelist.ice` that should be made in order to use the forcing properly.

