import glob
import os

import pipcl

import packaging.utils


def make(path):
    '''
    Creates <path>/simple/ as a pypi-style repository of python packages, for
    all wheels in <path>/.
    
    See:
        https://packaging.python.org/en/latest/specifications/simple-repository-api
    
    We do not include `#<hashname>=<hashvalue>` in links.
    '''
    pipcl.fs_ensure_empty_dir(f'{path}/simple')
    with open(f'{path}/simple/index.html', 'w') as f:
        print(f'<!DOCTYPE html>', file=f)
        print(f'<html>', file=f)
        print(f'<body>', file=f)

        for p in glob.glob(f'{path}/*.whl'):
            leaf = os.path.basename(p)
            name, version, build_number, tags = packaging.utils.parse_wheel_filename(leaf)
            print(f'<a href="simple/{name}/">name</a>', file=f)
            os.mkdir(f'{path}/simple/{name}/')
            with open(f'{path}/simple/{name}/index.html', 'w') as fp:
                print(f'<!DOCTYPE html>', file=fp)
                print(f'<html>', file=fp)
                print(f'<body>', file=fp)
                print(f'<a href="../../{leaf}">{leaf}</a></br>', file=fp)
                print(f'</body>', file=fp)
                print(f'</html>', file=fp)
        
        print(f'</body>', file=f)
        print(f'</html>', file=f)
