import f90nml
import os
import argparse
import glob
from netCDF4 import Dataset
from pytest import approx


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

    args = parser.parse_args()

    nml_config_path = os.path.join(args.path, 'namelist.config')

    if not os.path.exists(nml_config_path):
        raise FileNotFoundError(f'Can\'t gind {nml_config_path}')

    nml = f90nml.read(nml_config_path)
    MeshPath = nml['paths']['MeshPath']
    ResultPath = nml['paths']['ResultPath']
    runid = nml['modelname']['runid']

    print(MeshPath)
    print(ResultPath)
    print(runid)

    fcheck_values_path = os.path.join(args.path, 'fcheck_values.csv')
    if not fcheck_values_path:
        raise FileNotFoundError(f'Can\'t gind {fcheck_values_path}.')

    ds = pd.read_csv('./fcheck_values.csv', index_col=0)

    last_year = find_last_year(ResultPath, variable, runid)
    for variable in ds.index:
        ffile = Dataset(f'{}/{variable}.{runid}.{last_year}.nc')
        current_value = ffile.variables[variable][:].mean()
        master_value = ds.loc[variable].values[0]
        assert current_value == pytest.approx(master_value)


if __name__ == "__main__":
    # args = parser.parse_args()
    # args.func(args)
    fcheck()