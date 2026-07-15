import os
import platform
import sys

def test_doctest():
    if platform.system() == 'Windows':
        # Some tests like bash completion cannot succeed on windows.
        print('test_doctest(): not running on Windows.')
        return
    root = os.path.abspath(f'{__file__}/../..')
    sys.path.insert(0, root)
    import pipcl
    
    for path in pipcl.git_items(root):
        if path.endswith('.py'):
            pipcl.run(
                    f'cd {root} && python -m doctest {path}',
                    env_extra=dict(APTEST_DOT_APTEST='0'),
                    )
