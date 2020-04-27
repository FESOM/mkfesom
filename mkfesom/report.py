import argparse
import pandas as pd
import os
import numpy as np
import pandas as pd
import re
from collections import OrderedDict
import pprint as pp
from tabulate import tabulate
import time


def parce(ifile):
    dc = OrderedDict()
    CFL = OrderedDict()
    stat = OrderedDict()
    fl = open(ifile)
    iterations = []
    residuum = []
    dc['status'] = "NOT FINISHED"
    dc['restart'] = "Cold start"
    for line in fl.readlines():
        if "Runtime for all timesteps :" in line:
            dc['status'] = "FINISHED"
            dc['Total time'] = "{} sec, (~{:6.2f}) min".format(
                line.split()[5],
                float(line.split()[5]) / 60)
        elif "STOP" in line:
            dc['status'] = "Stopped (probably blew up)"
        elif "MODEL BLOW UP !!!" in line:
            dc['status'] = "MODEL BLOWED UP !!!"
        elif "time step size is set to" in line:
            dc['time step'] = float(line.split()[6])
        elif "clock restarted at time:" in line:
            dc['restart'] = "/".join(
                (line.split()[5], line.split()[6], line.split()[7]))
        elif "WARNING CFLz>1" in line:
            CFLz_max = line.split('=')[1].split(',')[0]
            mstep = line.split('=')[2].split(',')[0]
            glon = line.split('=')[3].split('/')[0]
            glat = line.split('=')[3].split('/')[1].split(',')[0]
            nz = line.split('=')[4]
            lonlat = f"{glon}/{glat}"
            if lonlat not in CFL:
                CFL[lonlat] = OrderedDict()
                CFL[lonlat]['mstep'] = []
                CFL[lonlat]['nz'] = []
                CFL[lonlat]['CFLz_max'] = []
                CFL[lonlat]['glon'] = []
                CFL[lonlat]['glat'] = []
            CFL[lonlat]['mstep'].append(int(mstep))
            CFL[lonlat]['nz'].append(int(nz))
            CFL[lonlat]['CFLz_max'].append(float(CFLz_max))
            CFL[lonlat]['glon'].append(float(glon))
            CFL[lonlat]['glat'].append(float(glat))
        elif "FESOM step:" in line:
            step = line.split()[2]
            stat[step] = {}
            stat[step]["day"] = line.split()[4]
            stat[step]["year"] = line.split()[6]

    if CFL:
        CFL_points = pd.DataFrame()
        for i in CFL.items():
            point = pd.DataFrame(i[1])
            point['occurence'] = int(point.shape[0])
            CFL_points = pd.concat([CFL_points, point.mean()],
                                   axis=1,
                                   sort=False)
    else:
        CFL_points = None

    fl.close()
    return dc, CFL_points, stat

def file_age(filename):
    st=os.stat('./examples/finished.out')
    age=(time.time()-st.st_mtime)

    return(age)

def report():
    parser = argparse.ArgumentParser(
        prog="report", description="Report on FESOM2 experiment.")
    parser.add_argument("path", help="Path to work directory")
    parser.add_argument(
        "--log",
        "-l",
        type=str,
        default="fesom2.0.out",
        help="Name of the FESOM2 log file",
    )

    args = parser.parse_args()
    logfile = os.path.join(args.path, args.log)
    dc, CFL_points, stat = parce(logfile)
    age = file_age(logfile)

    print('\n')
    print(f'File {logfile} was accessed {int(age)} sec ago \n')
    if len(stat) > 0:
        print(pd.DataFrame(stat).T.iloc[[0, -1]].to_markdown())
        print('\n')
    else:
        print("No info on timesteps yet. \n")

    print(pd.DataFrame(dc, index=[' ']).to_markdown())
    print('\n')
    # pp.pprint(CFL)
    # pp.pprint(dc)
    if CFL_points is not None:
        print(
            CFL_points.T.sort_values('occurence',
                                     ascending=False).head().to_markdown())
    else:
        print('No CFL conditions, congratulations!')


if __name__ == "__main__":
    # args = parser.parse_args()
    # args.func(args)
    report()