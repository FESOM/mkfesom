import f90nml
import os
import argparse
import glob
from netCDF4 import Dataset
from pytest import approx
import pandas as pd

def find_last_year(path, var, runid='fesom'):
    files = glob.glob(os.path.join(path, f'{var}.{runid}.*.nc'))
    if not files:
        raise FileNotFoundError(
            f'There are (yet) no files with variable {var}')
    files.sort()
    last_year = os.path.basename(files[-1]).split('.')[2]
    return int(last_year)


def fcheck():
    parser = argparse.ArgumentParser(prog="fcheck",
                                     description="Check FESOM2 experiment data.")
    parser.add_argument("path", help="Path to work directory")

    parser.add_argument(
        "--abs",
        "-a",
        type=float,
        default=1e-12,
        help="Absolute tolerance",
    )

    args = parser.parse_args()

    nml_config_path = os.path.join(args.path, 'namelist.config')

    if not os.path.exists(nml_config_path):
        raise FileNotFoundError(f'Can\'t gind {nml_config_path}')

    nml = f90nml.read(nml_config_path)
    MeshPath = nml['paths']['MeshPath']
    ResultPath = nml['paths']['ResultPath']
    runid = nml['modelname']['runid']

    fcheck_values_path = os.path.join(args.path, 'fcheck_values.csv')
    if not fcheck_values_path:
        raise FileNotFoundError(f'Can\'t gind {fcheck_values_path}.')

    ds = pd.read_csv('./fcheck_values.csv', index_col=0)

    valid = True
    for variable in ds.index:
        last_year = find_last_year(ResultPath, variable, runid)
        ffile = Dataset(f'{ResultPath}/{variable}.{runid}.{last_year}.nc')
        current_value = ffile.variables[variable][:].mean()
        master_value = ds.loc[variable].values[0]
        print(f"Variable: {variable}, current_value: {current_value}, master_value: {master_value}")
        try:
            assert current_value == approx(master_value, abs = args.abs)
        except:
            print(f'FAIL!!!: DIFFERENCE: {current_value-master_value}. For {variable} we got {current_value}. Got {master_value} instead.')
            valid = False
    if not valid:
        raise AssertionError('One or several tests have failed.')


if __name__ == "__main__":
    # args = parser.parse_args()
    # args.func(args)
    fcheck()
