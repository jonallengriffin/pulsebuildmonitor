# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.


import sys
from setuptools import setup, find_packages

version = '0.61'

deps = ['python-dateutil == 1.5', 'MozillaPulse >= 0.6']

# we only support python 2 right now
assert sys.version_info[0] == 2 and sys.version_info[1] >= 5

try:
  import json
except ImportError:
  deps.append('simplejson')

setup(name='pulsebuildmonitor',
      version=version,
      description="montior mozilla tinderbox builds via pulse",
      long_description="""\
""",
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='',
      author='Jonathan Griffin',
      author_email='jgriffin@mozilla.com',
      url='http://hg.mozilla.org/automation/pulsebuildmonitor',
      license='MPL',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=False,
      install_requires=deps
      )

