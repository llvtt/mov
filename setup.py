# Copyright 2015 MongoDB, Inc.
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

classifiers = '''
Development Status :: 4 - Beta
Intended Audience :: Developers
License :: OSI Approved :: Apache Software License
Programming Language :: Python :: 2.6
Programming Language :: Python :: 2.7
Programming Language :: Python :: 3.3
Programming Language :: Python :: 3.4
Topic :: Database
Topic :: Software Development :: Libraries :: Python Modules
Operating System :: Unix
Operating System :: MacOS :: MacOS X
Operating System :: Microsoft :: Windows
Operating System :: POSIX
'''

import sys
try:
    from setuptools import setup
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup

extra_opts = {}
install_requires = [
    'requests >= 2.5',
    'beautifulsoup4 >= 4.3'
]


try:
    with open('README.rst', 'r') as fd:
        extra_opts['long_description'] = fd.read()
except IOError:
    pass        # Install without README.rst


if sys.version_info[:2] == (2, 6):
    install_requires.append('argparse')


setup(
    name='mov',
    version='0.1',
    author='Luke Lovett',
    author_email='luke.lovett@mongodb.com',
    description='A version manager for MongoDB',
    keywords=['mongo', 'mongodb', 'version', 'installer'],
    url='https://github.com/llvtt/mov',
    license='http://www.apache.org/licenses/LICENSE-2.0.html',
    platforms=['any'],
    classifiers=classifiers.split('\n'),
    install_requires=install_requires,
    entry_points={'console_scripts': ['mov = mov.mov:main']},
    **extra_opts
)
