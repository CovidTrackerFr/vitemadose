from setuptools import setup

setup(
    name='vitemadose',
    version='0.0.1',
    packages=['scraper'],
    install_requires=[
        'pytz==2021.1',
        'httpx==0.17.1',
        'requests[socks]==2.25.1',
        'pytest==6.2.2',
        'beautifulsoup4==4.9.3',
        'python-dateutil',
    ],
)
