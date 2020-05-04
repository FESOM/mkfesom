#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

from setuptools import setup, find_packages

# with open('README.md') as readme_file:
#     readme = readme_file.read()

# with open('HISTORY.rst') as history_file:
#     history = history_file.read()

requirements = ['numpy', 'pandas', 'pyyaml', 'f90nml', 'tabulate', 'netCDF4']

setup_requirements = ['pytest-runner', ]

test_requirements = ['pytest', ]

setup(
    author="FESOM team",
    author_email='koldunovn@gmail.com',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    entry_points={
    'console_scripts': [
        'mkrun=mkfesom.mkrun:mkrun',  # command=package.module:function
        'report=mkfesom.report:report',  # command=package.module:function
        'fcheck=mkfesom.fcheck:fcheck',
    ],
    },
    description="FESOM2 runc creation",
    install_requires=requirements,
    license="MIT license",
    # long_description=readme + '\n\n' + history,
    include_package_data=True,
    keywords='mkfesom',
    name='mkfesom',
    packages=find_packages(include=['mkfesom']),
    package_dir={'mypkg': 'mkfesom'},
    package_data={'': ['*.yml']},
    setup_requires=setup_requirements,
    test_suite='tests',
    tests_require=test_requirements,
    url='https://github.com/koldunovn/mkfesom',
    version='0.1.0',
    zip_safe=False,
)
