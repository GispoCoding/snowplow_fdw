#!/usr/bin/env python
from setuptools import setup
from snowplowfdw._version import __version__

setup(
    name="snowplowfdw",
    version=__version__,
    url="https://github.com/GispoCoding/snowplow_fdw",
    # license="", # TODO: add license
    author="Pauliina Mäkinen",
    tests_require=["pytest"],
    author_email="pauliina@gispo.fi",
    description="PostgreSQL foreign data wrapper for json data from snowplow",
    long_description="PostgreSQL foreign data wrapper for json data from snowplow",
    packages=["snowplowfdw"],
    include_package_data=True,
    platforms="any",
    classifiers=[
    ],
    install_requires=[
        "multicorn>=1.3.4.dev0",
        "requests>=2.22.0",
        "plpygis>=0.1.0"
    ],
    keywords='gis geographical postgis fdw snowplow postgresql'
)
