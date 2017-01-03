#          Copyright Jamie Allsop 2014-2015
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   setup.py
#-------------------------------------------------------------------------------

from setuptools import setup
import os
import cuppa.version

with open( 'README.rst' ) as readme_file:
    long_description = readme_file.read()

setup(
    name             = 'cuppa',
    version          = cuppa.utility.version.get_version(),
    description      = 'Cuppa, an extension package to simplify and extend Scons',
    author           = 'ja11sop',
    url              = 'https://github.com/ja11sop/cuppa',
    license          = 'Boost Software License 1.0 - http://www.boost.org/LICENSE_1_0.txt',
    long_description = long_description,
    packages = [
        'cuppa',
        'cuppa.cpp',
        'cuppa.dependencies',
        'cuppa.dependencies.boost',
        'cuppa.methods',
        'cuppa.modules',
        'cuppa.platforms',
        'cuppa.profiles',
        'cuppa.project_generators',
        'cuppa.scms',
        'cuppa.test_report',
        'cuppa.toolchains',
        'cuppa.variants',
    ],
    package_data = {
        'cuppa': [
            'VERSION',
            os.path.join( 'dependencies','boost','boost_test_patch.diff' )
        ]
    },
    install_requires = [
        'colorama',
        'gcovr',
        'lxml',
        'grip'
    ],
    entry_points = {
        'cuppa.method.plugins' : [
            'cuppa.test_report.generate_bitten_report = cuppa.test_report.generate_bitten_report:GenerateBittenReportMethod',
        ]
    },
    classifiers = [
        "Topic :: Software Development :: Build Tools",
        "Intended Audience :: Developers",
        "Development Status :: 4 - Beta",
        "License :: OSI Approved",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 2",
    ],
    keywords = [
        'scons',
        'build',
        'c++'
    ]
)
