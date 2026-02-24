"""Setup configuration for RiskDAG package."""

from setuptools import setup, find_packages
import os

# Read README for long description
with open('README.md', 'r', encoding='utf-8') as f:
    long_description = f.read()

# Read version from package
version = {}
with open(os.path.join('riskdag', '__init__.py'), 'r') as f:
    for line in f:
        if line.startswith('__version__'):
            exec(line, version)
            break

setup(
    name='riskdag',
    version=version.get('__version__', '0.1.0'),
    author='Risk Engineering Team',
    description='Enterprise risk modeling for Airflow DAGs and latent operational risks',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/ExpandThenSimplify/riskdag',
    packages=find_packages(),
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'Topic :: Scientific/Engineering :: Information Analysis',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
    ],
    python_requires='>=3.8',
    install_requires=[
        'numpy>=1.20.0',
        'scipy>=1.7.0',
        'networkx>=2.6.0',
    ],
    extras_require={
        'airflow': [
            'apache-airflow>=2.0.0',
        ],
        'viz': [
            'plotly>=5.0.0',
            'matplotlib>=3.3.0',
        ],
        'all': [
            'apache-airflow>=2.0.0',
            'plotly>=5.0.0',
            'matplotlib>=3.3.0',
        ],
        'dev': [
            'pytest>=6.0.0',
            'pytest-cov>=2.0.0',
            'black>=21.0',
            'flake8>=3.9.0',
            'mypy>=0.900',
        ],
    },
    keywords='monte carlo, airflow, dag, enterprise risk, '
             'quantitative risk, expected shortfall, value at risk, '
             'cyber risk, operational risk',
    project_urls={
        'Documentation': 'https://github.com/ExpandThenSimplify/riskdag',
        'Source': 'https://github.com/ExpandThenSimplify/riskdag',
        'Tracker': 'https://github.com/ExpandThenSimplify/riskdag/issues',
    },
)
