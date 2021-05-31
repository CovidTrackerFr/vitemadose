from setuptools import setup

setup(
    name="vitemadose",
    version="0.0.1",
    packages=["scraper"],
    install_requires=[
        "pytz==2021.1",
        "httpx==0.17.1",
        "requests[socks]==2.25.1",
        "pytest==6.2.2",
        "beautifulsoup4==4.9.3",
        "coverage==5.5",
        "terminaltables==3.1.0",
        "python-dateutil==2.8.1",
        "coverage-badge==1.0.1",
        "unidecode==1.2.0",
        "jsonschema==3.2.0",
        "pydantic==1.8.2",
        "diskcache==5.2.1",
        "dotmap==1.3.23",
    ],
)
