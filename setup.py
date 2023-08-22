# Copyright (C) 2023 qBraid
#
# This file is part of the qBraid-SDK
#
# The qBraid-SDK is free software released under the GNU General Public License v3
# or later. You can redistribute and/or modify it under the terms of the GPL v3.
# See the LICENSE file in the project root or <https://www.gnu.org/licenses/gpl-3.0.html>.
#
# THERE IS NO WARRANTY for the qBraid-SDK, as per Section 15 of the GPL v3.

"""
qBraid setup file

"""

from setuptools import setup

with open("qbraid/_version.py") as f:
    version = f.readlines()[-1].split()[-1].strip("\"'")

setup(
    version=version,
    extras_require={ 
        # Install all optional dependencies
        'all':['dependency'],
        #Bra-ket
        'amazon-braket': ['amazon-braket-sdk'],
        #Pyquill
        'rigetti':['pyquill'],
        #Pytket
        'pytket-all': ['pytket','pytket-braket'],
        'pytket':['pytket'],
        'pytket-braket':['pytket-braket'],
        #Qiskit
        'qiskit-all': ['qiskit','qiskit-ibm-provider','qiskit-qasm3-import'],
        'qiskit':['qiskit'],
        'qiskit-ibm-provider':['qiskit-ibm-provider'],
        'qiskit-qasm3-import':['qiskit-qasm3-import']
    }
)
