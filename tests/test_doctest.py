import os
import sys

def test_doctest():
    root = os.path.abspath(f'{__file__}/../..')
    sys.path.insert(0, root)
    import pipcl
    
    for path in pipcl.git_items(root):
        if path.endswith('.py'):
            pipcl.run(f'cd {root} && python -m doctest {path}')
