#!/usr/bin/env python
# -*- coding: utf-8 -*-
import codecs
import setuptools


def long_description():
    try:
        return codecs.open('README.rst', 'r', 'utf-8').read()
    except IOError:
        return 'Long description error: Missing README.rst file'


setuptools.setup(
    name='twisted-celery',
    packages=setuptools.find_packages(),
    version='0.0.1',
    description='Celery connector for Twisted.',
    long_description=long_description(),
    keywords='twisted celery',
    author='Patrick Cloke',
    author_email='clokep@patrick.cloke.us',
    url='https://github.com/clokep/twisted-celery',
    license='BSD',
    platforms=['any'],
    install_requires=[
        'celery>=4.0,<5.0',
        # Probably works with older versions.
        'twisted>=18.7.0',
        # Probably works with older versions.
        'pika>=0.12.0<1.0.0',
    ],
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'License :: OSI Approved :: BSD License',
        'Topic :: System :: Distributed Computing',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Operating System :: OS Independent',
    ],
)
