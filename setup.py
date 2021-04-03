from setuptools import setup

setup(
    name='vitemadose',
    version='0.0.1',
    packages=['scraper'],
    install_requires=[
        'requests[socks]==2.25.1',
        'pytest==6.2.2',
    ],
)