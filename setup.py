#          Copyright Jamie Allsop 2014-2014
# Distributed under the Boost Software License, Version 1.0.
#    (See accompanying file LICENSE_1_0.txt or copy at
#          http://www.boost.org/LICENSE_1_0.txt)

#-------------------------------------------------------------------------------
#   setup.py
#-------------------------------------------------------------------------------

from setuptools import setup
import cuppa.version

try:
    import pypandoc
    read_markdown = lambda f: pypandoc.convert(f, 'rst')
except ImportError:
    print( "warning: pypandoc module not found, could not convert Markdown to RST" )
    read_markdown = lambda f: open(f, 'r').read()


setup(
    name             = 'cuppa',
    version          = cuppa.version.get(),
    description      = 'Cuppa, an extension package to simplify and extend Scons',
    author           = 'ja11sop',
    url              = 'https://github.com/ja11sop/cuppa',
    license          = 'LICENSE_1_0.txt',
    long_description = read_markdown('README.md'),
    packages = [
        'cuppa',
        'cuppa.cpp',
        'cuppa.dependencies',
        'cuppa.methods',
        'cuppa.modules',
        'cuppa.platforms',
        'cuppa.profiles',
        'cuppa.project_generators',
        'cuppa.scms',
        'cuppa.toolchains',
        'cuppa.variants',
    ],
    package_data = {
        '': ['VERSION', 'README.md' ]
    },
    install_requires = [
        'colorama',
        'gcovr'
    ]
)
