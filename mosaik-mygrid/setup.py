from setuptools import setup, find_packages


setup(
    name='mosaik-mygrid',
    version='0.1',
    author='Lucas Melo',
    author_email='lucassmelo at dee.ufc.br',
    description=('An interface to run mygrid powerflow tool in a mosaik cosimulation environment'),
    long_description=(open('README.md').read() + '\n\n'),
    install_requires=[
        'mygrid==0.3'
    ],
    packages=find_packages(),
    include_package_data=True,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: GNU Lesser General Public License v2 (LGPLv2)',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Topic :: Scientific/Engineering',
    ],
)
