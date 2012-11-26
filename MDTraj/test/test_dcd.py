# Copyright 2012 mdtraj developers
#
# This file is part of mdtraj
#
# mdtraj is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# mdtraj is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# mdtraj. If not, see http://www.gnu.org/licenses/.

"""
Test the cython dcd module

Note, this file cannot be located in the dcd subdirectory, because that
directory is not a python package (it has no __init__.py) and is thus tests
there are not discovered by nose
"""

import tempfile, os
import numpy as np
from mdtraj import dcd, io
from mdtraj.testing import get_fn, eq, DocStringFormatTester
import warnings

TestDocstrings = DocStringFormatTester(dcd, error_on_none=True)

fn_dcd = get_fn('frame0.dcd')
pdb = get_fn('native.pdb')

temp = tempfile.mkstemp(suffix='.dcd')[1]
def teardown_module(module):
    """remove the temporary file created by tests in this file 
    this gets automatically called by nose"""
    os.unlink(temp)

def test_read():
    xyz = dcd.read_xyz(fn_dcd)
    xyz2 = io.loadh(get_fn('frame0.dcd.h5'), 'xyz')

    eq(xyz, xyz2)
    
def test_write_0():
    xyz = dcd.read_xyz(fn_dcd)
    dcd.write_xyz(temp, xyz, force_overwrite=True)
    xyz2 = dcd.read_xyz(temp)

    eq(xyz, xyz2)
    
def test_write_1():
    xyz = np.array(np.random.randn(500, 10, 3), dtype=np.float32)
    dcd.write_xyz(temp, xyz, force_overwrite=True)
    xyz2 = dcd.read_xyz(temp)

    eq(xyz, xyz2)