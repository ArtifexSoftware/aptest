import os
import re
import sys


def test_override_pip():
    '''
    Check that packages specified with `pip:` and non-default version numbers,
    are not overridden by prerequisites of later packagesdo not override versions of  packages specified with `pip:`.
    '''
    root = os.path.abspath(f'{__file__}/../..')
    
    sys.path.insert(0, root)
    try:
        import pipcl
    finally:
        del sys.path[0]
    
    # Run aptest on our local pymupdf and pymupdf_layout from pypi.org. This
    # will install into the current venv.
    pipcl.run(f'{root}/aptest.py -p pip:==1.26.3 --layout pip: build')
    
    # Check that the installed pymupdf has our overwritten version number.
    pymupdf_version = pipcl.run(f'python -c "import pymupdf; print(pymupdf.__version__)"', capture=1)
    pymupdf_version = pymupdf_version.strip()
    print(f'{pymupdf_version=}')
    assert pymupdf_version == '1.26.3', f'Incorrect {pymupdf_version=}'


def test_override():
    '''
    Check that packages specified with `pip:` do not override
    versions of earlier packages that we build from source.
    '''
    root = os.path.abspath(f'{__file__}/../..')
    
    sys.path.insert(0, root)
    try:
        import pipcl
    finally:
        del sys.path[0]
    
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
