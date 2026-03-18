import os
import sys
import textwrap

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


def test_log_timestamps():
    print()
    code = textwrap.dedent('''
            import time
            
            import pipcl
            
            pipcl.g_log_format = '%d '
            
            pipcl.log('one')
            time.sleep(2)
            pipcl.log('two')
            time.sleep(2)
            pipcl._log('three\\n ', level=0, caller=1, raw=1)
            time.sleep(2)
            pipcl._log('four\\n', level=0, caller=1, raw=1)
            time.sleep(2)
            pipcl.log('five')
            ''')
    path = f'{root_relative}/tests/_test_log_timestamps.py'
    pipcl.fs_write(path, code)
    text = pipcl.run(f'{sys.executable} {path}', env_extra=dict(PYTHONPATH=root_relative), capture=1)
    print(f'test_log_timestamps():')
    print(textwrap.indent(text, '    '))
