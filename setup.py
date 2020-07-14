from setuptools import setup, find_packages


setup(
    name="smb3-foundry",
    version="1.0.0",
    description=("A modern Super Mario Bros. 3 Level Editor"),
    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
    ],
    keywords="smb3,romhacking,retro",
    author="Michael Nix",
    author_email="mchl.nix@googlemail.com",
    license="LICENSE",
    packages=find_packages(),
    include_package_data=True,
    zip_safe=True,
    install_requires=["PySide2>=5.15.0"],
    test_suite="tests",
    scripts=["smb3-foundry.py"],
)
