from setuptools import setup, find_packages

setup(
    name="pypeline",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "pynwb",
        "numpy",
        "pandas",
        "h5py",
        "kilosort>=4.0",
        "torch",
    ],
    entry_points={
        "console_scripts": [
            "pypeline=pypeline.core:cli",
        ],
    },
)
