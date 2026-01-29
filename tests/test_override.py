import os
import re
import sys


root = os.path.abspath(f'{__file__}/../..')

sys.path.insert(0, root)
try:
    import pipcl
finally:
    del sys.path[0]


def test_override_pip():
    '''
    Check that packages specified with `pip:` and non-default version numbers,
    are not overridden by prerequisites of later packages.
    '''
    # Use aptest to install specific old version of pymupdf from pypi.org, and
    # default pymupdf_layout from pypi.org. This will install into the current
    # venv.
    pipcl.run(f'{root}/aptest.py -p pip:==1.26.3 --layout pip: build')
    
    # Check that the installed pymupdf is the specified old version.
    pymupdf_version = pipcl.run(f'python -c "import pymupdf; print(pymupdf.__version__)"', capture=1)
    pymupdf_version = pymupdf_version.strip()
    print(f'{pymupdf_version=}')
    assert pymupdf_version == '1.26.3', f'Incorrect {pymupdf_version=}'


def test_override():
    '''
    Check that packages specified with `pip:` do not override
    versions of earlier packages that we build from source.
    '''
    # Get our own copy of pymupdf and overwrite version number in setup.py.
    pymupdf_checkout = 'aptest-test-git-pymupdf'
    pipcl.git_get(
            pymupdf_checkout,
            remote = 'git@github.com:PyMuPDF/PyMuPDF.git',
            branch = 'main',
            )
    text = pipcl.fs_read(f'{pymupdf_checkout}/setup.py')
    text2 = re.sub('version_p = \'[0-9.]+\'', 'version_p = \'9.9.9\'', text)
    assert text2 != text
    pipcl.fs_write(f'{pymupdf_checkout}/setup.py', text2)
    
    # Run aptest on our local pymupdf and pymupdf_layout from pypi.org. This
    # will install into the current venv.
    pipcl.run(f'{root}/aptest.py -p {pymupdf_checkout} --layout pip: build test -t -')
    
    # Check that the installed pymupdf has our overwritten version number.
    pymupdf_version = pipcl.run(f'python -c "import pymupdf; print(pymupdf.__version__)"', capture=1)
    pymupdf_version = pymupdf_version.strip()
    print(f'{pymupdf_version=}')
    assert pymupdf_version == '9.9.9', f'Incorrect {pymupdf_version=}'


def _get_pymupdf_version():
    pymupdf_version = pipcl.run(f'python -c "import pymupdf; print(pymupdf.__version__)"', capture=1)
    pymupdf_version = pymupdf_version.strip()
    print(f'{pymupdf_version=}')
    return pymupdf_version

def test_same_version():
    # Make modified pymupdf-1.26.3 with extra marker value in source.
    pymupdf_checkout = 'aptest-test-git-pymupdf_sameversion'
    pipcl.git_get(
            pymupdf_checkout,
            remote = 'git@github.com:PyMuPDF/PyMuPDF.git',
            tag = '1.26.3',
            )
    text = pipcl.fs_read(f'{pymupdf_checkout}/src/__init__.py')
    text += '\ntest_same_version_marker = "special marker"\n'
    pipcl.fs_write(f'{pymupdf_checkout}/src/__init__.py', text)
    
    pipcl.run(f'{root}/aptest.py -p {pymupdf_checkout} --layout pip: build')
    
    pymupdf_version = _get_pymupdf_version()
    assert pymupdf_version == '1.26.3', f'Incorrect {pymupdf_version=}'
    marker = pipcl.run(f'python -c "import pymupdf; print(pymupdf.test_same_version_marker)"', capture=1)
    assert marker.strip() == 'special marker', f'Unexpected {marker=}'
    
    # Installing directly from pypi.org should overwrite the installed pymupdf.
    pipcl.run(f'{root}/aptest.py -p pip:==1.26.3 build')
    pymupdf_version = _get_pymupdf_version()
    assert pymupdf_version == '1.26.3', f'Incorrect {pymupdf_version=}'
    
    has_marker = pipcl.run(f'python -c "import pymupdf; print(hasattr(pymupdf, \'test_same_version_marker\'))"', capture=1)
    assert has_marker.strip() == 'False', f'{has_marker=}'
