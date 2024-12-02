from setuptools import setup
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

setup(
    name="polybot",
    version="1.3",
    description="Multi bot library",
    long_description="",
    license="MIT",
    author="Russ Garrett",
    author_email="russ@garrett.co.uk",
    url="https://github.com/russss/polybot",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
    ],
    packages=["polybot"],
    install_requires=["tweepy==4.12.1", "Mastodon.py==1.8.0", "atproto==0.0.49"],
)
