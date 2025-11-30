from setuptools import setup, find_packages

setup(
    name="search1688api",
    version="2.0.0",
    author="netkaruma",
    author_email="suzumekaruma@gmail.com",
    description="Python library for searching products on 1688.com by image",
    packages=find_packages(),
    python_requires=">=3.7",
    install_requires=[
        "requests>=2.25.0",
        "aiohttp>=3.8.0",
        "yarl>=1.6.0",
        "brotli>=1.0.9",
        "zstandard>=0.18.0",
    ],
)
