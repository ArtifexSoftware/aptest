'''
Automatic creation/use of a venv.

Example usage:

    import autovenv
    autovenv.enter(packages=['pytest', 'numpy'])
    import numpy
    ...
'''

import os
import platform
import subprocess
import sys
import sysconfig
import tempfile


def _freethreads():
    '''
    Returns true if python is free-threads.
    '''
    Py_GIL_DISABLED = sysconfig.get_config_var('Py_GIL_DISABLED')
    if Py_GIL_DISABLED == 1:
        # Free threads build.
        if not sys._is_gil_enabled():   # pylint:disable=protected-access
            return True


def _bits():
    return int.bit_length(sys.maxsize+1)


def enter(*,
        packages=None,
        venv_path=None,
        verbose=True,
        ):
    '''
    Rerun current python program in a venv.
    Args:
        packages:
            List of packages to install.
        venv_path:
            Path of venv directory. If None (the default) we use a new and
            unique venv directory which is deleted afterwards.
            
            Otherwise we use venv_path.format(**kwargs) where kwargs is a dict
            containing these keys:
                python_version: platform.python_version(),
                freethreads: 't' if python is freethreads else '' .
                wordsize: e.g. 64 or 32.
    '''
    AUTOVENV_VENV_PATH = os.environ.get('AUTOVENV_VENV_PATH')
    if (AUTOVENV_VENV_PATH
            and os.path.realpath(sys.prefix)
                == os.path.realpath(AUTOVENV_VENV_PATH)
            ):
        # We are already in the autovenv venv; install packages and return.
        if verbose:
            print(f'autovenv: Already in autovenv venv, {sys.prefix=}.')
        if packages:
            if isinstance(packages, str):
                packages = [packages]
            if verbose:
                print(f'autovenv: Installing packages: {packages}.')
            subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', '--quiet', '--upgrade']
                        + packages,
                    check=1,
                    )
    else:
        # We are not in the autovenv venv so create/update it and rerun
        # ourselves in it.
        if verbose:
            if sys.prefix == sys.base_prefix:
                print(f'autovenv: Not in a venv.')
            else:
                print(f'autovenv: In non-autovenv venv, {sys.prefix=}.')
        
        def setup(venv_path):
            '''
            Create/update venv, modify os.environ so that any subprocesses
            still run inside the venv, and return path of venv's python.
            '''
            if verbose:
                print(f'autovenv: Using venv: {venv_path}')
            # Create/update venv.
            subprocess.run([sys.executable, '-m', 'venv', venv_path], check=1)
            
            # Update PATH and VIRTUAL_ENV so that any subprocesses still run
            # inside the venv. This uses internal implementation details of
            # the venv module.
            bin_dir = 'Scripts' if platform.system() == 'Windows' else 'bin'
            p = os.path.join(venv_path, bin_dir)
            os.environ['PATH'] = p + os.pathsep + os.environ['PATH']
            os.environ['VIRTUAL_ENV'] = venv_path
            
            # Set AUTOVENV_VENV_PATH so we can distinguish between venv's
            # created by us and venv's created by other means.
            os.environ['AUTOVENV_VENV_PATH'] = venv_path
            
            # Return location of venv's python.
            return f'{venv_path}/{bin_dir}/python'
        
        if venv_path:
            # Expand selected fields.
            kwargs = dict(
                    python_version = platform.python_version(),
                    freethreads = 't' if _freethreads() else '',
                    wordsize = _bits(),
                    )
            venv_path = venv_path.format(**kwargs)
            venv_python = setup(venv_path)
            # Rerun the current python program in the venv.
            if platform.system() == 'Windows':
                # Have seen odd behaviour with os.execve() where empty string
                # args appear to be removed.  So we use a child process
                # instead.
                cp = subprocess.run([venv_python] + sys.argv, env=os.environ)
                sys.exit(cp.returncode)
            else:
                os.execve(venv_python, [venv_python] + sys.argv, os.environ)
        
        else:
            # Use tempfile.TemporaryDirectory() to create venv directory that
            # will be automatically removed after use.
            with tempfile.TemporaryDirectory(prefix='autovenv-') as venv_path:
                if verbose:
                    print(f'autovenv: Using unique venv directory: {venv_path}')
                venv_python = setup(venv_path)
                # Rerun the current program in the venv. We need to use
                # a child process instead of os.execve(), so that our
                # tempfile.TemporaryDirectory gets to delete the venv
                # directory.
                cp = subprocess.run([venv_python] + sys.argv, env=os.environ)
                sys.exit(cp.returncode)
