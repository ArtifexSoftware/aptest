'''
Automatic creation/use of a venv.

Example usage:

    import autovenv
    autovenv.enter(packages=['pytest', 'numpy'])
    import numpy
    ...
'''

import shutil
import os
import platform
import subprocess
import sys
import sysconfig
import tempfile
import venv


def _freethreads():
    '''
    Returns true if python is free-threads.
    '''
    Py_GIL_DISABLED = sysconfig.get_config_var('Py_GIL_DISABLED')
    if Py_GIL_DISABLED == 1:
        # Free threads build.
        if not sys._is_gil_enabled():   # pylint:disable=protected-access,no-member
            return True


def _bits():
    return int.bit_length(sys.maxsize+1)


# When rerunning the current program we need to reset AUTOVENV_N back to its
# initial value; it can be defined if our parent process itself used autovenv.
#
_g_initial_AUTOVENV_N = os.environ.get('AUTOVENV_N', '0')


def enter(*,
        create=2,
        create_kwargs=None,
        packages=None,
        setupfn=None,
        use_existing_venv=True,
        venv_path=None,
        verbose=False,
        ):
    '''
    Rerun current python program in a venv.
    Args:
        create:
            Controls venv creation if <venv_path> is set:
            1: If <venv_path> already exists then assume it is up to date:
               * Don't call `venv.create()` to update the venv.
               * Don't call <setupfn>.
               * Don't install <packages>.
               Behaviour is undefined if <venv_path> is not valid venv.
            2: Always create/update the venv.
               Behaviour may be undefined if an existing venv is not a valid
               venv.
            3: Delete the venv if it exists, then create a new venv.
        create_kwargs:
            None or kwargs to pass to `venv.create()` when we create/update the
            venv - i.e. `venv.create(venv_path, **create_kwargs)`.  If None we
            use `dict(symlinks=(os.name!='nt'), with_pip=True)`.
        packages:
            List of packages to install before we enter the venv.
        setupfn:
            Optional function called after we create/update the venv and before
            we rerun in the venv. Passed a `types.SimpleNamespace` as returned by
            `venv.EnvBuilder.ensure_directories()`.
            
            For example can be used instead of <packages> if more control is
            required.
        use_existing_venv:
            If true (the default), we do nothing if we are already in a venv.
        venv_path:
            Path of venv directory. If None (the default) we use a new and
            unique venv directory which is deleted afterwards.
            
            Otherwise we use `venv_path.format()` with these values:
                python_version: platform.python_version(),
                freethreads: 't' if python is freethreads else '' .
                wordsize: e.g. 64 or 32.
        verbose:
            .
    If environment has AUTOVENV_DOIT=0, we do nothing.
    '''
    def log(text):
        if verbose:
            print(text, flush=1)
    
    if AUTOVENV_DOIT := os.environ.get('AUTOVENV_DOIT') == '0':
        print(f'autovenv.enter() doing nothing because {AUTOVENV_DOIT=}.')
        return
    
    # AUTOVENV_N and AUTOVENV_N_CURRENT are used to allow predictable behaviour
    # in the rather esoteric circumstance where we are called multiple times
    # by the same program, but also if we are called by both parent and child
    # processes.
    #
    AUTOVENV_N = int(os.environ.get('AUTOVENV_N', '0'))
    AUTOVENV_N_CURRENT = int(os.environ.get('AUTOVENV_N_CURRENT', '0'))
    AUTOVENV_VENV_PATH = os.environ.get('AUTOVENV_VENV_PATH', None)
    
    AUTOVENV_N += 1
    os.environ['AUTOVENV_N'] = str(AUTOVENV_N)
    
    if venv_path:
        venv_path = venv_path.format(
                python_version = platform.python_version(),
                freethreads = 't' if _freethreads() else '',
                wordsize = _bits(),
                )
    
    log(f'autovenv.enter(): Starting:')
    log(f'autovenv.enter():     {AUTOVENV_N=}')
    log(f'autovenv.enter():     {AUTOVENV_N_CURRENT=}')
    log(f'autovenv.enter():     {AUTOVENV_VENV_PATH=}')
    log(f'autovenv.enter():     {sys.prefix=}')
    log(f'autovenv.enter():     {venv_path=}')
    log(f'autovenv.enter():     {packages=}')
    
    if AUTOVENV_N < AUTOVENV_N_CURRENT:
        log(f'autovenv.enter(): skipping earlier call.')
        return
    
    elif AUTOVENV_N == AUTOVENV_N_CURRENT:
        log(f'autovenv.enter(): Have entered autovenv venv.')
        assert AUTOVENV_VENV_PATH
        assert os.path.realpath(sys.prefix) == os.path.realpath(AUTOVENV_VENV_PATH)
        return
    
    elif venv_path and os.path.realpath(venv_path) == os.path.realpath(sys.prefix):
        log(f'autovenv.enter(): already in requested venv - sys.prefix is same as venv_path (with os.path.realpath()).')
        return
    
    else:
        assert AUTOVENV_N == AUTOVENV_N_CURRENT + 1, f'{AUTOVENV_N=} {AUTOVENV_N_CURRENT=}'
        
        # We are not in an autovenv venv so create/update it and rerun
        # ourselves in it.
        if sys.prefix == sys.base_prefix:
            log(f'autovenv.enter(): Not in a venv.')
        else:
            log(f'autovenv.enter(): In unrelated venv, {sys.prefix=}.')
        
        def setup(venv_path, packages, create):
            '''
            Create/update venv, modify os.environ so that any subprocesses
            still run inside the venv, and return the types.SimpleNamespace
            from venv.EnvBuilder.ensure_directories().
            '''
            venv_path = os.path.abspath(venv_path)
            
            do_setup_venv = True
            
            # Create/update venv.
            if create == 3:
                # Delete any existing venv.
                shutil.rmtree(venv_path, ignore_errors=1)
                assert not os.path.exists(venv_path)
            
            if create == 1 and os.path.isdir(venv_path):
                # Don't update existing venv, don't call <setupfn>, don't
                # install <packages>.
                do_setup_venv = False
                log(f'autovenv.enter(): Will not updating existing venv or call setupfn or install packages, because {create=}.')
            else:
                if create_kwargs is None:
                    # Need to set symlinks to mimic what `python -m venv` does,
                    # otherwise we fail to update an existing venv on linux
                    # because of `shutil.SameFileError`.
                    symlinks = os.name != 'nt'
                    kwargs = dict(symlinks=symlinks, with_pip=True)
                else:
                    kwargs = create_kwargs
                log(f'autovenv.enter(): Create/update venv with venv.create(), {kwargs=}.')
                venv.create(venv_path, **kwargs)
            
            # We need a builder context even if we haven't
            # called venv.create(), so make a dummy call of
            # `builder.ensure_directories()` here.
            builder = venv.EnvBuilder()
            builder_context = builder.ensure_directories(venv_path)
            
            # Enter the venv by adding to the environment.
            log(f'autovenv.enter(): Updating environ to enter the venv.')
            os.environ['PATH'] = builder_context.bin_path + os.pathsep + os.environ['PATH']
            os.environ['VIRTUAL_ENV'] = venv_path
            
            # Also set AUTOVENV_VENV_PATH so we know later on if we are
            # rerunning in the autovenv venv
            os.environ['AUTOVENV_VENV_PATH'] = venv_path
            
            # Setup/install packages.
            if do_setup_venv:
                log(f'autovenv.enter(): {do_setup_venv=} {setupfn=} {packages=}.')
                if setupfn:
                    log(f'Calling setupfn().')
                    setupfn(builder_context)
                if packages:
                    if isinstance(packages, str):
                        packages = [packages]
                    log(f'autovenv.enter(): Installing packages: {packages}.')
                    subprocess.run(
                            [builder_context.env_exe, '-m', 'pip', 'install', '--quiet', '--upgrade']
                                + packages,
                            check=1,
                            )
                else:
                    log(f'autovenv.enter(): No packages to install.')
            
            # We are about to rerun the current process.
            #
            # Set AUTOVENV_N_CURRENT to current AUTOVENV_N so that we know what
            # to do when we are called again.
            #
            # We also need to reset AUTOVENV_N back to its initial value.
            #
            AUTOVENV_N_CURRENT = AUTOVENV_N
            os.environ['AUTOVENV_N_CURRENT'] = str(AUTOVENV_N_CURRENT)
            os.environ['AUTOVENV_N'] = _g_initial_AUTOVENV_N
            return builder_context
        
        if use_existing_venv and sys.prefix != sys.base_prefix:
            # Just install packages into current venv.
            log(f'autovenv.enter(): Using existing venv because {use_existing_venv=}. {sys.prefix=}.')
            if packages:
                if isinstance(packages, str):
                    packages = [packages]
                log(f'autovenv.enter(): Installing packages into current venv: {packages}.')
                subprocess.run(
                        [sys.executable, '-m', 'pip', 'install', '--quiet', '--upgrade']
                            + packages,
                        check=1,
                        )
            AUTOVENV_N_CURRENT = AUTOVENV_N
            os.environ['AUTOVENV_N_CURRENT'] = str(AUTOVENV_N_CURRENT)
                
        elif venv_path:
            builder_context = setup(venv_path, packages, create=create)
            
            # Rerun the current python program in the venv.
            if platform.system() == 'Windows':
                # Have seen odd behaviour with os.execve() where empty string
                # args appear to be removed.  So we use a child process
                # instead.
                log(f'autovenv.enter(): Rerunning with subprocess.run(), {builder_context.env_exe=}.')
                cp = subprocess.run([builder_context.env_exe] + sys.argv, check=0)
                sys.exit(cp.returncode)
            else:
                log(f'autovenv.enter(): Rerunning with os.execv(), {builder_context.env_exe=}.')
                os.execv(builder_context.env_exe, [builder_context.env_exe] + sys.argv)
        
        else:
            # Use tempfile.TemporaryDirectory() to create venv directory that
            # will be automatically removed after use.
            with tempfile.TemporaryDirectory(prefix='autovenv-') as venv_path:  # pylint: disable=redefined-argument-from-local.
                log(f'autovenv.enter(): Using unique venv directory: {venv_path}')
                
                builder_context = setup(venv_path, packages, create=2)
                
                # Rerun the current program in the venv. We need to use
                # a child process instead of os.execve(), so that our
                # tempfile.TemporaryDirectory gets to delete the venv
                # directory.
                log(f'autovenv.enter(): Rerunning with subprocess.run(), {builder_context.env_exe=}.')
                cp = subprocess.run([builder_context.env_exe] + sys.argv, check=0)
                sys.exit(cp.returncode)
