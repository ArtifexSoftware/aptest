import os
import sys


root = os.path.normpath(f'{__file__}/../..')

sys.path.insert(0, root)
try:
    import pipcl
finally:
    del sys.path[0]

root_relative = pipcl.relpath(root)

def test_dirname():
    print(f'{root=}')
    print(f'{root_relative=}')
    print(f'{os.getcwd()=}')
    leaf = os.path.basename(root)   # Typically 'aptest'.
    pipcl.run(f'cd {root}/.. && {leaf}/aptest.py -V=0 --aptest {leaf}')
    pipcl.run(f'cd {root}/.. && {leaf}/aptest.py -V=0 --aptest {leaf}/')
    pipcl.run(f'cd {root} && ./aptest.py -V=0 --aptest ../{leaf}')
    pipcl.run(f'cd {root} && ./aptest.py -V=0 --aptest ../{leaf}/')
