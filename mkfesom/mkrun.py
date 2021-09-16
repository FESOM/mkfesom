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
import pandas as pd

# this part is from https://stackoverflow.com/a/55301129
# allows to expand environment variables in paths
# Note that paths shouls not be surrouned by quatation marks
# otherwise they are treated like strings.

path_matcher = re.compile(r".*\$\{([^}^{]+)\}.*")


def path_constructor(loader, node):
    return os.path.expandvars(node.value)


class EnvVarLoader(yaml.SafeLoader):
    pass


EnvVarLoader.add_implicit_resolver("!path", path_matcher, None)
EnvVarLoader.add_constructor("!path", path_constructor)


def create_workpath(work_path):
    if not os.path.exists(work_path):
        os.makedirs(work_path)
    else:
        # answer = input('the directory {} exist, delete? [y/N]: '.format(work_path))
        answer = "y"
        if answer == "y":
            rmtree(work_path)
            os.makedirs(work_path)
        else:
            print("The script will end here, nothing is done.")
            exit()


def read_yml(yml_path):
    with open(yml_path) as f:
        docs = yaml.load(f, Loader=EnvVarLoader)
    return docs


def meshpath(paths, config, machine):
    if config["mesh"] not in paths[machine]["meshes"]:
        print(
            "The mesh {} is not recognised for {}. \
            Add it's path to ./example/paths.yml".format(
                config["mesh"], machine
            )
        )
        exit()
    mesh_path = os.path.join(paths[machine]["meshes"][config["mesh"]], "")
    if not os.path.exists(mesh_path):
        print(
            "Path to the mesh {} is specified, but it does not exist on this machine.".format(
                config["mesh"]
            )
        )
    return os.path.abspath(mesh_path) + os.path.sep


def resultpath(paths, config, machine, runname):

    if "opath" not in paths[machine]:
        print("The configuration for {} do not have 'opath'".format(paths[machine]))
        exit()

    result_path = os.path.join(
        paths[machine]["opath"]["opath"], "output_{}".format(runname)
    )

    if not os.path.exists(result_path):
        os.makedirs(result_path)
    else:
        answer = "y"
        # answer = input(
        #     'The path {} exist. Delete it? [y/N] '.format(result_path))
        if answer == "y":
            rmtree(result_path)
            os.makedirs(result_path)
        else:
            print("The script will end here.")
            exit()

    return os.path.abspath(result_path) + os.path.sep


def climatedatapath(paths, config, machine):

    if config["clim"]["type"] not in paths[machine]["clim"]:
        print(
            "The climatology {} is not set for {} ".format(
                config["clim"]["type"], machine
            )
        )
        exit()

    climate_data_path = os.path.join(paths[machine]["clim"][config["clim"]["type"]])

    clim_files = []
    for clim_file in config["clim"]["filelist"]:
        clim_file_path = os.path.join(climate_data_path, clim_file)
        clim_files.append(clim_file_path)

    for clim_file_path in clim_files:
        if not os.path.exists(clim_file_path):
            print(
                "There is no {} file in Climate data path ({})".format(
                    clim_file_path, climate_data_path
                )
            )

    return os.path.abspath(climate_data_path) + os.path.sep


def forcing_addpaths(paths, config, forcing, forcing_name, machine):
    for key in forcing["nam_sbc"]:
        if "file" in key:
            # print()
            forcing_path = os.path.join(
                paths[machine]["forcing"][forcing_name], forcing["nam_sbc"][key]
            )
            forcing["nam_sbc"][key] = os.path.abspath(forcing_path)
    return forcing


def forcing_additional_switches(forcing):
    """Reads additional switches related to other namelists."""

    forcing_related_switches = {}
    if "namelist.config" in forcing:
        forcing_related_switches["namelist.config"] = forcing["namelist.config"]
    if "namelist.ice" in forcing:
        forcing_related_switches["namelist.ice"] = forcing["namelist.ice"]
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
                        f"The {switch} parameter in the {namelist_name} has different recomended value in the forcing configuration: ({forcing_related_switches[namelist_name][section][switch]}). I assume you know what you are doing and keep the value from experiment setup ({patch_nml[section][switch]})."
                    )
                # if switch is not explicitly set in the experiment setup,
                # we change it to recomended value from the forcing.
                else:
                    patch_nml[section][switch] = forcing_related_switches[
                        namelist_name
                    ][section][switch]
                    print(
                        f"The {switch} parameter in the {namelist_name} was changed according to the changes reqired by the forcing."
                    )
    return patch_nml


def create_fesom_clock(result_path, path_to_namelistconfig):
    nml = f90nml.read(path_to_namelistconfig)
    timenew = nml["clockinit"]["timenew"]
    daynew = nml["clockinit"]["daynew"]
    yearnew = nml["clockinit"]["yearnew"]

    fl = open(os.path.join(result_path, "fesom.clock"), "w")
    fl.write(f"{timenew} {daynew} {yearnew} \n")
    fl.write(f"{timenew} {daynew} {yearnew} \n")

    fl.close()


def parce_io(filename, section='nml_list', nml_var="io_list"):
    iolist = f90nml.read(filename)[section][nml_var]
    keys = iolist[0::4]
    freq = iolist[1::4]
    unit = iolist[2::4]
    prec = iolist[3::4]

    io_dict = OrderedDict()
    for key, fre, un, pre in zip(keys, freq, unit, prec):
        io_dict[key] = {}
        io_dict[key]["freq"] = fre
        io_dict[key]["unit"] = un
        io_dict[key]["prec"] = pre

    return io_dict


def io_dict2nml(io_dict):
    out_list = []
    for key in io_dict:
        out_list.append(key)
        out_list.append(io_dict[key]["freq"])
        out_list.append(io_dict[key]["unit"])
        out_list.append(io_dict[key]["prec"])
    return out_list


def simple_patch(config, work_path, namelist):
    if namelist in config:
        patch_nml = config[namelist]
        if patch_nml == None:
            copy("./config/{}".format(namelist), "{}/{}".format(work_path, namelist))
        else:
            f90nml.patch(
                "./config/{}".format(namelist),
                patch_nml,
                "{}/{}".format(work_path, namelist),
            )
    else:
        try:
            copy("./config/{}".format(namelist), "{}/{}".format(work_path, namelist))
        except:
            print(f"You are trying to copy {namelist} from config, but it does not exist.")


def find_machine(paths):
    machine = None
    for host in paths:
        if "lnodename" in paths[host]:
            for pattern in paths[host]["lnodename"]:
                if re.match(pattern, socket.gethostname()):
                    if machine is None:
                        machine = host
                elif re.match(pattern, socket.getfqdn()):
                    if machine is None:
                        machine = host

    if machine == None:
        print(
            """Your hostname is {}.
        No matching host patterns was found in settings/paths.yml.
        Please provide name of the host explicitly with -m command,
        or add corresponding host pattern to settings/paths.yml.""".format(
                socket.gethostname()
            )
        )
        exit()
    else:
        return machine


def make_executable(path):
    # taken from https://stackoverflow.com/questions/12791997/how-do-you-do-a-simple-chmod-x-from-within-python
    mode = os.stat(path).st_mode
    mode |= (mode & 0o444) >> 2  # copy R bits to X
    os.chmod(path, mode)


def runscript_slurm(config, machine, runname, newbin="bin", account=None):

    if "ntasks" in config:
        ntasks = config["ntasks"]
    else:
        ntasks = None

    if "time" in config:
        time = config["time"]
    else:
        time = None

    work_path = "./work_{}".format(runname)
    job_name = "fes_{}".format(runname)

    if os.path.exists(f"./work/job_{machine}"):
        ipath = f"./work/job_{machine}"
    else:
        ipath = f"./work/job_ubuntu"

    opath = "{}/job_{}_new".format(work_path, machine)

    ifile = open(ipath, "r")
    ofile = open(opath, "w")

    for line in ifile.readlines():
        if line.startswith("#SBATCH --job-name"):
            ofile.write("#SBATCH --job-name={}\n".format(job_name))
        elif line.startswith("#SBATCH --ntasks="):
            if ntasks:
                ofile.write("#SBATCH --ntasks={}\n".format(ntasks))
        elif line.startswith("#SBATCH --time"):
            if time:
                ofile.write("#SBATCH --time={}\n".format(time))
        elif line.startswith("#SBATCH -A"):
            if account:
                ofile.write("#SBATCH -A {}\n".format(account))
        elif line.startswith("ln -s ../bin/fesom.x"):
            ofile.write("ln -s ../{}/fesom.x .\n".format(newbin))
        else:
            ofile.write(line)
    ifile.close()
    ofile.close()
    make_executable(opath)


def patch_io(config):
    if "namelist.io" in config:
        patch_nml = config["namelist.io"]
        # parce the crazy io_list from default file
        if patch_nml is not None:
            if "nml_list" in patch_nml:
                io_dict = parce_io("./config/namelist.io", "nml_list", "io_list")
                # get the infromation from experiment setup
                diff_in_vars = patch_nml["nml_list"]["io_list"]
                # modify information from original io_list
                for key in diff_in_vars:
                    io_dict[key] = diff_in_vars[key]
                # convert io_list back to the format f90nml can work with (a long list)
                patch_nml["nml_list"]["io_list"] = io_dict2nml(io_dict)
        else:
            patch_nml = {}
    else:
        patch_nml = {}
    return patch_nml

def patch_icepack(config):
    if "namelist.icepack" in config:
        patch_nml = config["namelist.icepack"]
        # parce the crazy io_list from default file
        if patch_nml is not None:
            if "nml_list_icepack" in patch_nml:
                io_dict = parce_io("./config/namelist.icepack", "nml_list_icepack", "io_list_icepack")
                # get the infromation from experiment setup
                diff_in_vars = patch_nml["nml_list_icepack"]["io_list_icepack"]
                # modify information from original io_list
                for key in diff_in_vars:
                    io_dict[key] = diff_in_vars[key]
                # convert io_list back to the format f90nml can work with (a long list)
                patch_nml["nml_list_icepack"]["io_list_icepack"] = io_dict2nml(io_dict)
        else:
            patch_nml = {}
    else:
        patch_nml = {}
    return patch_nml

def add_ini(config):
    "Add initial conditions"
    if "namelist.oce" in config:
        if "oce_init3d" in config["namelist.oce"]:
            config["namelist.oce"]["oce_init3d"]["filelist"] = config["clim"][
                "filelist"
            ]
            config["namelist.oce"]["oce_init3d"]["varlist"] = config["clim"]["varlist"]
        else:
            config["namelist.oce"]["oce_init3d"] = {}
            config["namelist.oce"]["oce_init3d"]["filelist"] = config["clim"][
                "filelist"
            ]
            config["namelist.oce"]["oce_init3d"]["varlist"] = config["clim"]["varlist"]
    else:
        config["namelist.oce"] = {}
        config["namelist.oce"]["oce_init3d"] = {}
        config["namelist.oce"]["oce_init3d"]["filelist"] = config["clim"]["filelist"]
        config["namelist.oce"]["oce_init3d"]["varlist"] = config["clim"]["varlist"]

    if "namelist.tra" in config:
        if "tracer_init3d" in config["namelist.tra"]:
            config["namelist.tra"]["tracer_init3d"]["filelist"] = config["clim"][
                "filelist"
            ]
            config["namelist.tra"]["tracer_init3d"]["varlist"] = config["clim"]["varlist"]
        else:
            config["namelist.tra"]["tracer_init3d"] = {}
            config["namelist.tra"]["tracer_init3d"]["filelist"] = config["clim"][
                "filelist"
            ]
            config["namelist.tra"]["tracer_init3d"]["varlist"] = config["clim"]["varlist"]
    else:
        config["namelist.tra"] = {}
        config["namelist.tra"]["tracer_init3d"] = {}
        config["namelist.tra"]["tracer_init3d"]["filelist"] = config["clim"]["filelist"]
        config["namelist.tra"]["tracer_init3d"]["varlist"] = config["clim"]["varlist"]
    return config



def mkrun():
    parser = argparse.ArgumentParser(
        prog="mkrun", description="Prepear FESOM2 experiment."
    )
    parser.add_argument("runname", help="Name of the run")
    parser.add_argument("parent", help="Name of the parent run (from examples)")
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
    parser.add_argument(
        "--forcing",
        "-f",
        type=str,
        help="Option to change forcing indicated in the experiment setup.",
    )

    args = parser.parse_args()

    if not os.path.exists("./config/namelist.config"):
        raise FileNotFoundError(
            "There is no ./config/namelist.config file. \n\
            Are you sure you in the FESOM2 directory?"
        )

    work_path = "./work_{}".format(args.runname)
    create_workpath(work_path)

    if args.account:
        account = args.account
    else:
        account = None

    if not args.newbin:
        newbin = "bin"
    else:
        newbin = "bin_{}".format(args.runname)
        create_workpath(newbin)

    #    paths_path = pkg_resources.resource_filename(__name__,
    #                                                 'settings/paths.yml')
    paths_path = "./setups/paths.yml"

    paths = read_yml(paths_path)
    # print(paths['ollie']['meshes'])
    # setup_path = pkg_resources.resource_filename(
    #    __name__, 'settings/{}/setup.yml'.format(args.parent))
    setup_path = "./setups/{}/setup.yml".format(args.parent)
    config = read_yml(setup_path)

    # forcings_path = pkg_resources.resource_filename(__name__,
    #                                                'settings/forcings.yml')
    forcings_path = "./setups/forcings.yml"
    forcings = read_yml(forcings_path)
    if args.forcing:
        forcing_name = args.forcing
    else:
        forcing_name = config["forcing"]
    forcing = forcings[forcing_name]
    # print(runconf['namelist.config'])

    if not args.machine:
        machine = find_machine(paths)
    else:
        machine = args.machine

    # namelist.forcing (should not be in setup.yml, taken from forcings.yml)
    forcing = forcing_addpaths(paths, config, forcing, forcing_name, machine)
    forcing_related_switches = forcing_additional_switches(forcing)

    patch_nml = forcing
    f90nml.patch(
        "./config/namelist.forcing", patch_nml, "{}/namelist.forcing".format(work_path)
    )

    # namelist.config
    patch_nml = config["namelist.config"]
    patch_nml["paths"] = {}
    patch_nml["paths"]["MeshPath"] = meshpath(paths, config, machine)
    result_path = resultpath(paths, config, machine, args.runname)
    patch_nml["paths"]["ResultPath"] = result_path
    patch_nml["paths"]["ClimateDataPath"] = climatedatapath(paths, config, machine)

    patch_nml = apply_forcing_switches(
        patch_nml, forcing_related_switches, "namelist.config"
    )

    f90nml.patch(
        "./config/namelist.config", patch_nml, "{}/namelist.config".format(work_path)
    )

    create_fesom_clock(result_path, "{}/namelist.config".format(work_path))

    config = add_ini(config)
    simple_patch(config, work_path, "namelist.oce")
    simple_patch(config, work_path, "namelist.ice")
    simple_patch(config, work_path, "namelist.cvmix")
    simple_patch(config, work_path, "namelist.tra")
    # simple_patch(config, work_path, "namelist.icepack")

    # namelist.io
    patch_nml = patch_io(config)
    # patch the file
    if patch_nml:
        f90nml.patch(
            "./config/namelist.io", patch_nml, "{}/namelist.io".format(work_path)
        )
    else:
        copy("./config/namelist.io", "{}/namelist.io".format(work_path))
        
    patch_nml = patch_icepack(config)
    if patch_nml:
        f90nml.patch(
            "./config/namelist.icepack", patch_nml, "{}/namelist.icepack".format(work_path)
        )
    else:
        copy("./config/namelist.icepack", "{}/namelist.icepack".format(work_path))


    runscript_slurm(config, machine, args.runname, newbin, account=account)

    if "fcheck" in config:
        fcheck = {}
        fcheck["fcheck"] = config["fcheck"]
        df = pd.DataFrame(fcheck)
        df.to_csv(f"{work_path}/fcheck_values.csv")


if __name__ == "__main__":
    mkrun()
