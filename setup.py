import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="boldigger",
    version="2.0.1",
    author="Dominik Buchner",
    author_email="dominik.buchner524@googlemail.com",
    description="A python package to query different databases of boldsystems.org",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/DominikBuchner/BOLDigger",
    packages=setuptools.find_packages(),
    license = 'MIT',
    install_requires = ['PySimpleGUI >= 4.18.2',
                        'requests-html >= 0.10.0',
                        'beautifulsoup4 >= 4.7.1',
                        'openpyxl >= 2.6.2',
                        'numpy >= 1.16.4',
                        'pandas >= 0.25.0',
                        'requests >= 2.22.0',
                        'more-itertools >= 7.2.0',
                        'lxml >= 4.3.3',
                        'html5lib >= 1.0.1',
                        'xlrd >= 1.2.0',
                        'luddite >= 1.0.1',
                        'biopython >= 1.78',
                        'joblib >= 1.1.0',
                        'psutil >= 5.8.0',
                        'tqdm >= 4.56.0',
                        'tables >= 3.7.0'],
    include_package_data = True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    entry_points = {
        "console_scripts" : [
            "boldigger = boldigger.__main__:main",
        ]
    },
)
