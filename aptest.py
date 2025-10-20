#! /usr/bin/env python3

'''Developer build/test script for Artifex packages.

Args:

* Command line arguments are called parameters if they start with `-`,
  otherwise they are called commands.
* Parameters are evaluated first in the order that they were specified.
* Then commands are run in the order in which they were specified.
* Usually command `test` would be specified after commands such as `build`.
* Parameters and commands can be interleaved but it may be clearer to separate
  them on the command line.


Examples:

    aptest.py -p pip: -P pip: -l pip: build test
    
        Installs pymupdf, pymupdfpro and pymupdf_layout from pypi.org and runs
        tests on each of them.
    
    aptest.py -p PyMuPDF -P PyMuPDFPro -m mupdf -l sce build test
    
        Builds and installs pymupdf, pymupdfpro and pymupdf_layout from local
        directories. Then runs tests on each of them.
    
    aptest.py -p git: -P git: -l git: build test
    
        * Clones/updates local git repositories for each of pymupdf, pymupdfpro
          and pymupdf_layout.
        * Build/install/test each package.
    
    aptest.py -r @github -p git: -P git -l git: cibw
        * Runs aptest.py on Github.
        * Uses latest code in default git repositories.
        * Downloads the logs and wheels from Github to local machine.
    
    aptest.py -g -p git: -P git -l git: cibw upload
        * Runs cibuildwheel on Github to build wheels and test pymupdf,
          pymupdfpro and pymupdf-layout wheels, using latest code in default git
          repositories.
        * Downloads wheels from Github artifacts to local machine.
        * Uploads wheels to pypi.org.

Args:

    Options:
    
        -a <env_name>
            Read next space-separated argument(s) from environmental variable
            <env_name>.
            * Does nothing if <env_name> is unset.
            * Useful when running via Github action.
    
        -b <packages>
            Modifies behaviour of 'build' command to only build/install only
            the specified comma-separated packages instead of all packages
            specified by `-i`.
        
        --build-pyodide 0|1
            Modifies 'build' command to build pyodide wheels.

            We clone `emsdk.git`, set it up, and run `pyodide
            build`. This runs our setup.py with CC etc set up to
            create Pyodide binaries in a wheel called, for example,
            `PyMuPDF-1.23.2-cp311-none-emscripten_3_1_32_wasm32.whl`.

            It seems that sys.version must match the Python version inside
            emsdk; as of 2025-02-14 this is 3.12. Otherwise we get build errors
            such as: [wasm-validator error in function 723] unexpected false:
            all used features should be allowed, on ...
        
        --build-wheels 0|1
            Makes `build` command build wheel(s) in wheelhouse/ and install
            them, instead of direct build and install.
        
        ? -c <packages>
            The 'cibw' command runs only on the specified packages.
        
        --cibw-name <cibw_name>
            Name to use when installing cibuildwheel, e.g.:
                --cibw-name cibuildwheel==3.0.0b1
                --cibw-name git+https://github.com/pypa/cibuildwheel
            Default is `cibuildwheel`, i.e. the current release.

        --cibw-pyodide 0|1
             Experimental, make `cibw` command build a pyodide wheel.
             2025-05-27: this fails when building mupdf C API - `ld -r -b
             binary ...` fails with:
                emcc: error: binary: No such file or directory ("binary"
                was expected to be an input file, based on the commandline
                arguments provided)

        --cibw-pyodide-version <cibw_pyodide_version>
            Override default Pyodide version to use with `cibuildwheel`
            command. If empty string we use cibuildwheel's default.

        --cibw-skip-add-defaults 0|1
            If 1 (the default) we add defaults to CIBW_SKIP such as `pp*` (to
            exclude pypy) and `cp3??t-*` (to exclude free-threading).
        
        -e <name>=<value>
            Set specified environment variable.
        
        --graal 0|1
            If '1' we use Graal environment.

            As of 2025-08-04, if specified:
            * We assert-fail if cibw and non-cibw commands are specified.
            * If `cibw` is specified:
                * We use a conventional venv.
                * We set CIBW_ENABLE=graalpy.
                * We set CIBW_BUILD = 'gp*'.
            * Otherwise:
                * We don't create a conventional venv.
                * Clone the latest pyenv and build it.
                * Use pyenv to install graalpy.
                * Use graalpy to create venv.

            [After the first time, suggest `-v 1` to avoid delay from
            updating/building pyenv and recreating the graal venv.]
    
        --help
        -h
            Show help.
    
        -i <package-name> <location>
            Add an input package.
            package-name:
                One of: mupdf pymupdf pro layout
                If empty string will be ignored except that `-r` will sync to
                remote.
            location:
                `pip:`
                    Install from pypi.org using pip.
                `pip:==<version>`
                    Install specified version from pypi.org.
                `git:[-b <branch>] [-t <tag>] [<remote>]`
                    Clone/update from git remote, optionally overriding default
                    branch/tag/remote.

                    The local git repository will be called
                    `git-<package-name>`.
                <local-dir>
                    Local directory, typically a git checkout.

        -l <location>
            Alias for `-i layout <location>
        
        -m <location>
            Alias for `-i mupdf <location>
        
        -o <os_names>
            Control which OS's we run on. If current OS is not in
            (comma-separated) list, we do nothing. <os_names> is case
            insensitive.
        
        -p <location>
            Alias for `-i pymupdf <location>
        
        -P <location>
            Alias for `-i pro <location>
        
        -r <remote>
        
            Rerun ourselves on remote machine(s) and on success copy wheels
            back to local machines.
        
            If remote='github', run on Github:
            
                * We push specified local checkouts directories (specified
                  by -i, -m, -p etc) to branches called `aptest-$USER`in the
                  equivalent repositories in github.com/ArtifexSoftware/.

                * We rerun the aptest.py command on Github machines, changing
                  -i, -m etc args to use git: to refer to the above
                  repostories.

                * On success we copy Github logs and artifacts
                  and extracted wheels etc to local directory
                  gh_workflow_YYYY-MM-DD-<workflowid>. Wheels are copied in
                  flat format into gh_workflow_YYYY-MM-DD-<workflowid>-union/.
            
            Otherwise <remote> should be a ssh-style remote user/machine such
            as 'macmini' or 'username@macmini'.
            
                * Specify a ssh jump host using `::`, for example `-r
                  <gataeway>::<internal-name>`.

                * Local checkouts specified by `-i` are coped to the remote
                  using rsync, then `git clean -f` is run on the remote.

                * On success wheels are copied back into local directory
                  aptest/wheelhouse/.
        
        -t <packages>
            Comma-separated ordered list of modifications to the list of
            packages tested by the 'test' command.
            
            This list defaults to all packages specified by `-i`. Then for each
            comma-separated item in <packages>:
            
                '-<name>' removes package <name> from the list.
                '+<name>' and '<name>' adds package <name> to the list.
                '-' removes all packages from the list.
            
            In addition if the first item does not start with '+' or '-' we
            first remove all packages from the list.
            
            For example:
                -t -,pro
                    Tests only pro.
                -t -mupdf,-layout
                    Removes mupdf and layout from list of packages to test.

        -v <venv>
            0 - do not use a venv.
            1 - Use venv. If it already exists, we assume the existing
                directory was created by us earlier and is a valid venv
                containing all necessary packages; this saves a little time.
            2 - Use venv.
            3 - Use venv but delete it first if it already exists.
            
            The default is 2.
        
        --pyodide-build-version <version>
            Version of Python package pyodide-build to use with `pyodide`
            command.

            If None (the default) `pyodide` uses the latest available version.
            2025-02-13: pyodide_build_version='0.29.3' works.
    
        --pytest <pytest-flags>
            Specify pytest flags, for example `--pytest '-k test_123'`.

        --pytest-wrap gdb|valgrind|helgrind
            Run tests under specified tool
        
        --python <python>
            Set Python to use. If set we re-run ourselves using specified
            python command.
        
        --remote-github-workflow <workflow_id>
            Changes behaviour of `-r @github`. Don't run anything Github,
            instead continue from previous `-r @github` invocation by waiting
            for <workflow_id> to finish and then downloadings logs and wheels
            etc. Note that you still need to include `-r @github cibw`.
        
        --remote-prefix <remote_prefix>
            Run remote using specified Python command. Ignored by `-r @github`.
        
        --remote-do 0|1
            [For debugging.]
            If 0 we don't sync to remote and we don't run any commands on
            remote. But we do sync remote wheels to local.
        
        --sdists 0|1
            If 1, the 'build' and 'cibw' commands will also build sdists.
        
        --swig <swig>
            Use <swig> instead of the `swig` command.
            
            Unix only:
                Clone/update/build swig from a git repository using 'git:' prefix.
                
                We default to https://github.com/swig/swig.git branch master, so these
                are all equivalent:
                
                    --swig 'git:--branch master https://github.com/swig/swig.git'
                    --swig 'git:--branch master'
                    --swig git:
                
                2025-08-18: This fixes building with py_limited_api on python-3.13.

        --swig-quick 0|1
            If 1 and `--swig` starts with 'git:', we do not update/build swig if
            already present.
    
        --system-packages 0|1
            If 1, automatically install required system packages such as
            Valgrind, using `apt` on Linux and `brew` on MacOS. Default is 1 if
            running as Github action, otherwise 0.
    
        --system-site-packages 0|1
            If 1, use `--system-site-packages` when creating venv. Defaults is 0.
        
        --github-upload 0|1
            If 1, if `-r @github` is used then on sccess we ask the user to
            confirm and then upload wheels to pypi.org.
        
    Commands:
    
        build
            Builds and installs packages specified by `-i` into venv.

        cibw
            Build and test packages using cibuildwheel. Wheels are placed
            in directory `wheelhouse`.
            * We do not install wheels and it is generally not useful to do
            `cibw test`.

            If CIBW_BUILD is unset, we set it as follows:
            * On Github we build and test all supported Python versions.
            * Otherwise we build and test the current Python version only.

            If CIBW_ARCHS is unset we set $CIBW_ARCHS_WINDOWS, $CIBW_ARCHS_MACOS
            and $CIBW_ARCHS_LINUX to auto64 if they are unset.

        test
            Runs pytest tests.

        upload
            Only works with `-r @github` and intended for use with `cibw` only.

            Uploads wheels to pypi.org. Asks for confirmation before uploading.
            

Other:

* If we are not already running inside a Python venv, we automatically create a
  venv and re-run ourselves inside it (also see the -v option).
* Tests use whatever packages are installed in the venv.
* We run tests with pytest.

* One can generate call traces by setting environment variables in debug
  builds. For details see:
  https://mupdf.readthedocs.io/en/latest/language-bindings.html#environmental-variables

Environment:

    APTEST_options
        Is prepended to command line args.
'''

import glob
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import textwrap
import time


g_root_abs = os.path.abspath( f'{__file__}/..')

try:
    sys.path.insert(0, g_root_abs)
    import github
    import pipcl
finally:
    del sys.path[0]

g_root = pipcl.relpath(g_root_abs)


# With cibw we build and test Python 3.x for x in this range.
python_versions_minor = range(10, 13+1)

def cibw_cp(*version_minors):
    '''
    Returns <version_tuples> in 'cp39*' format, e.g. suitable for CIBW_BUILD.
    '''
    ret = list()
    for version_minor in version_minors:
        ret.append(f'cp3{version_minor}*')
    return ' '.join(ret)


def git_push(path, repository, remote_branch, tmpcommit=True, doit=True):
    '''
    Pushes <path> to <repository> (or 'origin' if None).
    
    If <tmpcommit> is true, we do a temporary commit of any uncommited changes
    before pushing, then restore. Note that this will forget about newly added
    files.
    '''
    _sha, _comment, _diff, branch = pipcl.git_info(path)
    if not doit:
        return branch
    if tmpcommit:
        diff = pipcl.run(f'cd {path} && git diff --ignore-submodules=dirty', capture=1)
        if diff:
            try:
                pipcl.run(f'cd {path} && git commit -m "ghtest.py temporary commit" -a')
            except Exception:
                log(f'Temporary commit failed. {diff=}.')
                raise
    try:
        #pipcl.run(f'cd {path} && GIT_SSH_COMMAND="ssh -i ~/.ssh/id_rsa2" git push -fv {repository} HEAD:{remote_branch}')
        pipcl.run(
                f'cd {path} && GIT_SSH_COMMAND="ssh -i ~/.ssh/id_rsa2" git push -fv {repository or "origin"} HEAD:{remote_branch}',
                prefix='git push: ',
                )
    finally:
        if tmpcommit and diff:
            pipcl.run(f'cd {path} && git reset HEAD~1')
    return branch


def sync_reverse(remote, remote_dir, path_remote, path_local, ssh_command, filters=None, verbose=1):
    '''
    Uses rsync to copy from remote machine to local.

    remote:
        Remote spec.
    remote_dir:
        Root directory on remote.
    path_remote:
        Remote path, relative to <remote_dir>.
    path_local:
        Local path.
    filters:
        List of rsync filter args, e.g. ['--include=foo.*txt',
        'exclude=*']. They should not be escaped for the shell - we use shlex
        to quote each filter.
    '''
    ssh_command2 = ssh_command
    if remote:
        ssh_command2 += f' {remote}'
    command = (
            f'rsync -aizr '
            f'{"--stats " if verbose else ""}'
            f'--rsh {shlex.quote(ssh_command2)} '
            )
    if filters:
        if isinstance(filters, str):
            filters = (filters,)
        command += f'{shlex.join(filters)} '
    command += (
            f':{remote_dir}/{path_remote} {path_local}'
            )
    pipcl.run(command, prefix=f'reverse sync {path_remote} => {path_local}: ')
        

def sync(remote, remote_dir, path, ssh_command, verbose):
    '''
    Syncs <path> to <remote>:<remote_dir>/ using rsync.

    If <path>/.git is a directory we sync only files known to git, and return
    true.
    '''
    ret = None
    #ssh_command2 = f'{ssh_command} {remote}'
    ssh_command2 = f'{ssh_command}'
    if remote:
        ssh_command2 += f' {remote}'
    command = (
            f'rsync -Raizr '
            f'{"--stats " if verbose else ""}'
            f'--rsh {shlex.quote(ssh_command2)} '
            )
    path = os.path.relpath(path)
    path = path.rstrip('/')
    filenames_path = None
    try:
        if os.path.isdir(f'{path}/.git'):
            # Sync only files known to git.
            ret = True
            pipcl.log(f'syncing git directory: {path}')
            filenames = pipcl.git_items(path, submodules=1)
            filenames_path = f'remote-sync-paths-{os.getpid()}-{time.time()}'
            with open(filenames_path, 'w') as f:
                for filename in filenames:
                    filename_path = f'{path}/{filename.strip()}'
                    if os.path.isfile(filename_path):
                        f.write(f'{filename_path}\n')
                f.write(f'{path}/.git')
            command += (
                        f'--files-from={filenames_path} '
                        f'. :{remote_dir}/'
                        )
        else:
            # Sync the file or directory directly.
            pipcl.log(f'syncing: {path}')
            command += f'{path} :{remote_dir}/'
        pipcl.run(command, prefix=f'sync {path}: ')
    finally:
        if filenames_path:
            fs_remove(filenames_path)
    return ret


def name_info(name):
    class NameInfo:
        pass
    ret = NameInfo()
    ret.submodules = True
    if name == 'mupdf':
        ret.name_full = 'mupdf'
        ret.git_remote = 'git@github.com:ArtifexSoftware/mupdf.git'
        ret.git_branch = 'master'
    elif name == 'pymupdf':
        ret.name_full = 'pymupdf'
        ret.git_remote = 'git@github.com:pymupdf/PyMuPDF.git'
        ret.git_branch = 'main'
    elif name == 'pro':
        ret.name_full = 'pymupdfpro'
        ret.git_remote = 'git@github.com:ArtifexSoftware/PyMuPDFPro.git'
        ret.git_branch = 'main'
    elif name == 'layout':
        ret.name_full = 'pymupdf_layout'
        ret.git_remote = 'git@github.com:ArtifexSoftware/sce.git'
        ret.git_branch = 'master'
        # Have seen problems with clong after we've pushed local checkout to
        # branch but submodule `mupdf` not present.
        ret.submodules = False
    else:
        assert 0, f'{name=}'
    return ret


class ArgsIterator:
    def __init__(self, argv):
        self.argv = argv
        self.pos = 0
    
    def __next__(self):
        if self.pos == len(self.argv):
            raise StopIteration()
        ret = self.argv[self.pos]
        self.pos += 1
        return ret

def main(argv):

    pipcl.show_system()
    
    if github_workflow_unimportant():
        return
    
    python = None
    remote = None
    remote_dir = 'artifex-remote'
    remote_do = True
    remote_github_workflow_id = None
    remote_prefix = None
    remote_ssh = None
    show_help = False
    venv = 2
    
    class State:
        pass
    state = State()
    state.build_isolation = None
    state.build_wheels = None
    state.cibw_name = 'cibuildwheel'
    state.cibw_pyodide = None
    state.cibw_pyodide_version = None
    state.cibw_skip_add_defaults = True
    state.cibw_test_project = None
    state.cibw_test_project_setjmp = False
    state.commands = list()
    state.env_extra = dict()
    state.github_upload = None
    state.graal = False
    state.os_names = list()
    state.packages = dict()   # map from name to location.
    state.packages_build = list() # Sorted list of names.
    state.packages_test = list()  # Sorted list of names.
    state.pybind = False
    state.pyodide_build_version = None
    state.pytest_options = ''
    state.pytest_wrap = None
    state.sdists = False
    state.swig = 'pip:==4.3.1'
    state.swig_quick = None
    state.system_packages = True if os.environ.get('GITHUB_ACTIONS') == 'true' else False
    state.system_site_packages = False
    state.valgrind = False
    
    def add_package(name, location, args_pos):
        if name:
            state.packages[name] = (location, args_pos)
            state.packages_build.append(name)
            state.packages_test.append(name)

            names = [
                'mupdf',
                'pymupdf',
                'pro',
                'layout'
                ]
            keyfn = lambda name: names.index(name)
            state.packages_build.sort(key=keyfn)
            state.packages_test.sort(key=keyfn)
        else:
            state.packages.append(os.path.dirname(location), location)
    
    def apply_deltas(items, deltas, check=1):
        if deltas and not deltas[0].startswith(('+', '-')):
            del items[:]
        for delta in deltas:
            if delta == '-':
                del items[:]
            elif delta.startswith('-'):
                try:
                    items.remove(delta[1:])
                except Exception:
                    if check:
                        raise
            else:
                if delta.startswith('+'):
                    delta = delta[1:]
                items.append(delta)
    
    # Parse args and update the above state. We do this before moving into a
    # venv, partly so we can return errors immediately.
    #
    options = os.environ.get('APTEST_options', '')
    options = shlex.split(options)    
    args_list = options + argv[1:]
    args = ArgsIterator(args_list)
    i = 0
    while 1:
        try:
            arg = next(args)
        except StopIteration:
            arg = None
            break
        
        if 0:
            pass
        
        elif arg == '-a':
            pos1 = args.pos
            _name = next(args)
            _value = os.environ.get(_name, '')
            pos2 = args.pos
            new_args = shlex.split(_value)
            #args_list = shlex.split(_value) + list(args)
            #args = iter(args_list)
            args.argv[pos1:pos2] = new_args
            args.pos = pos1
        
        elif arg == '-b':
            state.packages_build = next(args).split(',')
        
        elif arg == '--build-isolation':
            state.build_isolation = int(next(args))
        
        elif arg == '--build-wheels':
            state.build_wheels = int(next(args))
        
        #elif arg == '--cibw-release-1':
        #    cibw_sdist = True
        #    env_extra['CIBW_ARCHS_LINUX'] = 'auto64'
        #    env_extra['CIBW_ARCHS_MACOS'] = 'auto64'
        #    env_extra['CIBW_ARCHS_WINDOWS'] = 'auto'    # win32 and win64.
        #    env_extra['CIBW_SKIP'] = '*i686 *musllinux*aarch64* cp3??t-*'
        #    cibw_skip_add_defaults = 0
        #
        #elif arg == '--cibw-release-2':
        #    # Testing only first and last python versions because otherwise
        #    # Github times out after 6h.
        #    env_extra['CIBW_BUILD'] = cibw_cp(python_versions_minor[0], python_versions_minor[-1])
        #    env_extra['CIBW_ARCHS_LINUX'] = 'aarch64'
        #    env_extra['CIBW_SKIP'] = '*i686 *musllinux*aarch64* cp3??t-*'
        #    cibw_skip_add_defaults = 0
        #    os_names = ['linux']
        #
        #elif arg == '--cibw-archs-linux':
        #    env_extra['CIBW_ARCHS_LINUX'] = next(args)
        #    
        elif arg == '--cibw-name':
            state.cibw_name = next(args)
        
        elif arg == '--cibw-pyodide':
            state.cibw_pyodide = int(next(args))
        
        elif arg == '--cibw-pyodide-version':
            state.cibw_pyodide_version = next(args)
        
        elif arg == '--cibw-skip-add-defaults':
            state.cibw_skip_add_defaults = int(next(args))
        
        #elif arg == '--cibw-test-project':
        #    cibw_test_project = int(next(args))
        #
        #elif arg == '--cibw-test-project-setjmp':
        #    cibw_test_project_setjmp = int(next(args))
        #
        #elif arg == '--dummy':
        #    env_extra['PYMUPDF_SETUP_DUMMY'] = '1'
        #    env_extra['CIBW_TEST_COMMAND'] = ''
        #
        elif arg == '-e':
            _nv = next(args)
            assert '=' in _nv, f'-e <name>=<value> does not contain "=": {_nv!r}'
            _name, _value = _nv.split('=', 1)
            state.env_extra[_name] = _value
        
        elif arg == '--graal':
            state.graal = int(next(args))
        
        elif arg in ('-h', '--help'):
            state.show_help = True
        
        elif arg == '-i':
            _name = next(args)
            _location = next(args)
            add_package(_name, _location, args.pos - 1)
        
        elif arg == '-l':
            add_package('layout', next(args), args.pos - 1)
        
        elif arg == '-m':
            add_package('mupdf', next(args), args.pos - 1)
        
            #_mupdf = next(args)
            #if _mupdf == '-':
            #    _mupdf = None
            #elif _mupdf.startswith(':'):
            #    _branch = _mupdf[1:]
            #    _mupdf = f'git:--branch {_branch} https://github.com/ArtifexSoftware/mupdf.git'
            #    env_extra['PYMUPDF_SETUP_MUPDF_BUILD'] = _mupdf
            #elif _mupdf.startswith('git:') or '://' in _mupdf:
            #    env_extra['PYMUPDF_SETUP_MUPDF_BUILD'] = _mupdf
            #else:
            #    assert os.path.isdir(_mupdf), f'Not a directory: {_mupdf=}'
            #    env_extra['PYMUPDF_SETUP_MUPDF_BUILD'] = os.path.abspath(_mupdf)
            #    mupdf_sync = _mupdf
        
        elif arg == '-o':
            state.os_names += next(args).lower().split(',')
        
        elif arg == '-p':
            add_package('pymupdf', next(args), args.pos - 1)
        
        elif arg == '-P':
            add_package('pro', next(args), args.pos - 1)
        
        elif arg == '-p':
            state.pytest_options += f' {next(args)}'
        
        elif arg == '-P':
            state.system_packages = int(next(args))
        
        elif arg == '-r':
            remote_arg = args.pos
            remote = next(args)
        
        elif arg == '-t':
            _names = next(args).split(',')
            apply_deltas(state.packages_test, _names)
        
        elif arg == '--pybind':
            state.pybind = int(next(args))
        
        elif arg == '--pyodide-build-version':
            state.pyodide_build_version = next(args)
        
        elif arg == '--pytest':
            state.pytest_options = next(args)
        
        elif arg == '--pytest-wrap':
            state.pytest_wrap = next(args)
        
        elif arg == '--python':
            python_args_pos = args.pos
            python = next(args)
        
        elif arg == '--remote-do':
            remote_do = int(next(args))
        
        elif arg == '--remote-github-workflow':
            remote_github_workflow_id = next(args)
        
        elif arg == '--remote-prefix':
            remote_prefix = next(args)
        
        elif arg == '--sdists':
            state.sdists = int(next(args))
        
        elif arg == '--system-site-packages':
            state.system_site_packages = int(next(args))
        
        elif arg == '--swig':
            state.swig = next(args)
        
        elif arg == '--swig-quick':
            state.swig_quick = int(next(args))
        
        elif arg == '--system-packages':
            state.system_packages = int(next(args))
        
        elif arg == '--system-site-packages':
            state.system_site_packages = int(next(args))
        
        elif arg == '--github-upload':
            state.github_upload = int(next(args))
        
        elif arg == '-v':
            state.venv = int(next(args))
            assert state.venv in (0, 1, 2, 3), f'Invalid {state.venv=} should be 0, 1, 2 or 3.'
        
        elif arg.startswith('-'):
            assert 0, f'Unrecognised option: {arg=}.'
            
        elif arg in ('build', 'cibw', 'test'):
            state.commands.append(arg)
        
        else:
            assert 0, f'Unrecognised command: {arg=}.'
    
    if show_help:
        print(__doc__)
        return
    
    # Check whether we should run with `-o <osname>`.
    if not remote:
        os_self = platform.system().lower()
        oss = [os_self]
        pipcl.log(f'{oss=}')
        apply_deltas(oss, state.os_names, check=0)
        pipcl.log(f'{state.os_names=}')
        pipcl.log(f'{os_self=}')
        if os_self not in oss:
            pipcl.log(f'Not running on {os_self=}: {state.os_names=}')
            return
    
    # Rerun with different python if `--python` is specified.
    if not remote and python:
        python_version = pipcl.run(f'{python} -c "import platform; print(platform.python_version())"', capture=1)
        python_version_tuple = tuple(python_version.split('.'))
        if platform.python_version_tuple()[:2] == python_version_tuple[:2]:
            pipcl.log(f'Already running on required python. {platform.python_version_tuple()=} {python_version_tuple=}')
        else:
            pipcl.log(f'{python=}: rerunning because {platform.python_version_tuple()[:2]=} != {python_version_tuple[:2]=}')
            argv = args.argv[:]
            argv[python_args_pos] = ''
            e = pipcl.run(f'{python} {shlex.join(argv)}', check=0)
            sys.exit(e)
            
    
    # Hard-coded ssh/git key paths.
    pymupdfpro_key_path_leaf = 'thirdparty-so-key'
    artifex_software_ssh_key = 'artifex-software-ssh-key'
    
    if remote:
        argv = args.argv[:]
        argv[remote_arg] = ''   # Change `-r github` to `-r ''`.
        if remote == '@github':
            branch = f'aptest-{os.environ["USER"]}'    #-{time.strftime("%F-%T")}'
            pipcl.log(f'{branch=}.')

            if remote_github_workflow_id:
                workflow_id = remote_github_workflow_id
            else:
                # Push ourselves to Git.
                git_push(g_root, 'git@github.com:ArtifexSoftware/aptest.git', branch)

                # Push specified local package repositorie to Github and update args to
                # point to new location.
                for package_name, (package_location, args_pos) in state.packages.items():
                    if not package_location.startswith(('git:', 'pip:')):
                        # Push to a Github branch and update argv[] to refer to this
                        # Github branch.
                        info = name_info(package_name)
                        pipcl.log(f'{package_name=}.')
                        pipcl.log(f'{info.git_remote=}.')
                        if 0 and package_name == 'mupdf':
                            # We can't non-fast-forward push to ghostscript.com:/home/git/mupdf.git.
                            git_remote = 'git@github.com:ArtifexSoftware/mupdf.git'
                            git_push(package_location, git_remote, branch)
                            argv[args_pos] = f'git:-b {branch} {git_remote}'
                        else:
                            git_push(package_location, info.git_remote, branch)
                            argv[args_pos] = f'git:-b {branch} {info.git_remote}'

                # Run ourselves on Github, passing argv.
                data = dict(
                        ref = branch,
                        inputs = dict(args=shlex.join(argv)),
                        )
                workflow_id = github.gh_run_workflow(
                        'https://api.github.com/repos/ArtifexSoftware/aptest',
                        'test.yml',
                        data,
                        )
            
            assert isinstance(workflow_id, str)
            github.gh_workflow_download_multiple(
                    #rest_url_base,
                    'https://api.github.com/repos/ArtifexSoftware/aptest',
                    'test.yml',
                    workflow_id,
                    #extra_wheels=upload_extra_wheels,
                    upload=state.github_upload,
                    )
        
        else:
            verbose = 1
            jumps = None
            if not remote_ssh:
                jumps = remote.split('::')
                jumps, remote = jumps[:-1], jumps[-1]
            colon = remote.rfind(':')
            if colon >= 0:
                remote, remote_dir = remote[:colon], remote[colon+1:]
                pipcl.log(f'{remote=}')
            if jumps:
                pipcl.log(f'{jumps=} {remote=}')
                ssh_command = 'ssh'
                for j in jumps:
                    ssh_command += f' -J {j}'
                ssh_command += f' {remote}'
                remote = None
            elif remote_ssh:
                ssh_command = remote
                remote = None
            else:
                ssh_command = 'ssh'
            pipcl.log(f'{ssh_command=}')

            if remote_do:
                git_paths = list()
                for package_name, (package_location, args_pos) in state.packages.items():
                    if not package_location.startswith(('git:', 'pip:')):
                        if sync(remote, remote_dir, package_location, ssh_command=ssh_command, verbose=verbose):
                            git_paths.append(package_location)

                # Sync aptest/ checkout.
                if sync(remote, remote_dir, g_root, ssh_command=ssh_command, verbose=verbose):
                    git_paths.append(g_root)

                if 'pro' in state.packages_build or 'layout' in state.packages_build:
                    if os.path.isfile(artifex_software_ssh_key):
                        sync(remote, remote_dir, artifex_software_ssh_key, ssh_command=ssh_command, verbose=verbose)
                    else:
                        pipcl.log(f'## Warning: may not be able to remote clone/update pro or layout checkouts because not a file: {artifex_software_ssh_key}')

                if 'pro' in state.packages_build:
                    if os.path.isfile(pymupdfpro_key_path_leaf):
                        sync(remote, remote_dir, pymupdfpro_key_path_leaf, ssh_command=ssh_command, verbose=verbose)
                    else:
                        pipcl.log(f'## Warning: may not be able to remote build SmartOffice because not a file: {artifex_software_ssh_key}')
                    sync(remote, remote_dir, pymupdfpro_key_path_leaf, ssh_command=ssh_command, verbose=verbose)

                # Run remote command.
                #
                remote_command = f'cd {remote_dir} && '
                for git_path in git_paths:
                    # We exclude *.tar.gz to avoid pymupdf re-downloading mupdf .tar.gz file.
                    remote_command += f'(cd {git_path} && git clean -e "*.tar.gz" -f) && '
                if remote_prefix:
                    remote_command += f'{remote_prefix} '
                elif remote and 'windows' in remote:
                    remote_command += f'py '
                remote_command += f'{os.path.basename(g_root_abs)}/aptest.py {shlex.join(argv)}'

                command = f'{ssh_command} {remote if remote else ""} {shlex.quote(remote_command)}'
                #if tee_out is None:
                #    tee_out = f'out-{remote}'
                pipcl.log(f'{command=}')
                pipcl.log(f'{ssh_command=}')

                #with open(tee_out, 'w') as f:
                #    jlib.system(command, prefix=f'{remote}: ', out=['log', f])
                pipcl.run(command, prefix=f'{remote}: ')

            if 1:
                # Copy remote wheels back to local machine.
                filters = list()
                for package in state.packages_build:
                    info = name_info(package)
                    filters.append(f'--include={info.name_full}-*.whl')
                    filters.append(f'--include={info.name_full}-*.tar.gz')
                filters.append('--exclude=*')
                sync_reverse(
                        remote, remote_dir,
                        f'{g_root}/wheelhouse/',
                        f'{g_root}/wheelhouse/',
                        ssh_command=ssh_command,
                        filters=filters,
                        )

        return
        
    if state.commands:
        if venv:
            # Rerun ourselves inside a venv if not already in a venv.
            if not venv_in():
            
                if state.graal:
                    if 'cibw' in state.commands:
                        # We don't create graal/pyenv so wheel/build commands
                        # will not work.
                        assert 'build' not in state.commands
                if state.graal and 'cibw' not in state.commands:
                    # Re-run outselves in a pyenv/Graal venv.
                    # 2025-07-24: We need the latest pyenv.
                    graalpy = 'graalpy-24.2.1'
                    venv_name = f'venv-aptest-{graalpy}'
                    pyenv_dir = f'{g_root_abs}/pyenv-git'
                    os.environ['PYENV_ROOT'] = pyenv_dir
                    os.environ['PATH'] = f'{pyenv_dir}/bin:{os.environ["PATH"]}'
                    os.environ['PIPCL_GRAAL_PYTHON'] = sys.executable
                    
                    if venv >= 3:
                        shutil.rmtree(venv_name, ignore_errors=1)
                    if venv == 1 and os.path.exists(pyenv_dir) and os.path.exists(venv_name):
                        pipcl.log(f'{venv=} and {venv_name=} already exists so not building pyenv or creating venv.')
                    else:
                        pipcl.git_get(pyenv_dir, remote='https://github.com/pyenv/pyenv.git', branch='master')
                        pipcl.run(f'cd {pyenv_dir} && src/configure && make -C src')
                        pipcl.run(f'which pyenv')
                        pipcl.run(f'pyenv install -v -s {graalpy}')
                        pipcl.run(f'{pyenv_dir}/versions/{graalpy}/bin/graalpy -m venv {venv_name}')
                    e = pipcl.run(f'. {venv_name}/bin/activate && python {shlex.join(sys.argv)}',
                            check=False,
                            )
                else:
                    # Re-run outselves in a Python venv.
                    venv_name = f'venv-aptest-{platform.python_version()}-{int.bit_length(sys.maxsize+1)}'
                    e = venv_run(
                            sys.argv,
                            venv_name,
                            recreate=(venv>=2),
                            clean=(venv>=3),
                            )
                sys.exit(e)
    elif not remote_github_workflow_id:
        pipcl.log(f'Warning, no commands specified so nothing to do.')
    
    # Clone/update/build swig if specified.
    swig_binary = pipcl.swig_get(state.swig, state.swig_quick)
    #state.env_extra['PYMUPDF_SETUP_SWIG'] = swig_binary
    #state.env_extra['PYMUPDFPRO_SETUP_SWIG'] = swig_binary
    #state.env_extra['PYMUPDF_LAYOUT_SETUP_SWIG'] = swig_binary
    #if swig_binary:
    #    os.environ['PYMUPDF_SETUP_SWIG'] = swig_binary
    
    # Set environment variables to give access to required git repositories.
    #
    paths_to_delete = list()
    if (1   # we need this even for mupdf because we use git@github.com/... when cloning, not https.
            or 'pro' in state.packages_build
            or 'layout' in state.packages_build
            or 'layout' in state.packages_test
            ):
        # Allow access to private github.com/ArtifexSoftware/* repositories.
        
        # On Github ARTIFEX_SOFTWARE_SSH_KEY is set from repository secret.
        ARTIFEX_SOFTWARE_SSH_KEY = os.environ.get('ARTIFEX_SOFTWARE_SSH_KEY')
        if ARTIFEX_SOFTWARE_SSH_KEY:
            # Write to temp file.
            temp_key_path = f'{artifex_software_ssh_key}-tmp'
            paths_to_delete.append(temp_key_path)
            fs_write_key(temp_key_path, ARTIFEX_SOFTWARE_SSH_KEY)
            state.ssh_key_path_abs = os.path.abspath(temp_key_path)
        elif os.path.isfile(artifex_software_ssh_key):
            state.ssh_key_path_abs = os.path.abspath(artifex_software_ssh_key)
        else:
            pipcl.log('## May not be able to clone/update/test pro/layout because ARTIFEX_SOFTWARE_SSH_KEY unset and file {artifex_software_ssh_key!r} does not exist')
            state.ssh_key_path_abs = None
        if state.ssh_key_path_abs:
            # We need to use forward slashes on Windows.
            ssh_key_path_abs = state.ssh_key_path_abs.replace('\\', '/')
            GIT_SSH_COMMAND = f'ssh -i {ssh_key_path_abs} -o StrictHostKeyChecking=no'
            state.env_extra['GIT_SSH_COMMAND'] = GIT_SSH_COMMAND
            pipcl.log(f'Using {GIT_SSH_COMMAND=}.')
            #APTEST_SSH_KEY = os.path.abspath(key_path)
            #state.env_extra['APTEST_SSH_KEY'] = APTEST_SSH_KEY

    if 'pro' in state.packages_build:
        # The SmartOffice build requires remote git access.
        
        # On Github PYMUPDFPRO_SETUP_SOT_KEY is set from repository secret.
        PYMUPDFPRO_SETUP_SOT_KEY = os.environ.get('PYMUPDFPRO_SETUP_SOT_KEY')
        if PYMUPDFPRO_SETUP_SOT_KEY:
            pipcl.log(f'PYMUPDFPRO_SETUP_SOT_KEY is set.')
        else:
            # With non-github builds we rely on this file existing.
            PYMUPDFPRO_SETUP_SOT_KEY_PATH = os.path.abspath(pymupdfpro_key_path_leaf)
            if os.path.isfile(PYMUPDFPRO_SETUP_SOT_KEY_PATH):
                state.env_extra['PYMUPDFPRO_SETUP_SOT_KEY_PATH'] = PYMUPDFPRO_SETUP_SOT_KEY_PATH
                pipcl.log(f'Using {PYMUPDFPRO_SETUP_SOT_KEY_PATH=}.')
            else:
                pipcl.log('## May not be able to build pro because PYMUPDFPRO_SETUP_SOT_KEY unset and file {PYMUPDFPRO_SETUP_SOT_KEY_PATH!r} does not exist')
    
    def build_sdist(package, directory):
        if package == 'pymupdf':
            pipcl.run(
                    f'cd {directory} && python setup.py -d {g_root_abs}/wheelhouse sdist',
                    prefix='sdist {package}: ',
                    )
    
    try:
        # Handle commands.
        #
        have_installed = False
        for command in state.commands:
            pipcl.log(f'### {command=}.')
            if 0:
                pass

            elif command == 'build':

                pipcl.run(f'pip install --upgrade piprepo setuptools')
                pypi_local = os.path.abspath(f'aptest-pypi')
                pipcl.fs_ensure_empty_dir(pypi_local)
                pipcl.run(f'piprepo build {pypi_local}')
                os.makedirs(f'{g_root_abs}/wheelhouse', exist_ok=1)

                for package in state.packages_build:
                    pipcl.log(f'{package=}')
                    location, args_pos = state.packages[package]
                    if not location:
                        continue
                    info = name_info(package)
                    if location.startswith('pip:'):
                        assert info.name_full != 'mupdf', f'Not a package on pypi.org: {info.full_name}'
                        command = f'pip install -v'
                        command += f' {info.name_full}{location[4:]}'
                        pipcl.run(command)
                    else:
                        if location.startswith('git:'):
                            temp_key_path = None
                            directory = pipcl.git_get(
                                    local=f'git-{info.name_full}',
                                    remote=info.git_remote,
                                    branch=info.git_branch,
                                    text=location,
                                    env_extra=state.env_extra,
                                    )
                            # Update information to contain local directory. This
                            # allows 'test' command to work without repeating the
                            # call of pip.git_get().
                            state.packages[package] = directory, args_pos
                        else:
                            directory = location
                        directory_abs = os.path.abspath(directory)
                        pipcl.log(f'{package=}')
                        if package == 'mupdf':
                            state.env_extra['PYMUPDF_SETUP_MUPDF_BUILD'] = directory_abs
                            # fixme: be able to set to '' for system install?
                        else:
                            pipcl.run(f'pip uninstall -y {info.name_full}')
                            
                            if state.sdists:
                                build_sdist(package, directory)

                            if (package == 'pymupdf'
                                    and state.graal
                                    and (
                                        'pro' in state.packages_build
                                        or 'layout' in state.packages_build
                                        )
                                    ):
                                # As of 2025-08-07, pipcl does graal builds by running a
                                # non-graal build with graal python's include and library
                                # paths.
                                #
                                # In the non-graal build, out setup.py will still want
                                # to do `import pymupdf`, so we prepare a non-graal venv
                                # containing its own build of the specified pymupdf,
                                # and tell pipcl to use it when it does the non-graal
                                # build. Thus pro's setup.py will be able to do `import pymupdf`
                                # etc.
                                #
                                native_python = os.environ['PIPCL_GRAAL_PYTHON']
                                assert native_python
                                venv_native = 'venv-aptest-graal-native'
                                pipcl.run(f'{native_python} -m venv {venv_native}')
                                pipcl.run(
                                        f'. {venv_native}/bin/activate && pip install -v {directory_abs}',
                                        env_extra=state.env_extra,
                                        prefix='PyMuPDFPro/scripts/test.py install PyMuPDF graal native python: ',
                                        )
                                # Tell pipcl to use <venv_native> when it
                                # builds pro/layout later on.
                                state.env_extra['PIPCL_GRAAL_NATIVE_VENV'] = os.path.abspath(venv_native)

                            new_files = pipcl.NewFiles(f'{g_root_abs}/wheelhouse/{info.name_full}*.whl')
                            pipcl.run(
                                    f'pip wheel -v --extra-index-url file://{pypi_local}/simple -w {g_root_abs}/wheelhouse {directory_abs}',
                                    env_extra=state.env_extra,
                                    prefix=f'build {package}: ',
                                    )
                            wheel = new_files.get_one()
                            pipcl.run(
                                    f'pip install -v --extra-index-url file://{pypi_local}/simple {wheel}',
                                    env_extra=state.env_extra,
                                    prefix=f'install {package}: ',
                                    )
                        pipcl.run(
                                f'piprepo sync {g_root_abs}/wheelhouse {pypi_local}',
                                prefix='piprepo sync: ',
                                )

            elif command == 'cibw':
                # Build wheels for each package with cibuildwheel, adding to wheelhouse,
                # and using piprepo to update a local pypi-style tree.
                
                pipcl.run(f'pip install --upgrade --force-reinstall {state.cibw_name}', prefix=f'pip install {state.cibw_name}: ')
                pipcl.run(f'pip install --upgrade piprepo setuptools', prefix=f'pip install piprepo setuptools: ')
                cibw_pypi = os.path.abspath(f'cibw-pypi')
                #shutil.rmtree(cibw_wheelhouse, ignore_errors=True)
                #shutil.rmtree(cibw_pypi, ignore_errors=True)
                os.makedirs(cibw_pypi, exist_ok=1)
                pipcl.run(f'piprepo build {cibw_pypi}')

                # Some general flags.
                if 'CIBW_BUILD_VERBOSITY' not in state.env_extra:
                    state.env_extra['CIBW_BUILD_VERBOSITY'] = '1'

                # Add default flags to CIBW_SKIP.
                # 2025-10-07: `cp3??t-*` excludes free-threading, which currently breaks
                # some tests.

                if state.cibw_skip_add_defaults:
                    CIBW_SKIP = state.env_extra.get('CIBW_SKIP', '')
                    CIBW_SKIP += ' *i686 *musllinux* *-win32 *-aarch64 cp3??t-*'
                    CIBW_SKIP = CIBW_SKIP.split()
                    CIBW_SKIP = sorted(list(set(CIBW_SKIP)))
                    CIBW_SKIP = ' '.join(CIBW_SKIP)
                    state.env_extra['CIBW_SKIP'] = CIBW_SKIP

                # Set what wheels to build, if not already specified.
                if 'CIBW_ARCHS' not in state.env_extra:
                    if 'CIBW_ARCHS_WINDOWS' not in state.env_extra:
                        state.env_extra['CIBW_ARCHS_WINDOWS'] = 'auto64'

                    if 'CIBW_ARCHS_MACOS' not in state.env_extra:
                        state.env_extra['CIBW_ARCHS_MACOS'] = 'auto64'

                    if 'CIBW_ARCHS_LINUX' not in state.env_extra:
                        state.env_extra['CIBW_ARCHS_LINUX'] = 'auto64'

                # Tell cibuildwheel not to use `auditwheel` on Linux and MacOS,
                # because it cannot cope with us deliberately having required
                # libraries in different wheel - specifically in the PyMuPDF wheel.
                #
                # We cannot use a subset of auditwheel's functionality
                # with `auditwheel addtag` because it says `No tags
                # to be added` and terminates with non-zero. See:
                # https://github.com/pypa/auditwheel/issues/439.
                #
                state.env_extra['CIBW_REPAIR_WHEEL_COMMAND_LINUX'] = ''
                state.env_extra['CIBW_REPAIR_WHEEL_COMMAND_MACOS'] = ''

                # Specify python versions.
                CIBW_BUILD = state.env_extra.get('CIBW_BUILD')
                pipcl.log(f'{CIBW_BUILD=}')
                if CIBW_BUILD is None:
                    if state.graal:
                        CIBW_BUILD = 'gp*'
                        state.env_extra['CIBW_ENABLE'] = 'graalpy'
                    elif state.cibw_pyodide:
                        # Using python-3.13 fixes problems with MuPDF's setjmp/longjmp.
                        CIBW_BUILD = 'cp313*'
                    elif os.environ.get('GITHUB_ACTIONS') == 'true':
                        # Build/test all supported Python versions.
                        CIBW_BUILD = cibw_cp(*python_versions_minor)
                    else:
                        # Build/test current Python only.
                        v = platform.python_version_tuple()[:2]
                        pipcl.log(f'{v=}')
                        CIBW_BUILD = f'cp{"".join(v)}*'
                    pipcl.log(f'Defaulting to {CIBW_BUILD=}.')

                cibw_pyodide_args = ''
                if state.cibw_pyodide:
                    cibw_pyodide_args = ' --platform pyodide'
                    state.env_extra['HAVE_LIBCRYPTO'] = 'no'
                    state.env_extra['PYMUPDF_SETUP_MUPDF_TESSERACT'] = '0'
                if state.cibw_pyodide_version:
                    # 2025-07-21: there is no --pyodide-version option so we set
                    # CIBW_PYODIDE_VERSION.
                    state.env_extra['CIBW_PYODIDE_VERSION'] = cibw_pyodide_version
                    state.env_extra['CIBW_ENABLE'] = 'pyodide-prerelease'

                packages = list()
                for package in state.packages_build:
                    pipcl.log(f'{package=}')
                    location, args_pos = state.packages[package]
                    if not location:
                        continue
                    info = name_info(package)
                    if location.startswith('pip:'):
                        # cibuildwheel will download from pypi as required.
                        continue
                    elif location.startswith('git:'):
                        directory = pipcl.git_get(
                                local=f'git-aptest-{info.name_full}',
                                remote=info.git_remote,
                                branch=info.git_branch,
                                text=location,
                                env_extra=state.env_extra,
                                submodules=info.submodules,
                                )
                        # Update information to contain local directory. This
                        # allows 'test' command to work without repeating the
                        # call of pip.git_get().
                        state.packages[package] = directory, args_pos
                    else:
                        directory = location
                    directory_abs = os.path.abspath(directory)
                    if package == 'mupdf':
                        if platform.system() == 'Linux':
                            # Need /host/ prefix so accessible from within manylinux docker.
                            state.env_extra['PYMUPDF_SETUP_MUPDF_BUILD'] = f'/host/{directory_abs}'
                        else:
                            state.env_extra['PYMUPDF_SETUP_MUPDF_BUILD'] = directory_abs
                        # fixme: be able to set to '' for system install?
                        continue
                    
                    if state.sdists and platform.system() == 'Linux':
                        build_sdist(package, directory)

                    # Tell cibuildwheel how to test <package>.
                    if package in state.packages_test:
                        state.env_extra['CIBW_TEST_COMMAND'] = f'python {{project}}/scripts/test.py test'
                    else:
                        pipcl.log(f'Not testing because not in state.packages_test: {package=}')
                    # fixme: prefer to just run pytest directly. Needs
                    # test/conftest.py to alway `pip install` packages required for
                    # testing.
                    #state.env_extra['CIBW_TEST_COMMAND'] = f'pytest {{project}}/tests'

                    #if cibw_sdist and platform.system() == 'Linux':
                    #    pipcl.log(f'Building sdist.')
                    #    run(f'cd {pymupdf_dir_abs} && {sys.executable} setup.py -d wheelhouse sdist', env_extra=env_extra)
                    #    sdists = glob.glob(f'{pymupdf_dir_abs}/wheelhouse/pymupdf-*.tar.gz')
                    #    pipcl.log(f'{sdists=}')
                    #    assert sdists

                    # Use a copy of state.env_extra because we modify it if
                    # using manylinux docker.
                    #
                    env_extra = state.env_extra.copy()
                    
                    if platform.system() == 'Linux':
                        prefix = '/host'
                        # Update GIT_SSH_COMMAND if set, to be within /host
                        # in manylinux docker. Otherwise for example tests
                        # that access remote git repositories will not use the
                        # appropriate key.
                        GIT_SSH_COMMAND_0 = env_extra.get('GIT_SSH_COMMAND')
                        if GIT_SSH_COMMAND_0:
                            GIT_SSH_COMMAND = f'ssh -i {prefix}{state.ssh_key_path_abs} -o StrictHostKeyChecking=no'
                            pipcl.log(f'Changing GIT_SSH_COMMAND from {GIT_SSH_COMMAND_0!r} to {GIT_SSH_COMMAND!r}.')
                            env_extra['GIT_SSH_COMMAND'] = GIT_SSH_COMMAND
                    else:
                        prefix = ''
                    
                    # Ensure that when cibuildwheel runs pip to install
                    # prerequisite packages, it also looks in cibw_pypi. PIP_EXTRA_INDEX_URL
                    # is equivalent to pip's `--extra-index-url`.
                    env_extra['PIP_EXTRA_INDEX_URL'] = f'file://{prefix}{cibw_pypi}/simple'.replace('\\', '/')
                    
                    env_extra['CIBW_BUILD'] = CIBW_BUILD
                    
                    # Pass all the environment variables we have set in
                    # state.env_extra, to Linux docker. Note that this will
                    # miss any settings in the original environment.
                    CIBW_ENVIRONMENT_PASS_LINUX = env_extra.keys()
                    CIBW_ENVIRONMENT_PASS_LINUX = list(CIBW_ENVIRONMENT_PASS_LINUX)
                    CIBW_ENVIRONMENT_PASS_LINUX.sort()
                    CIBW_ENVIRONMENT_PASS_LINUX = ' '.join(CIBW_ENVIRONMENT_PASS_LINUX)
                    env_extra['CIBW_ENVIRONMENT_PASS_LINUX'] = CIBW_ENVIRONMENT_PASS_LINUX

                    #if cibw_test_project:
                    #    cibw_do_test_project(
                    #            env_extra,
                    #            CIBW_BUILD,
                    #            cibw_pyodide,
                    #            cibw_pyodide_args,
                    #            cibw_test_project_setjmp,
                    #            )
                    #    return

                    pipcl.run(
                            f'cd {directory} && cibuildwheel{cibw_pyodide_args} --output-dir {g_root_abs}/wheelhouse',
                            env_extra=env_extra,
                            prefix=f'cibw {package}: ',
                            )

                    pipcl.run(f'ls -ld {g_root_abs}/wheelhouse/*')
                    pipcl.run(f'piprepo sync {g_root_abs}/wheelhouse {cibw_pypi}')
                    packages.append(package)
                    
                    pipcl.log(f'Contents of: {cibw_pypi=} are:')
                    for dirpath, dirnames, filenames in os.walk(cibw_pypi):
                        for filename in filenames:
                            path = os.path.join(dirpath, filename)
                            st = os.stat(path)
                            pipcl.log(f'{st=}: {path=}')
                        for dirname in dirnames:
                            path_dir = os.path.join(dirpath, dirname)
                            st = os.stat(path_dir)
                            pipcl.log(f'{st=}: {path_dir=}')

            elif command == 'test':
                if state.pytest_wrap in ('valgrind', 'helgrind'):
                    if state.system_packages:
                        pipcl.log('Installing valgrind.')
                        pipcl.run(f'sudo apt update')
                        pipcl.run(f'sudo apt install --upgrade valgrind')
                    pipcl.run(f'valgrind --version')

                pipcl.run(f'pip install --upgrade pytest')
                pipcl.log(f'packages_test:')
                for i in state.packages_test:
                    pipcl.log(f'    {i!r}')
                for package in state.packages_test:
                    location, _ = state.packages[package]
                    if not location:
                        continue
                    info = name_info(package)
                    if info.name_full == 'mupdf':
                        pass
                    elif location.startswith('pip:'):
                        pass
                    else:
                        if location.startswith('git:'):
                            directory = pipcl.git_get(
                                    local='git-{info.name_full}',
                                    remote=info.git_remote,
                                    branch=info.git_branch,
                                    text=location,
                                    )
                        else:
                            directory = location
                        command = f'pytest {directory}/tests {state.pytest_options}'
                        if state.pytest_wrap:
                            if state.pytest_wrap == 'gdb':
                                command = f'gdb --args {command}'
                            elif state.pytest_wrap == 'valgrind':
                                state.env_extra['PYMUPDF_RUNNING_ON_VALGRIND'] = '1'
                                state.env_extra['PYTHONMALLOC'] = 'malloc'
                                command = (
                                        f' valgrind'
                                        f' --suppressions={pymupdf_dir_abs}/valgrind.supp'
                                        f' --trace-children=no'
                                        f' --num-callers=20'
                                        f' --error-exitcode=100'
                                        f' --errors-for-leak-kinds=none'
                                        f' --fullpath-after='
                                        f' {command}'
                                        )
                            elif state.pytest_wrap == 'helgrind':
                                state.env_extra['PYMUPDF_RUNNING_ON_VALGRIND'] = '1'
                                state.env_extra['PYTHONMALLOC'] = 'malloc'
                                command = (
                                        f' valgrind'
                                        f' --tool=helgrind'
                                        f' --trace-children=no'
                                        f' --num-callers=20'
                                        f' --error-exitcode=100'
                                        f' --fullpath-after='
                                        f' {command}'
                                        )
                            else:
                                assert 0, f'Unrecognised {state.pytest_wrap=}.'
                        pipcl.run(
                                command,
                                env_extra=state.env_extra,
                                prefix=f'pytest {package}: ',
                                )

                if 0: test(
                        env_extra=env_extra,
                        implementations=implementations,
                        test_names=test_names,
                        pytest_options=pytest_options,
                        test_timeout=test_timeout,
                        pytest_prefix=pytest_prefix,
                        test_fitz=test_fitz,
                        pybind=pybind,
                        system_packages=system_packages,
                        venv=venv,
                        )

            elif command == 'pyodide':
                build_pyodide_wheel(pyodide_build_version=pyodide_build_version)

            else:
                assert 0, f'{command=}'
    finally:
        for path in paths_to_delete:
            fs_remove(path)


def get_env_bool(name, default=0):
    v = os.environ.get(name)
    if v in ('1', 'true'):
        return 1
    elif v in ('0', 'false'):
        return 0
    elif v is None:
        return default
    else:
        assert 0, f'Bad environ {name=} {v=}'

def show_help():
    print(__doc__)
    print(venv_info())


def cibw_do_test_project(
        env_extra,
        CIBW_BUILD,
        cibw_pyodide,
        cibw_pyodide_args,
        cibw_test_project_setjmp,
        ):
    testdir = f'{pymupdf_dir_abs}/cibw_test'
    shutil.rmtree(testdir, ignore_errors=1)
    os.mkdir(testdir)
    with open(f'{testdir}/setup.py', 'w') as f:
        f.write(textwrap.dedent(f'''
                import shutil
                import sys
                import os
                import pipcl

                def build():
                    so_leaf = pipcl.build_extension(
                            name = 'foo',
                            path_i = 'foo.i',
                            outdir = 'build',
                            source_extra = 'qwerty.cpp',
                            py_limited_api = True,
                            )
                    
                    return [
                            ('build/foo.py', 'foo/__init__.py'),
                            (f'build/{{so_leaf}}', f'foo/'),
                            ]

                p = pipcl.Package(
                        name = 'pymupdf-test',
                        version = '1.2.3',
                        fn_build = build,
                        py_limited_api=True,
                        )

                def get_requires_for_build_wheel(config_settings=None):
                    return ['swig']
                
                build_wheel = p.build_wheel
                build_sdist = p.build_sdist
                
                # Handle old-style setup.py command-line usage:
                if __name__ == '__main__':
                    p.handle_argv(sys.argv)
                '''))
    with open(f'{testdir}/foo.i', 'w') as f:
        if cibw_test_project_setjmp:
            f.write(textwrap.dedent('''
                    %{
                    #include <stdexcept>

                    #include <assert.h>
                    #include <setjmp.h>
                    #include <stdio.h>
                    #include <string.h>

                    int qwerty(void);

                    static sigjmp_buf jmpbuf;
                    static int bar0(const char* text)
                    {
                        printf("bar0(): text: %s\\n", text);

                        int q = qwerty();
                        printf("bar0(): q=%i\\n", q);

                        int len = (int) strlen(text);
                        printf("bar0(): len=%i\\n", len);
                        printf("bar0(): calling longjmp().\\n");
                        fflush(stdout);
                        longjmp(jmpbuf, 1);
                        assert(0);
                    }
                    int bar1(const char* text)
                    {
                        int ret = 0;
                        if (setjmp(jmpbuf) == 0)
                        {
                            ret = bar0(text);
                        }
                        else
                        {
                            printf("bar1(): setjmp() returned non-zero.\\n");
                            throw std::runtime_error("deliberate exception");
                        }
                        assert(0);
                    }
                    int bar(const char* text)
                    {
                        int ret = 0;
                        try
                        {
                            ret = bar1(text);
                        }
                        catch(std::exception& e)
                        {
                            printf("bar1(): received exception: %s\\n", e.what());
                        }
                        return ret;
                    }
                    %}
                    int bar(const char* text);
                    '''))
        else:
            f.write(textwrap.dedent('''
                    %{
                    #include <stdexcept>

                    #include <assert.h>
                    #include <stdio.h>
                    #include <string.h>

                    int qwerty(void);

                    int bar(const char* text)
                    {
                        qwerty();
                        return strlen(text);
                    }
                    %}
                    int bar(const char* text);
                    '''))
    
    with open(f'{testdir}/qwerty.cpp', 'w') as f:
        f.write(textwrap.dedent('''
                #include <stdio.h>
                int qwerty(void)
                {
                    printf("qwerty()\\n");
                    return 3;
                }
                '''))

    with open(f'{testdir}/pyproject.toml', 'w') as f:
        f.write(textwrap.dedent('''
                [build-system]
                # We define required packages in setup.py:get_requires_for_build_wheel().
                requires = []

                # See pep-517.
                #
                build-backend = "setup"
                backend-path = ["."]
                '''))
        
    shutil.copy2(f'{pymupdf_dir_abs}/pipcl.py', f'{testdir}/pipcl.py')
    shutil.copy2(f'{pymupdf_dir_abs}/wdev.py', f'{testdir}/wdev.py')

    env_extra['CIBW_BUILD'] = CIBW_BUILD
    CIBW_TEST_COMMAND = ''
    if cibw_pyodide:
        CIBW_TEST_COMMAND += 'pyodide xbuildenv search --all; '
    CIBW_TEST_COMMAND += 'python -c "import foo; foo.bar(\\"some text\\")"'
    env_extra['CIBW_TEST_COMMAND'] = CIBW_TEST_COMMAND
    #env_extra['CIBW_TEST_COMMAND'] = ''
    
    pipcl.run(f'cd {testdir} && cibuildwheel --output-dir ../wheelhouse{cibw_pyodide_args}',
            env_extra=env_extra,
            prefix='cibw: ',
            )
    pipcl.run(f'ls -ldt {pymupdf_dir_abs}/wheelhouse/*')
        

def build_pyodide_wheel(pyodide_build_version=None):
    '''
    Build Pyodide wheel.

    This runs `pyodide build` inside the PyMuPDF directory, which in turn runs
    setup.py in a Pyodide build environment.
    '''
    pipcl.log(f'## Building Pyodide wheel.')

    # Our setup.py does not know anything about Pyodide; we set a few
    # required environmental variables here.
    #
    env_extra = dict()

    # Disable libcrypto because not available in Pyodide.
    env_extra['HAVE_LIBCRYPTO'] = 'no'

    # Tell MuPDF to build for Pyodide.
    env_extra['OS'] = 'pyodide'

    # Build a single wheel without a separate PyMuPDFb wheel.
    env_extra['PYMUPDF_SETUP_FLAVOUR'] = 'pb'
    
    # 2023-08-30: We set PYMUPDF_SETUP_MUPDF_BUILD_TESSERACT=0 because
    # otherwise mupdf thirdparty/tesseract/src/ccstruct/dppoint.cpp fails to
    # build because `#include "errcode.h"` finds a header inside emsdk. This is
    # pyodide bug https://github.com/pyodide/pyodide/issues/3839. It's fixed in
    # https://github.com/pyodide/pyodide/pull/3866 but the fix has not reached
    # pypi.org's pyodide-build package. E.g. currently in tag 0.23.4, but
    # current devuan pyodide-build is pyodide_build-0.23.4.
    #
    env_extra['PYMUPDF_SETUP_MUPDF_TESSERACT'] = '0'
    setup = pyodide_setup(pymupdf_dir, pyodide_build_version=pyodide_build_version)
    command = f'{setup} && echo "### Running pyodide build" && pyodide build --exports whole_archive'
    
    command = command.replace(' && ', '\n && ')
    
    pipcl.run(command, env_extra=env_extra)
    
    # Copy wheel into `wheelhouse/` so it is picked up as a workflow
    # artifact.
    #
    pipcl.run(f'ls -l {pymupdf_dir}/dist/')
    pipcl.run(f'mkdir -p {pymupdf_dir}/wheelhouse && cp -p {pymupdf_dir}/dist/* {pymupdf_dir}/wheelhouse/')
    pipcl.run(f'ls -l {pymupdf_dir}/wheelhouse/')    


def pyodide_setup(
        directory,
        clean=False,
        pyodide_build_version=None,
        ):
    '''
    Returns a command that will set things up for a pyodide build.
    
    Args:
        directory:
            Our command cd's into this directory.
        clean:
            If true we create an entirely new environment. Otherwise
            we reuse any existing emsdk repository and venv.
        pyodide_build_version:
            Version of Python package pyodide-build; if None we use latest
            available version.
            2025-02-13: pyodide_build_version='0.29.3' works.
    
    The returned command does the following:
    
    * Checkout latest emsdk from https://github.com/emscripten-core/emsdk.git:
      * Clone emsdk repository to `emsdk` if not already present.
      * Run `git pull -r` inside emsdk checkout.
    * Create venv `venv_pyodide_<python_version>` if not already present.
    * Activate venv `venv_pyodide_<python_version>`.
    * Install/upgrade package `pyodide-build`.
    * Run emsdk install scripts and enter emsdk environment.
    
    Example usage in a build function:
    
        command = pyodide_setup()
        command += ' && pyodide build --exports pyinit'
        subprocess.run(command, shell=1, check=1)
    '''
    
    pv = platform.python_version_tuple()[:2]
    assert pv == ('3', '12'), f'Pyodide builds need to be run with Python-3.12 but current Python is {platform.python_version()}.'
    command = f'cd {directory}'
    
    # Clone/update emsdk. We always use the latest emsdk with `git pull`.
    #
    # 2025-02-13: this works: 2514ec738de72cebbba7f4fdba0cf2fabcb779a5
    #
    dir_emsdk = 'emsdk'
    if clean:
        shutil.rmtree(dir_emsdk, ignore_errors=1)
        # 2024-06-25: old `.pyodide-xbuildenv` directory was breaking build, so
        # important to remove it here.
        shutil.rmtree('.pyodide-xbuildenv', ignore_errors=1)
    if not os.path.exists(f'{directory}/{dir_emsdk}'):
        command += f' && echo "### Cloning emsdk.git"'
        command += f' && git clone https://github.com/emscripten-core/emsdk.git {dir_emsdk}'
    command += f' && echo "### Updating checkout {dir_emsdk}"'
    command += f' && (cd {dir_emsdk} && git pull -r)'
    command += f' && echo "### Checkout {dir_emsdk} is:"'
    command += f' && (cd {dir_emsdk} && git show -s --oneline)'
    
    # Create and enter Python venv.
    #
    python = sys.executable
    venv_pyodide = f'venv_pyodide_{sys.version_info[0]}.{sys.version_info[1]}'
    
    if not os.path.exists( f'{directory}/{venv_pyodide}'):
        command += f' && echo "### Creating venv {venv_pyodide}"'
        command += f' && {python} -m venv {venv_pyodide}'
    command += f' && . {venv_pyodide}/bin/activate'
    command += f' && echo "### Installing Python packages."'
    command += f' && python -m pip install --upgrade pip wheel pyodide-build'
    if pyodide_build_version:
        command += f'=={pyodide_build_version}'
    
    # Run emsdk install scripts and enter emsdk environment.
    #
    command += f' && cd {dir_emsdk}'
    command += ' && PYODIDE_EMSCRIPTEN_VERSION=$(pyodide config get emscripten_version)'
    command += ' && echo "### PYODIDE_EMSCRIPTEN_VERSION is: $PYODIDE_EMSCRIPTEN_VERSION"'
    command += ' && echo "### Running ./emsdk install"'
    command += ' && ./emsdk install ${PYODIDE_EMSCRIPTEN_VERSION}'
    command += ' && echo "### Running ./emsdk activate"'
    command += ' && ./emsdk activate ${PYODIDE_EMSCRIPTEN_VERSION}'
    command += ' && echo "### Running ./emsdk_env.sh"'
    command += ' && . ./emsdk_env.sh'   # Need leading `./` otherwise weird 'Not found' error.
    
    command += ' && cd ..'
    return command


def test(
        *,
        env_extra,
        implementations,
        venv=False,
        test_names=None,
        pytest_options=None,
        test_timeout=None,
        pytest_prefix=None,
        test_fitz=True,
        pytest_k=None,
        pybind=False,
        system_packages=False,
        ):
    if pybind:
        cpp_path = 'pymupdf_test_pybind.cpp'
        cpp_exe = 'pymupdf_test_pybind.exe'
        cpp = textwrap.dedent('''
                #include <pybind11/embed.h>
                
                int main()
                {
                    pybind11::scoped_interpreter guard{};
                    pybind11::exec(R"(
                            print('Hello world', flush=1)
                            import pymupdf
                            pymupdf.JM_mupdf_show_warnings = 1
                            print(f'{pymupdf.version=}', flush=1)
                            doc = pymupdf.Document()
                            pymupdf.mupdf.fz_warn('Dummy warning.')
                            pymupdf.mupdf.fz_warn('Dummy warning.')
                            pymupdf.mupdf.fz_warn('Dummy warning.')
                            print(f'{doc=}', flush=1)
                            )");
                }
                ''')
        def fs_read(path):
            try:
                with open(path) as f:
                    return f.read()
            except Exception:
                return
        def fs_remove(path):
            try:
                os.remove(path)
            except Exception:
                pass
        cpp_existing = fs_read(cpp_path)
        if cpp == cpp_existing:
            pipcl.log(f'Not creating {cpp_exe} because unchanged: {cpp_path}')
        else:
            with open(cpp_path, 'w') as f:
                f.write(cpp)
        def getmtime(path):
            try:
                return os.path.getmtime(path)
            except Exception:
                return 0
        python_config = f'{os.path.realpath(sys.executable)}-config'
        # `--embed` adds `-lpython3.11` to the link command, which appears to
        # be necessary when building an executable.
        flags = pipcl.run(f'{python_config} --cflags --ldflags --embed', capture=1)
        build_command = f'c++ {cpp_path} -o {cpp_exe} -g -W -Wall {flags}'
        build_path = f'{cpp_exe}.cmd'
        build_command_prev = fs_read(build_path)
        if build_command != build_command_prev or getmtime(cpp_path) >= getmtime(cpp_exe):
            fs_remove(build_path)
            pipcl.run(build_command)
            with open(build_path, 'w') as f:
                f.write(build_command)
        pipcl.run(f'./{cpp_exe}')
        return
    
    pymupdf_dir_rel = gh_release.relpath(pymupdf_dir)
    if not pytest_options and pytest_prefix == 'valgrind':
        pytest_options = '-sv'
    if pytest_k:
        pytest_options += f' -k {shlex.quote(pytest_k)}'
    pytest_arg = ''
    if test_names:
        for test_name in test_names:
            pytest_arg += f' {pymupdf_dir_rel}/{test_name}'
    else:
        pytest_arg += f' {pymupdf_dir_rel}/tests'
    python = gh_release.relpath(sys.executable)
    pipcl.log('Running tests with tests/run_compound.py and pytest.')
    
    PYODIDE_ROOT = os.environ.get('PYODIDE_ROOT')
    if PYODIDE_ROOT is not None:
        # We can't install packages with `pip install`; setup.py will have
        # specified pytest in the wheels's <requires_dist>, so it will be
        # already installed.
        #
        pipcl.log(f'Not installing test packages because {PYODIDE_ROOT=}.')
        command = f'{pytest_options} {pytest_arg}'
        args = shlex.split(command)
        pipcl.log(f'{PYODIDE_ROOT=} so calling pytest.main(args).')
        pipcl.log(f'{command=}')
        pipcl.log(f'args are ({len(args)}):')
        for arg in args:
            pipcl.log(f'    {arg!r}')
        import pytest
        e = pytest.main(args)
        assert e == 0, f'pytest.main() failed: {e=}'
        return
    
    if venv >= 2:
        pipcl.run(f'pip install --upgrade {gh_release.test_packages}')
    else:
        pipcl.log(f'{venv=}: Not installing test packages: {gh_release.test_packages}')
    run_compound_args = ''
    
    if implementations:
        run_compound_args += f' -i {implementations}'
    
    if test_timeout:
        run_compound_args += f' -t {test_timeout}'

    if pytest_prefix in ('valgrind', 'helgrind'):
        if system_packages:
            pipcl.log('Installing valgrind.')
            pipcl.run(f'sudo apt update')
            pipcl.run(f'sudo apt install --upgrade valgrind')
        pipcl.run(f'valgrind --version')

    command = f'{python} {pymupdf_dir_rel}/tests/run_compound.py{run_compound_args}'
    
    if pytest_prefix is None:
        pass
    elif pytest_prefix == 'gdb':
        command += ' gdb --args'
    elif pytest_prefix == 'valgrind':
        env_extra['PYMUPDF_RUNNING_ON_VALGRIND'] = '1'
        env_extra['PYTHONMALLOC'] = 'malloc'
        command += (
                    f' valgrind'
                    f' --suppressions={pymupdf_dir_abs}/valgrind.supp'
                    f' --trace-children=no'
                    f' --num-callers=20'
                    f' --error-exitcode=100'
                    f' --errors-for-leak-kinds=none'
                    f' --fullpath-after='
                    )
    elif pytest_prefix == 'helgrind':
        env_extra['PYMUPDF_RUNNING_ON_VALGRIND'] = '1'
        env_extra['PYTHONMALLOC'] = 'malloc'
        command = (
                f' valgrind'
                f' --tool=helgrind'
                f' --trace-children=no'
                f' --num-callers=20'
                f' --error-exitcode=100'
                f' --fullpath-after='
                )
    else:
        assert 0, f'Unrecognised {pytest_prefix=}'

    if platform.system() == 'Windows':
        # `python -m pytest` doesn't seem to work.
        command += ' pytest'
    else:
        # On OpenBSD `pip install pytest` doesn't seem to install the pytest
        # command, so we use `python -m pytest ...`.
        command += f' {python} -m pytest'

    command += f' {pytest_options} {pytest_arg}'

    # Always start by removing any test_*_fitz.py files.
    for p in glob.glob(f'{pymupdf_dir_rel}/tests/test_*_fitz.py'):
        pipcl.log(f'Removing {p=}')
        os.remove(p)
    if test_fitz:
        # Create copies of each test file, modified to use `pymupdf`
        # instead of `fitz`.
        for p in glob.glob(f'{pymupdf_dir_rel}/tests/test_*.py'):
            if os.path.basename(p).startswith('test_fitz_'):
                # Don't recursively generate test_fitz_fitz_foo.py,
                # test_fitz_fitz_fitz_foo.py, ... etc.
                continue
            branch, leaf = os.path.split(p)
            p2 = f'{branch}/{leaf[:5]}fitz_{leaf[5:]}'
            pipcl.log(f'Converting {p=} to {p2=}.')
            with open(p, encoding='utf8') as f:
                text = f.read()
            text2 = re.sub("([^\'])\\bpymupdf\\b", '\\1fitz', text)
            if p.replace(os.sep, '/') == f'{pymupdf_dir_rel}/tests/test_docs_samples.py'.replace(os.sep, '/'):
                assert text2 == text
            else:
                assert text2 != text, f'Unexpectedly unchanged when creating {p!r} => {p2!r}'
            with open(p2, 'w', encoding='utf8') as f:
                f.write(text2)
    try:
        pipcl.log(f'Running tests with tests/run_compound.py and pytest.')
        pipcl.run(command, env_extra=env_extra, timeout=test_timeout)
        
    except subprocess.TimeoutExpired as e:
         pipcl.log(f'Timeout when running tests.')
         raise
    finally:
        pipcl.log(f'\n'
                f'[As of 2024-10-10 we get warnings from pytest/Python such as:\n'
                f'    DeprecationWarning: builtin type SwigPyPacked has no __module__ attribute\n'
                f'This seems to be due to Swig\'s handling of Py_LIMITED_API.\n'
                f'For details see https://github.com/swig/swig/issues/2881.\n'
                f']'
                )
        pipcl.log('\n' + venv_info(pytest_args=f'{pytest_options} {pytest_arg}'))


def github_workflow_unimportant():
    '''
    Returns true if we are running a Github scheduled workflow but in a
    repository not called 'main'. This can be used to avoid consuming
    unnecessary Github minutes running workflows on non-main branches.
    '''
    GITHUB_EVENT_NAME = os.environ.get('GITHUB_EVENT_NAME')
    GITHUB_REPOSITORY = os.environ.get('GITHUB_REPOSITORY')
    if GITHUB_EVENT_NAME == 'schedule':
        sha, comment, diff, branch = pipcl.git_info(g_root)
        if branch != 'main':
            log(f'## This is an unimportant Github workflow on non-main branch.')
            log(f'## {GITHUB_EVENT_NAME=}.')
            log(f'## {GITHUB_REPOSITORY=}.')
            log(f'## {branch=}.')
            return True


def venv_in(path=None):
    '''
    If path is None, returns true if we are in a venv. Otherwise returns true
    only if we are in venv <path>.
    '''
    if path:
        return os.path.abspath(sys.prefix) == os.path.abspath(path)
    else:
        return sys.prefix != sys.base_prefix


def venv_run(args, path, recreate=True, clean=False):
    '''
    Runs command inside venv and returns termination code.
    
    Args:
        args:
            List of args.
        path:
            Name of venv.
        recreate:
            If false we do not run `<sys.executable> -m venv <path>` if <path>
            already exists. This avoids a delay in the common case where <path>
            is already set up, but fails if <path> exists but does not contain
            a valid venv.
        clean:
            If true we first delete <path>.
    '''
    if clean:
        pipcl.log(f'Removing any existing venv {path}.')
        assert path.startswith('venv-')
        shutil.rmtree(path, ignore_errors=1)
    if recreate or not os.path.isdir(path):
        pipcl.run(f'{sys.executable} -m venv {path}')
    if platform.system() == 'Windows':
        command = f'{path}\\Scripts\\activate && python'
        # shlex not reliable on Windows.
        # Use crude quoting with "...". Seems to work.
        for arg in args:
            assert '"' not in arg
            command += f' "{arg}"'
    else:
        command = f'. {path}/bin/activate && python {shlex.join(args)}'
    e = pipcl.run(command, check=0)
    return e


def fs_remove(path):
    '''
    Removes file or directory, without raising exception if it doesn't exist.

    path:
        The path to remove.

    We assert-fail if the path still exists when we return, in case of
    permission problems etc.
    '''
    try:
        os.remove( path)
    except Exception:
        pass
    shutil.rmtree( path, ignore_errors=1)
    assert not os.path.exists( path)


def fs_write_key(path, data):
    '''
    Writes <data> to <path>, ensuring that <path> is created with appropriate
    permissions.
    '''
    fs_remove(path)
    if platform.system() == 'Windows':
        # For unknown reasons, the code below for non-Windows does not work
        # on Windows.
        #
        # Also for unknown reasons, using backslashes in
        # path doesn't work - we write the file but it
        # doesn't appear in the filesystem.
        path = path.replace('\\', '/')
        with open(path, 'wb') as f:
            f.write(data.encode('utf8').replace(b'\r', b''))
    else:
        # Need to create file as read/write for current user only, so we have
        # to use `os.open()` instead of `open()`.
        #
        fd = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_EXCL, 0o600)
        try:
            os.write(fd, data.encode('utf8'))
        finally:
            os.close(fd)


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv))
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        # Terminate relatively quietly, failed commands will usually have
        # generated diagnostics.
        pipcl.log(f'{e}')
        sys.exit(1)
    # Other exceptions should not happen, and will generate a full Python
    # backtrace etc here.
