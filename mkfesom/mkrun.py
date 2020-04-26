import f90nml
import os
from shutil import copy, rmtree
import sys
import argparse
import yaml
from collections import OrderedDict
import re
import socket
import pkg_resources

# this part is from https://stackoverflow.com/a/55301129
# allows to expand environment variables in paths
# Note that paths shouls not be surrouned by quatation marks
# otherwise they are treated like strings.

path_matcher = re.compile(r'.*\$\{([^}^{]+)\}.*')


def path_constructor(loader, node):
    return os.path.expandvars(node.value)


class EnvVarLoader(yaml.SafeLoader):
    pass


EnvVarLoader.add_implicit_resolver('!path', path_matcher, None)
EnvVarLoader.add_constructor('!path', path_constructor)


def create_workpath(work_path):
    if not os.path.exists(work_path):
        os.makedirs(work_path)
    else:
        # answer = input('the directory {} exist, delete? [y/N]: '.format(work_path))
        answer = 'y'
        if answer == 'y':
            rmtree(work_path)
            os.makedirs(work_path)
        else:
            print('The script will end here, nothing is done.')
            exit()


def read_yml(yml_path):
    with open(yml_path) as f:
        docs = yaml.load(f, Loader=EnvVarLoader)
    return docs


def meshpath(paths, config, machine):
    if config['mesh'] not in paths[machine]['meshes']:
        print("The mesh {} is not recognised for {}. \
            Add it's path to ./example/paths.yml".format(
            config['mesh'], machine))
        exit()
    mesh_path = os.path.join(paths[machine]['meshes'][config['mesh']], '')
    if not os.path.exists(mesh_path):
        print(
            'Path to the mesh {} is specified, but it does not exist on this machine.'
            .format(config['mesh']))
    return os.path.abspath(mesh_path) + os.path.sep


def resultpath(paths, config, machine, runname):

    if 'opath' not in paths[machine]:
        print("The configuration for {} do not have 'opath'".format(
            paths[machine]))
        exit()

    result_path = os.path.join(paths[machine]['opath']['opath'],
                               'output_{}'.format(runname))

    if not os.path.exists(result_path):
        os.makedirs(result_path)
    else:
        answer = 'y'
        # answer = input(
        #     'The path {} exist. Delete it? [y/N] '.format(result_path))
        if answer == 'y':
            rmtree(result_path)
            os.makedirs(result_path)
        else:
            print('The script will end here.')
            exit()

    return os.path.abspath(result_path) + os.path.sep


def climatedatapath(paths, config, machine):

    if config['clim']['type'] not in paths[machine]['clim']:
        print("The climatology {} is not set for {} ".format(
            config['clim']['type'], machine))
        exit()

    climate_data_path = os.path.join(
        paths[machine]['clim'][config['clim']['type']])
    clim_file = os.path.join(climate_data_path, config['clim']['file'])

    if not os.path.exists(clim_file):
        print('There is no {} file in Climate data path ({})'.format(
            config['clim']['file'], climate_data_path))

    return os.path.abspath(climate_data_path) + os.path.sep


def forcing_addpaths(paths, config, forcing, machine):
    for key in forcing['nam_sbc']:
        if "file" in key:
            # print()
            forcing['nam_sbc'][key] = os.path.join(
                paths[machine]['forcing'][config['forcing']],
                forcing['nam_sbc'][key])
    return forcing


def forcing_additional_switches(forcing):
    '''Reads additional switches related to other namelists.'''

    forcing_related_switches = {}
    if 'namelist.config' in forcing:
        forcing_related_switches['namelist.config'] = forcing[
            'namelist.config']
    if 'namelist.ice' in forcing:
        forcing_related_switches['namelist.ice'] = forcing['namelist.ice']
    return forcing_related_switches


def apply_forcing_switches(patch_nml, forcing_related_switches, namelist_name):
    if namelist_name in forcing_related_switches:
        for section in forcing_related_switches[namelist_name]:
            if section not in patch_nml:
                patch_nml[section] = {}
            for switch in forcing_related_switches[namelist_name][section]:
                # values from experiment setup has priority
                if switch in patch_nml[section]:
                    print(
                        f'The {switch} parameter in the {namelist_name} has different recomended value in the forcing configuration: ({forcing_related_switches[namelist_name][section][switch]}). I assume you know what you are doing and keep the value from experiment setup ({patch_nml[section][switch]}).'
                    )
                # if switch is not explicitly set in the experiment setup,
                # we change it to recomended value from the forcing.
                else:
                    patch_nml[section][switch] = forcing_related_switches[
                        namelist_name][section][switch]
                    print(
                        f'The {switch} parameter in the {namelist_name} was changed according to the changes reqired by the forcing.'
                    )
    return patch_nml

def create_fesom_clock(result_path, path_to_namelistconfig):
    nml = f90nml.read(path_to_namelistconfig)
    timenew = nml['clockinit']['timenew']
    daynew  = nml['clockinit']['daynew']
    yearnew = nml['clockinit']['yearnew']

    fl = open(os.path.join(result_path, 'fesom.clock'), 'w')
    fl.write(f'{timenew} {daynew} {yearnew} \n')
    fl.write(f'{timenew} {daynew} {yearnew} \n')

    fl.close()

def parce_io(filename):
    iolist = f90nml.read(filename)['nml_list']['io_list']
    keys = iolist[0::4]
    freq = iolist[1::4]
    unit = iolist[2::4]
    prec = iolist[3::4]

    io_dict = OrderedDict()
    for key, fre, un, pre in zip(keys, freq, unit, prec):
        io_dict[key] = {}
        io_dict[key]['freq'] = fre
        io_dict[key]['unit'] = un
        io_dict[key]['prec'] = pre

    return io_dict


def io_dict2nml(io_dict):
    out_list = []
    for key in io_dict:
        out_list.append(key)
        out_list.append(io_dict[key]['freq'])
        out_list.append(io_dict[key]['unit'])
        out_list.append(io_dict[key]['prec'])
    return out_list


def simple_patch(config, work_path, namelist):
    if namelist in config:
        patch_nml = config[namelist]
        if patch_nml == None:
            copy('./config/namelist.oce', '{}/{}'.format(work_path, namelist))
        else:
            f90nml.patch('./config/namelist.oce', patch_nml,
                         '{}/{}'.format(work_path, namelist))
    else:
        copy('./config/namelist.oce', '{}/{}'.format(work_path, namelist))


def find_machine(paths):
    machine = None
    for host in paths:
        if 'lnodename' in paths[host]:
            for pattern in paths[host]['lnodename']:
                if re.match(pattern, socket.gethostname()):
                    if machine is None:
                        machine = host
                elif re.match(pattern, socket.getfqdn()):
                    if machine is None:
                        machine = host

    if machine == None:
        print("""Your hostname is {}.
        No matching host patterns was found in settings/paths.yml.
        Please provide name of the host explicitly with -m command,
        or add corresponding host pattern to settings/paths.yml.""".format(
            socket.gethostname()))
        exit()
    else:
        return machine


def runscript_slurm(config, machine, runname, newbin='bin', account=None):

    if 'ntasks' in config:
        ntasks = config['ntasks']
    else:
        ntasks = None

    if 'time' in config:
        time = config['time']
    else:
        time = None

    work_path = './work_{}'.format(runname)
    job_name = 'fes_{}'.format(runname)

    ipath = f'./work/job_{machine}'
    opath = '{}/job_{}_new'.format(work_path, machine)

    ifile = open(ipath, 'r')
    ofile = open(opath, 'w')

    for line in ifile.readlines():
        if line.startswith('#SBATCH --job-name'):
            ofile.write('#SBATCH --job-name={}\n'.format(job_name))
        elif line.startswith('#SBATCH --ntasks'):
            if ntasks:
                ofile.write('#SBATCH --ntasks={}\n'.format(ntasks))
        elif line.startswith('#SBATCH --time'):
            if time:
                ofile.write('#SBATCH --time={}\n'.format(time))
        elif line.startswith('#SBATCH -A'):
            if account:
                ofile.write('#SBATCH -A {}\n'.format(account))
        elif line.startswith('ln -s ../bin/fesom.x'):
            ofile.write('ln -s ../{}/fesom.x .\n'.format(newbin))
        else:
            ofile.write(line)
    ifile.close()
    ofile.close()


def mkrun():
    parser = argparse.ArgumentParser(prog="mkrun",
                                     description="Prepear FESOM2 experiment.")
    parser.add_argument("runname", help="Name of the run")
    parser.add_argument("parent",
                        help="Name of the parent run (from examples)")
    parser.add_argument(
        "--machine",
        "-m",
        type=str,
        help="Name of the host. Should be in ./examples/paths.yml",
    )
    parser.add_argument(
        "--account",
        "-a",
        type=str,
        help="Account",
    )
    parser.add_argument(
        "--newbin",
        "-n",
        action="store_true",
        help="If present separate bin directory will be created.",
    )

    args = parser.parse_args()

    if not os.path.exists('./config/namelist.config'):
        raise FileNotFoundError('There is no ./config/namelist.config file. \n\
            Are you sure you in the FESOM2 directory?')

    work_path = './work_{}'.format(args.runname)
    create_workpath(work_path)

    if args.account:
        account = args.account
    else:
        account = None

    if not args.newbin:
        newbin = 'bin'
    else:
        newbin = 'bin_{}'.format(args.runname)
        create_workpath(newbin)

    paths_path = pkg_resources.resource_filename(__name__,
                                                 'settings/paths.yml')
    paths = read_yml(paths_path)
    # print(paths['ollie']['meshes'])
    setup_path = pkg_resources.resource_filename(
        __name__, 'settings/{}/setup.yml'.format(args.parent))
    config = read_yml(setup_path)

    forcings_path = pkg_resources.resource_filename(__name__,
                                                    'settings/forcings.yml')
    forcings = read_yml(forcings_path)
    forcing = forcings[config['forcing']]
    # print(runconf['namelist.config'])

    if not args.machine:
        machine = find_machine(paths)
    else:
        machine = args.machine

    # namelist.forcing (should not be in setup.yml, taken from forcings.yml)
    forcing = forcing_addpaths(paths, config, forcing, machine)
    forcing_related_switches = forcing_additional_switches(forcing)

    patch_nml = forcing
    f90nml.patch('./config/namelist.forcing', patch_nml,
                 '{}/namelist.forcing'.format(work_path))

    # namelist.config
    patch_nml = config['namelist.config']
    patch_nml['paths'] = {}
    patch_nml['paths']['MeshPath'] = meshpath(paths, config, machine)
    result_path = resultpath(paths, config, machine, args.runname)
    patch_nml['paths']['ResultPath'] = result_path
    patch_nml['paths']['ClimateDataPath'] = climatedatapath(
        paths, config, machine)

    patch_nml = apply_forcing_switches(patch_nml, forcing_related_switches,
                                       'namelist.config')

    f90nml.patch('./config/namelist.config', patch_nml,
                 '{}/namelist.config'.format(work_path))

    create_fesom_clock(result_path, '{}/namelist.config'.format(work_path))

    simple_patch(config, work_path, 'namelist.oce')
    simple_patch(config, work_path, 'namelist.ice')
    simple_patch(config, work_path, 'namelist.cvmix')

    # namelist.io
    patch_nml = config['namelist.io']
    # parce the crazy io_list from default file
    io_dict = parce_io('./config/namelist.io')
    # get the infromation from experiment setup
    diff_in_vars = patch_nml['nml_list']['io_list']
    # modify information from original io_list
    for key in diff_in_vars:
        io_dict[key] = diff_in_vars[key]
    # convert io_list back to the format f90nml can work with (a long list)
    patch_nml['nml_list']['io_list'] = io_dict2nml(io_dict)
    # patch the file
    f90nml.patch('./config/namelist.io', patch_nml,
                 '{}/namelist.io'.format(work_path))

    runscript_slurm(config, machine, args.runname, newbin, account=None)
    # patch_nml = {'timestep':
    #                    {'step_per_day': step_per_day,
    #                     'run_length': run_lenghth,
    #                     'run_length_unit': run_length_unit},
    #          'paths':
    #                 {'MeshPath': MeshPath,
    #                 'ResultPath': ResultPath,
    #                 'ClimateDataPath': ClimateDataPath},
    #           'geometry':
    #                 {'force_rotation': force_rotation},
    #           'inout':
    #                 {'restart_length': restart_length,
    #                  'restart_length_unit': restart_length_unit}
    #         }

    # with open('./examples/paths.yml') as f:
    #     docs = yaml.load(f)
    #     print(docs['ollie']['meshes'])
    # with open('./examples/{}/setup.yml'.format(args.runname)) as f:
    #     runconf = yaml.load(f)
    # print(runconf)


if __name__ == "__main__":
    # args = parser.parse_args()
    # args.func(args)
    mkrun()

# try:
#     run_name = sys.argv[1]
# except:
#     run_name = "nkolduno"

# machine = 'mistral'
# work_path = './work_{}/'.format(run_name)
# job_name = 'fes_{}'.format(run_name)
# ntasks = 288
# time = '00:30:00'
# account = 'bk0988'

# MeshPath            = '/mnt/lustre01/work/ab0995/a270088/meshes/COREII/'
# ResultPath          = '/scratch/a/a270088/output_{}/'.format(run_name)
# ClimateDataPath     = '/mnt/lustre01/work/ba1035/a270092/input/fesom2/hydrography/'
# ForcingDataPath     = '/pool/data/AWICM/FESOM2/FORCING/CORE2/'
# step_per_day        = 32
# run_lenghth         = 1
# run_length_unit     = 'y'
# force_rotation      = False
# restart_length      = 1
# restart_length_unit = 'y'

# Div_c   = 0.5
# Leith_c = 0.05
# w_split = False

# whichEVP = 0
# evp_rheol_steps = 150

# if not os.path.exists(work_path):
#     os.makedirs(work_path)

# patch_nml = {'timestep':
#                        {'step_per_day': step_per_day,
#                         'run_length': run_lenghth,
#                         'run_length_unit': run_length_unit},
#              'paths':
#                     {'MeshPath': MeshPath,
#                     'ResultPath': ResultPath,
#                     'ClimateDataPath': ClimateDataPath},
#               'geometry':
#                     {'force_rotation': force_rotation},
#               'inout':
#                     {'restart_length': restart_length,
#                      'restart_length_unit': restart_length_unit}
#             }

# f90nml.patch('./config/namelist.config', patch_nml, '{}/namelist.config'.format(work_path))

# patch_nml_oce = {'oce_dyn':
#                            {'Div_c':Div_c,
#                              'Leith_c':Leith_c,
#                              'w_split':w_split}
#                 }

# f90nml.patch('./config/namelist.oce', patch_nml_oce, '{}/namelist.oce'.format(work_path))

# patch_nml_ice = {'ice_dyn':
#                            {'whichEVP':whichEVP,
#                             'evp_rheol_steps':evp_rheol_steps}
#                 }

# f90nml.patch('./config/namelist.ice', patch_nml_ice, '{}/namelist.ice'.format(work_path))

# patch_nml = {'nam_sbc':
#                        {'nm_xwind_file': f'{ForcingDataPath}/u_10.',
#                         'nm_ywind_file': f'{ForcingDataPath}/v_10.',
#                         'nm_humi_file':  f'{ForcingDataPath}/q_10.',
#                         'nm_qsr_file':   f'{ForcingDataPath}/ncar_rad.',
#                         'nm_qlw_file':   f'{ForcingDataPath}/ncar_rad.',
#                         'nm_tair_file':  f'{ForcingDataPath}/t_10.',
#                          'nm_prec_file': f'{ForcingDataPath}/ncar_precip.',
#                          'nm_snow_file': f'{ForcingDataPath}/ncar_precip.',
#                         'nm_mslp_file':  f'{ForcingDataPath}/slp.',
#                         'nm_runoff_file': f'{ForcingDataPath}/runoff.nc',
#                         'nm_sss_data_file': f'{ForcingDataPath}/PHC2_salx.nc'
#                         },
#             }

# f90nml.patch('./config/namelist.forcing', patch_nml, '{}/namelist.forcing'.format(work_path))

# ipath = f'./work/job_{machine}'
# opath = '{}/job_{}_new'.format(work_path, machine)
# newbin = 'bin_{}'.format(run_name)

# ifile = open(ipath, 'r')
# ofile = open(opath, 'w')

# for line in ifile.readlines():
#     if line.startswith('#SBATCH --job-name'):
#         ofile.write('#SBATCH --job-name={}\n'.format(job_name))
#     elif line.startswith('#SBATCH --ntasks'):
#         ofile.write('#SBATCH --ntasks={}\n'.format(ntasks))
#     elif line.startswith('#SBATCH --time'):
#         ofile.write('#SBATCH --time={}\n'.format(time))
#     elif line.startswith('#SBATCH -A'):
#         ofile.write('#SBATCH -A {}\n'.format(account))
#     elif line.startswith('ln -s ../bin/fesom.x'):
#         ofile.write('ln -s ../{}/fesom.x .\n'.format(newbin))
#     else:
#         ofile.write(line)
# ifile.close()
# ofile.close()

# copy('./config/namelist.io', '{}/namelist.io'.format(work_path))
# #copy('./config/namelist.forcing', '{}/namelist.forcing'.format(work_path))
# copy('./config/namelist.cvmix', '{}/namelist.cvmix'.format(work_path))

# if not os.path.exists('./{}'.format(newbin)):
#     os.makedirs('./{}'.format(newbin))

# copy('./bin/fesom.x', './{}/fesom.x'.format(newbin))

# if not os.path.exists(ResultPath):
#     os.makedirs(ResultPath)

# if not os.path.exists(ResultPath+'/fesom.clock'):
#     ofile = open(ResultPath+'/fesom.clock', 'w')
#     ofile.write('0 0 1948\n')
#     ofile.write('0 0 1948\n')
#     ofile.close()