import shutil
import os
import subprocess
import sys
import textwrap
import venv

g_root = os.path.normpath(f'{__file__}/../..')


def _log(text=''):
    print(text, flush=1)


def _write_code(code, path):
    code = textwrap.dedent(code)
    with open(path, 'w') as f:
        f.write(code)


# Create an env for running test child processes, so that `import autovenv`
# will work.
#
# We also unset AUTOVENV_VENV_ENTERED in case pytest itself is being run in an
# autoenv venv.
#
g_env = os.environ.copy()
g_env['PYTHONPATH'] = g_root
g_env.pop('AUTOVENV_VENV_ENTERED', None)


def test_autovenv_default():
    '''
    Check handling of autovenv.enter() with no venv_path.
    '''
    _log()
    path = f'{g_root}/tests/_test_autovenv.py'
    _write_code(f'''
            import autovenv
            import os
            import sys
            autovenv.enter(packages='requests', use_existing_venv=0)
            PATH = os.environ.get("PATH")
            VIRTUAL_ENV = os.environ.get("VIRTUAL_ENV")
            print(f'test_autovenv_default: {{PATH=}}')
            print(f'test_autovenv_default: {{VIRTUAL_ENV=}}')
            print(f'test_autovenv_default: {{sys.prefix=}}')
            assert os.path.realpath(sys.prefix) == os.path.realpath(VIRTUAL_ENV)
            import requests
            assert requests.__file__.startswith(sys.prefix)
            ''',
            path,
            )
    subprocess.run([sys.executable, path], check=1, env=g_env)
    
    
def test_autovenv_named():
    '''
    Check handling of autovenv.enter()'s venv_path.
    '''
    _log()
    path = f'{g_root}/tests/_test_autovenv.py'
    venv_path = os.path.normpath(f'{g_root}/tests/_test_autovenv_venv')
    shutil.rmtree(venv_path, ignore_errors=1)
    _write_code(f'''
            import autovenv
            import sys
            autovenv.enter(venv_path={venv_path!r}, packages='requests', use_existing_venv=0)
            venv_path = sys.prefix
            import requests
            print(f'test_autovenv_named(): {{sys.prefix=}}')
            print(f'test_autovenv_named(): {{requests.__file__=}}')
            assert requests.__file__.startswith(sys.prefix)
            assert sys.prefix.endswith({venv_path!r}), f'{{sys.prefix=}}'
            ''',
            path,
            )
    subprocess.run([sys.executable, path], check=1, env=g_env)
    
    
def test_autovenv_named_setupfn():
    '''
    Check handling of autovenv.enter()'s setupfn.
    '''
    _log()
    path = f'{g_root}/tests/_test_autovenv.py'
    venv_path = os.path.normpath(f'{g_root}/tests/_test_autovenv_venv')
    shutil.rmtree(venv_path, ignore_errors=1)
    _write_code(f'''
            import autovenv
            import subprocess
            import sys
            def venv_setup(builder_context):
                subprocess.run(
                        [
                            builder_context.env_exe,
                            '-m',
                            'pip',
                            'install',
                            '--quiet',
                            'requests',
                        ],
                        check=1,
                        )
            autovenv.enter(venv_path={venv_path!r}, setupfn=venv_setup, use_existing_venv=0)
            venv_path = sys.prefix
            import requests
            print(f'test_autovenv_named_setupfn(): {{sys.prefix=}}')
            print(f'test_autovenv_named_setupfn(): {{requests.__file__=}}')
            assert requests.__file__.startswith(sys.prefix)
            assert sys.prefix.endswith({venv_path!r}), f'{{sys.prefix=}}'
            ''',
            path,
            )
    subprocess.run([sys.executable, path], check=1, env=g_env)


def test_autovenv_existing():
    '''
    Checks that we can update an existing venv. This requires us to set
    symlinks=True on non-windows, when calling venv.create().
    '''
    _log()
    venv_path = os.path.normpath(f'{g_root}/tests/_test_autovenv_venv')
    
    if 0:
        # Show info about calls to venv.EnvBuilder().
        vei0 = venv.EnvBuilder.__init__
        def vei1(*args, **kwargs):
            _log(f'{args=}')
            _log(f'{kwargs=}')
            vei0(*args, **kwargs)
        venv.EnvBuilder.__init__ = vei1
        
    shutil.rmtree(venv_path, ignore_errors=1)
    
    _log(f'test_autovenv_existing(): Running -m venv')
    subprocess.run([sys.executable, '-m', 'venv', venv_path], check=1)
    
    _log(f'test_autovenv_existing(): Running -m venv')
    subprocess.run([sys.executable, '-m', 'venv', venv_path], check=1)
    
    _log(f'test_autovenv_existing(): Calling venv.main()')
    venv.main(['venv_path'])
    
    _log(f'test_autovenv_existing(): Calling venv.create()')
    symlinks = os.name != 'nt'
    venv.create(venv_path, symlinks=symlinks, with_pip=True)
    
    _log(f'test_autovenv_existing(): Calling autovenv.enter()')
    path = f'{g_root}/tests/_test_autovenv.py'
    _write_code(f'''
            import sys
            import autovenv
            autovenv.enter(venv_path={venv_path!r}, packages='requests', use_existing_venv=0)
            import requests
            print(f'test_autovenv_existing(): {{sys.prefix=}}')
            print(f'test_autovenv_existing(): {{requests.__file__=}}')
            assert requests.__file__.startswith(sys.prefix)
            assert sys.prefix.endswith({venv_path!r}), f'{{sys.prefix=}}'
            ''',
            path,
            )
    subprocess.run([sys.executable, path], check=1, env=g_env)
    

def test_autovenv_chain():
    '''
    Check we get assert failure if we call .enter() twice.
    '''
    _log()
    #os.environ.pop('AUTOVENV_VENV_PATH', None)
    #os.environ.pop('AUTOVENV_VENV_ENTERED', None)
    venv_path1 = f'{g_root}/tests/_test_autovenv_venv1'
    venv_path2 = f'{g_root}/tests/_test_autovenv_venv2'
    venv_path3 = f'{g_root}/tests/_test_autovenv_venv3'
    shutil.rmtree(venv_path1, ignore_errors=1)
    shutil.rmtree(venv_path2, ignore_errors=1)
    shutil.rmtree(venv_path3, ignore_errors=1)
    
    path = f'{g_root}/tests/_test_autovenv.py'
    _write_code(f'''
            import os
            import sys
            import autovenv
            AUTOVENV_VENV_PATH = os.environ.get('AUTOVENV_VENV_PATH')
            print(f'test_autovenv_chain(): start: {{AUTOVENV_VENV_PATH=}}')
            autovenv.enter(venv_path={venv_path1!r}, packages='requests', use_existing_venv=0)
            import requests
            print(f'test_autovenv_chain(): {{requests.__file__=}}')
            autovenv.enter(venv_path={venv_path2!r}, packages=['requests', 'swig'], use_existing_venv=0)
            import swig
            autovenv.enter(venv_path={venv_path3!r}, packages=['requests', 'swig'], use_existing_venv=0)
            ''',
            path,
            )
    subprocess.run([sys.executable, path], check=1, env=g_env)
    

def test_autovenv_chain_unnamed():
    '''
    Check we get assert failure if we call .enter() twice.
    '''
    _log()
    os.environ.pop('AUTOVENV_VENV_PATH', None)
    os.environ.pop('AUTOVENV_VENV_ENTERED', None)
    
    path = f'{g_root}/tests/_test_autovenv.py'
    _write_code(f'''
            import os
            import sys
            import autovenv
            AUTOVENV_VENV_PATH = os.environ.get('AUTOVENV_VENV_PATH')
            print(f'test_autovenv_chain_unnamed(): start: {{AUTOVENV_VENV_PATH=}}')
            autovenv.enter(packages='requests', use_existing_venv=0)
            import requests
            print(f'test_autovenv_chain_unnamed():{{requests.__file__=}}')
            autovenv.enter(packages=['requests', 'swig'], use_existing_venv=0)
            import swig
            print(f'test_autovenv_chain_unnamed():{{swig.__file__=}}')
            ''',
            path,
            )
    subprocess.run([sys.executable, path], check=1, env=g_env)


def test_autovenv_nested():
    print()
    venv_path1 = f'{g_root}/tests/_test_autovenv_venv1'
    venv_path2 = f'{g_root}/tests/_test_autovenv_venv2'
    venv_path3 = f'{g_root}/tests/_test_autovenv_venv3'
    shutil.rmtree(venv_path1, ignore_errors=1)
    shutil.rmtree(venv_path2, ignore_errors=1)
    shutil.rmtree(venv_path3, ignore_errors=1)
    
    path1 = f'{g_root}/tests/_test_autovenv_nested1.py'
    path2 = f'{g_root}/tests/_test_autovenv_nested2.py'
    path3 = f'{g_root}/tests/_test_autovenv_nested3.py'
    _write_code(f'''
            import os
            import subprocess
            import sys
            import autovenv
            print(f'### path1')
            autovenv.enter(venv_path={venv_path1!r}, use_existing_venv=0)
            subprocess.run([sys.executable, {path2!r}], check=1)
            ''',
            path1,
            )
    _write_code(f'''
            import os
            import subprocess
            import sys
            import autovenv
            print(f'### path2')
            autovenv.enter(venv_path={venv_path2!r})
            subprocess.run([sys.executable, {path3!r}], check=1)
            ''',
            path2,
            )
    _write_code(f'''
            import os
            import subprocess
            import sys
            import autovenv
            print(f'### path3')
            autovenv.enter(venv_path={venv_path3!r})
            ''',
            path3,
            )
    subprocess.run([sys.executable, path1], check=1, env=g_env)
