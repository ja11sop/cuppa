#          Copyright Jamie Allsop 2014-2024
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   setup.py
#-------------------------------------------------------------------------------

from setuptools import setup
import os


def get_version():
    # Read VERSION directly so setup/pip build isolation does not import the
    # cuppa package (which pulls runtime deps such as six).
    version_path = os.path.join( os.path.dirname( __file__ ), 'cuppa', 'VERSION' )
    with open( version_path ) as version_file:
        return version_file.read().strip()


with open( 'README.pypi.md' ) as readme_file:
    long_description = readme_file.read()

setup(
    name             = 'cuppa',
    version          = get_version(),
    description      = 'Cuppa, an extension package to simplify and extend Scons',
    author           = 'ja11sop',
    url              = 'https://github.com/ja11sop/cuppa',
    license          = 'Boost Software License 1.0 - http://www.boost.org/LICENSE_1_0.txt',
    long_description = long_description,
    long_description_content_type = 'text/markdown',
    packages = [
        'cuppa',
        'cuppa.core',
        'cuppa.cpp',
        'cuppa.cpp.templates',
        'cuppa.dependencies',
        'cuppa.dependencies.boost',
        'cuppa.method_helpers',
        'cuppa.methods',
        'cuppa.modules',
        'cuppa.package_managers',
        'cuppa.packages',
        'cuppa.platforms',
        'cuppa.profiles',
        'cuppa.project_generators',
        'cuppa.scms',
        'cuppa.test_report',
        'cuppa.toolchains',
        'cuppa.variants',
        'cuppa.utility',
    ],
    package_data = {
        'cuppa': [
            'VERSION',
            os.path.join( 'dependencies','boost','boost_bug_fix_1.73.0.diff' ),
            os.path.join( 'dependencies','boost','boost_test_patch_1.58.0.diff' ),
            os.path.join( 'dependencies','boost','boost_test_patch_1.67.0.diff' ),
            os.path.join( 'dependencies','boost','boost_test_patch_1.68.0.diff' ),
            os.path.join( 'dependencies','boost','boost_test_patch_1.71.0.diff' ),
            os.path.join( 'dependencies','boost','boost_test_patch_1.72.0.diff' ),
            os.path.join( 'cpp','templates','coverage_index.html' ),
            os.path.join( 'cpp','templates','cxx_profiles_breadcrumb.html' ),
            os.path.join( 'cpp','templates','cxx_profiles_index.html' ),
            os.path.join( 'cpp','templates','cxx_profiles_partial_files.html' ),
            os.path.join( 'cpp','templates','cxx_profiles_partial_file_path_oneline.html' ),
            os.path.join( 'cpp','templates','cxx_profiles_partial_rules.html' ),
            os.path.join( 'cpp','templates','cxx_profiles_partial_violation_count.html' ),
            os.path.join( 'cpp','templates','cxx_profiles_partial_build_refs.html' ),
            os.path.join( 'cpp','templates','cxx_profiles_partial_build_views.html' ),
            os.path.join( 'cpp','templates','cxx_profiles_partial_variant_index_list.html' ),
            os.path.join( 'cpp','templates','cxx_profiles_partial_variant_metric.html' ),
            os.path.join( 'cpp','templates','cxx_profiles_table_styles.html' ),
            os.path.join( 'cpp','templates','cxx_profiles_scope.html' ),
            os.path.join( 'cpp','templates','cxx_profiles_source_file.html' ),
            os.path.join( 'test_report','templates','test_report_index.html' ),
            os.path.join( 'test_report','templates','test_suite_index.html' ),
        ]
    },
    install_requires = [
        'colorama',
        'gcovr',
        'grip',
        'jinja2',
        'libsass',
        'lxml',
        'packaging',
        'psutil',
        'pyscss',
        'six',
        'pyyaml',
        'scons'
    ],
    entry_points = {
        'console_scripts': [
              'cuppa = cuppa.__main__:main'
        ],
        'cuppa.method.plugins' : [
            'cuppa.test_report.generate_bitten_report = cuppa.test_report.generate_bitten_report:GenerateBittenReportMethod',
            'cuppa.test_report.html_report.generate_html_report = cuppa.test_report.html_report:GenerateHtmlReportMethod',
            'cuppa.test_report.html_report.collate_test_report = cuppa.test_report.html_report:CollateTestReportIndexMethod',
        ]
    },
    classifiers = [
        "Topic :: Software Development :: Build Tools",
        "Intended Audience :: Developers",
        "Development Status :: 6 - Mature",
        "License :: OSI Approved",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 3",
    ],
    keywords = [
        'scons',
        'build',
        'c++',
    ]
)
