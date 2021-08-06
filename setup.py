# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

with open('requirements.txt') as f:
	install_requires = f.read().strip().split('\n')

# get version from __version__ variable in uniseal_custom/__init__.py
from uniseal_custom import __version__ as version

setup(
	name='uniseal_custom',
	version=version,
	description='Uniseal Custom',
	author='Saif Ur Rehman',
	author_email='saif@mocha.pk',
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
