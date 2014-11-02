# -*- coding: utf-8 -*-
from setuptools import setup

setup(
    name='deedbundler',
    version='0.4',
    url='https://github.com/extempore',
    license='Proprietary',
    author='punkman',
    description='deedbundler bundles deeds in a blockchain',
    packages=[
        'deedbundler',
	'deedbundler.packages',
	'deedbundler.packages.coinkit',
    ],
    package_dir = {'deedbundler': 'deedbundler'},
    install_requires=[
        'ecdsa>=0.10',
        'utilitybelt>=0.1.4'
    ],
)
