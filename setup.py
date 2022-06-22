from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()
with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = fh.read()

setup(
    name = 'autobench',
    version = '0.0.1',
    author = 'Abhinandan Purkait',
    author_email = 'abhinandan.purkait@mayadata.io',
    license = 'MIT',
    description = 'Storage Performance Benchmarking Tool',
    long_description = long_description,
    long_description_content_type = "text/markdown",
    url = 'https://github.com/Abhinandan-Purkait/autobench',
    py_modules = ['autobench'],
    packages = find_packages(),
    install_requires = [requirements],
    python_requires='>=3.9',
    classifiers=[
        "Programming Language :: Python :: 3.10.4",
        "Operating System :: Linux",
    ],
    entry_points = '''
        [console_scripts]
        autobench=autobench:cli
    '''
)