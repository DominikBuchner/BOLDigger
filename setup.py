import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="boldigger",
    version="1.1.0",
    author="Dominik Buchner",
    author_email="dominik.buchner524@googlemail.com",
    description="A python package to query different databases of boldsystems.org",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/DominikBuchner/BOLDigger",
    packages=setuptools.find_packages(),
    license = 'MIT',
    install_requires = ['PySimpleGUI', 'requests-html', 'beautifulsoup4', 'openpyxl',
                        'numpy', 'pandas', 'requests', 'more-itertools'],
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
