import f90nml
import os
import argparse
import glob
# import pyfesom2 as pf


def find_last_year(path, var, runid='fesom'):
    files = glob.glob(os.path.join(path, f'{var}.{runid}.*.nc'))
    if not files:
        raise FileNotFoundError(
            f'There are (yet) no files with variable {var}')
    files.sort()
    last_year = os.path.basename(files[-1]).split('.')[2]
    return int(last_year)


def monitor():
    parser = argparse.ArgumentParser(prog="monitor",
                                     description="Monitor FESOM2 experiment.")
    parser.add_argument("path", help="Path to work directory")

    # parser.add_argument(
    #     "--log",
    #     "-l",
    #     type=str,
    #     default="fesom2.0.out",
    #     help="Name of the FESOM2 log file",
    # )

    args = parser.parse_args()

    nml_config_path = os.path.join(args.path, 'namelist.config')

    if not os.path.exists(nml_config_path):
        raise FileNotFoundError(f'Can\'t gind {nml_config_path}')

    nml = f90nml.read(nml_config_path)
    MeshPath = nml['paths']['MeshPath']
    ResultPath = nml['paths']['ResultPath']
    rotation = nml['geometry']['force_rotation']

    if rotation:
        abg = [0,0,0]
    else:
        abg = [50, 15, -90]

    print(MeshPath)
    print(ResultPath)

    # mesh = pf.load_mesh('/Users/koldunovn/PYHTON/DATA/LCORE_MESH/',
    #                     abg=abg)
    # for variable in ['salt', 'temp', 'a_ice', 'm_ice']:
    #     last_year = find_last_year(ResultPath, variable)
    #     print(last_year)
    #     data = pf.get_data(ResultPath, variable, last_year, mesh, records=[-1], how=None, compute=False)
    #     print(data.mean().compute().data)
    # temperature



if __name__ == "__main__":
    # args = parser.parse_args()
    # args.func(args)
    monitor()