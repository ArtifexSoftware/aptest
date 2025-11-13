#! /usr/bin/env python3

'''Developer build/test script for Artifex packages.

Examples:

    ./aptest/aptest.py -p PyMuPDF -P PyMuPDFPro -m mupdf -l sce build test
    
        Build, install and test pymupdf, pymupdfpro and pymupdf_layout using
        local checkouts.
    
    ./aptest/aptest.py -p git: -P git: -l git: build test
    
        Build, install and test pymupdf, pymupdfpro and pymupdf_layout using
        central git repositories.
    
        * Clones/updates local git repositories for each of pymupdf, pymupdfpro
          and pymupdf_layout.
        * Build/install/test each package.
    
    ./aptest/aptest.py --release-1
    ./aptest/aptest.py --release-2
    ./aptest/aptest.py --release-3
        Make release, building/testing on Github, downloading to local machine,
        and uploading to pypi.org.
        
    ./aptest/aptest.py -r @github -p pip: -P PyMuPDFPlus -l git: cibw
        Build/test pymupdf, pymupdfpro and pymupdf-layout using cibuildwheel,
        getting packages from different locations.
        
        * Installs pymupdf from pypi.org. (We will not run pymupdf tests
          because no checkout.)
        * For pymupdfpro we use local checkout.
        * Gets pymupdf_layout from central git.
        
        (Builds may fail if any of the packages have incompatible version
        numbers.)
    
    ./aptest/aptest.py -r macmini -p pip: -p git: build test
        Test current pymupdf release with latest test suite in central git.

    ./aptest/aptest.py -r macmini -p pip: -p PyMuPDF build test
        Test current pymupdf release with test suite in local checkout.

    ./aptest/aptest.py -r @github --remote-github-yml test_multiple.yml -P PyMuPDFPlus --remote-github-yml-inputs 'args=-o windows'
        Runs specific Github workflow PyMuPDFPlus/.github/workflows/test_multiple.yml.

Args:

    * Command line arguments are called parameters if they start with `-`,
      otherwise they are called commands.
    * Parameters are evaluated first in the order that they were specified.
    * Then commands are run in the order in which they were specified.
    * Usually command `test` would be specified after commands such as `build`.
    * Parameters and commands can be interleaved but it may be clearer to separate
      them on the command line.

    Parameters:
    
        -a <env_name>
            Read next space-separated argument(s) from environmental variable
            <env_name>.
            * Does nothing if <env_name> is unset.
            * Useful when running via Github action.
    
        -b <packages>
            Modifies behaviour of 'build' command to build/install only
            the specified comma-separated packages instead of all packages
            specified by `-i`.
        
        --build-type debug|memento|release
            Set build type. Default is relese.
        
        --cibw-name <cibw_name>
            Name to use when installing cibuildwheel, e.g.:
                --cibw-name cibuildwheel==3.0.0b1
                --cibw-name git+https://github.com/pypa/cibuildwheel
            Default is `cibuildwheel`, i.e. the current release.

        --cibw-pyodide 0|1
             Make `cibw` command build a pyodide wheel, runs `cibuildwheel
             --platform pyodide` etc.

        --cibw-pyodide-version <cibw_pyodide_version>
            Override default Pyodide version to use with `cibuildwheel` command
            by setting CIBW_PYODIDE_VERSION.

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
                One of: mupdf pymupdf pymupdfpro layout
            location:
                `pip:`
                    Install from pypi.org using pip.
                `pip:==<version>`
                    Install specified version from pypi.org.
                    Doesn't really work because if another project needs a
                    newer version, pip will install again from pypi.prg.
                `'git:[-b <branch>] [-t <tag>] [<remote>]'`
                    Clone/update from git remote into local checkout
                    `aptest-git-<package-name>`, optionally overriding default
                    branch/tag/remote.
                <local-dir>
                    Local directory, typically a git checkout.
            
            If a package is specified twice, the first location will be used
            for building, and the second location used for testing. This allows
            packages on pypi.org to be tested, for example:
            
                aptest.py -i pymupdf pip: -i pymupdf PyMuPDF build test
                    Test current pymupdf release with testsuite in PyMuPDF/tests.

                aptest.py -i pymupdf pip: -i pymupdf git: build test
                    Test current pymupdf release with testsuite in current git.

        --pymupdf_layout <location>
        --layout <location>
        -l <location>
            Aliases for `-i pymupdf_layout <location>
        
        --mupdf <location>
        -m <location>
            Aliases for `-i mupdf <location>
        
        -o <os_names>
            Control which OS's we run on. If current OS is not in
            (comma-separated) list, we do nothing. <os_names> is case
            insensitive. Should match linux, windows or darwin.
        
        --pymupdf <location>
        -p <location>
            Aliases for `-i pymupdf <location>
        
        --pymupdfpro <location>
        --pro <location>
        -P <location>
            Aliases for `-i pymupdfpro <location>
        
        --pytest <pytest-flags>
            Specify pytest flags, for example `--pytest '-k test_123'`.
        
        --pytest-path <pytest_path>
            Specify a directory/file/function to test, relative to project root
            directory. Can be specified multiple times. Default is the project
            root directory itself.

        --pytest-wrap gdb|valgrind|helgrind
            Run tests under specified tool
        
        --python <python>
            Set Python to use. If set we re-run ourselves using specified
            python command.
        
        -r <remote>
        
            Rerun ourselves on remote machine(s) and on success copy wheels
            back to local machines.
        
            If remote='github', run on Github:
            
                * We push specified local checkouts directories (specified
                  by -i, -m, -p etc) to branches called `aptest-$USER`in the
                  equivalent repositories in github.com/ArtifexSoftware/.
                
                * Warning: if local checkouts have uncommited changes, they are
                  pushed as temporary commits; unfortuntaely this will forget
                  about newly added files.

                * We rerun the aptest.py command on Github machines, changing
                  -i, -m etc args to use git: to refer to the above
                  repositories.

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
                  aptest-wheelhouse/.
        
        --release-1
        --release-2
        --release-3
            Preset args for making releases. Only one may be specified, and it
            must be the only arg.
            
            aptest/aptest.py --release-1
                Build wheels for everything except linux-aarch64 and win32.
            aptest/aptest.py --release-2
                Build wheels for linux-aarch64.
            aptest/aptest.py --release-3
                Build wheels for win32 (pymupdf only).
        
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
            
            We allow single-letter aliases for package names.
            
            For example:
                -t -,P
                -t -,pymudfpro
                    Tests only pymupdfpro.
                -t -m,-l
                -t -mupdf,-pymupdf_layout
                    Removes mupdf and layout from list of packages to test.

        -u 0|1
            If 1, if `-r @github` is used then on success we ask the user to
            confirm and then upload wheels to pypi.org.
            
        -v <venv>
            0 - do not use a venv.
            1 - Use venv. If it already exists, we assume the existing
                directory was created by us earlier and is a valid venv
                containing all necessary packages; this saves a little time.
            2 - Use venv.
            3 - Use venv but delete it first if it already exists.
            
            The default is 2.
        
        --remote-github-workflow <workflow_id>
            Changes behaviour of `-r @github`. Don't run anything Github,
            instead continue from previous `-r @github` invocation by waiting
            for <workflow_id> to finish and then downloadings logs and wheels
            etc. Note that you still need to include `-r @github cibw`.
        
        --remote-github-yml <yml>
            With @github, run .yml file instead of running aptest.py.
            
        --remote-github-yml-inputs <inputs>
            Specify inputs used with --github-yml. <inputs> is comma-separated
            list of name=value pairs.
        
        --remote-prefix <remote_prefix>
            Run remote using specified Python command. Ignored by `-r @github`.
        
        --remote-do 0|1
            [For debugging.]
            If 0 we don't sync to remote and we don't run any commands on
            remote. But we do sync remote wheels to local.
        
        --run <package> <command>
            Make `run` command run specified command within checkout of
            <package>.
        
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
        
        --ticker <delay>
            Use ticker with specified delay. Disabled if delay==0. Default is
            0.5.
            
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

        run
            Runs commands specified by `--run` within checkouts.
        
        test
            Runs pytest tests.
            
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

import os
import platform
import shlex
import shutil
import subprocess
import sys
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
    
    If <tmpcommit> is true, we do a temporary commit of any uncommitted changes
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
                pipcl.log(f'Temporary commit failed. {diff=}.')
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


def sync_reverse(
        remote,
        remote_dir,
        path_remote,
        path_local,
        ssh_command,
        *,
        filters=None,
        verbose=1,
        ):
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
    pipcl.run(command, prefix=f'reverse sync {path_remote} => {path_local}: ', log=1)
        

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
            with open(filenames_path, 'w') as f:    # pylint: disable=unspecified-encoding
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
            pipcl.fs_remove(filenames_path)
    return ret


class NameInfo:
    '''
    Hard-coded info about package.
    '''
    def __init__(self, name):
        self.submodules = True
        if name == 'mupdf':
            self.github_name = 'ArtifexSoftware/mupdf'
            self.git_branch = 'master'
        elif name == 'pymupdf':
            self.github_name = 'pymupdf/PyMuPDF'
            self.git_branch = 'main'
        elif name == 'pymupdfpro':
            self.github_name = 'ArtifexSoftware/PyMuPDFPro'
            self.git_branch = 'main'
        elif name == 'pymupdf_layout':
            self.github_name = 'ArtifexSoftware/sce'
            self.git_branch = 'master'
            # Have seen problems with clong after we've pushed local checkout to
            # branch but submodule `mupdf` not present.
            self.submodules = False
        else:
            assert 0, f'{name=}'
        self.git_remote = f'git@github.com:{self.github_name}.git'


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
    ticker = 0.5
    
    class State:
        pass
    state = State()
    state.build_type = None
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
    state.packages2 = dict()   # map from name to location.
    state.packages_build = list() # Sorted list of names.
    state.packages_test = list()  # Sorted list of names.
    state.pybind = False
    state.pytest_options = ''
    state.pytest_paths = list()
    state.pytest_wrap = None
    state.remote_github_yml = None
    state.remote_github_yml_inputs = None
    state.run_commands = list()
    state.sdists = False
    state.swig = None
    state.swig_quick = None
    state.system_packages = True if os.environ.get('GITHUB_ACTIONS') == 'true' else False   # pylint: disable=simplifiable-if-expression
    state.system_site_packages = False
    state.valgrind = False
    
    def add_package(name, location, args_pos):
        if name in state.packages:
            pipcl.log(f'Adding secone location for {name=} testing only: {location=}')
            state.packages2[name] = (location, args_pos)
            return
        state.packages[name] = (location, args_pos)
        state.packages_build.append(name)
        state.packages_test.append(name)

        names = [
            'mupdf',
            'pymupdf',
            'pymupdf_layout',
            'pymupdfpro',
            ]
        keyfn = lambda name: names.index(name)
        state.packages_build.sort(key=keyfn)
        state.packages_test.sort(key=keyfn)
    
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
            pos1 = args.pos - 1
            _name = next(args)
            _value = os.environ.get(_name, '')
            pos2 = args.pos
            new_args = shlex.split(_value)
            args.argv[pos1:pos2] = new_args
            args.pos = pos1
        
        elif arg == '-b':
            state.packages_build = next(args).split(',')
        
        elif arg == '--build-type':
            state.build_type = next(args)
            assert state.build_type in ('release', 'debug', 'memento')
        
        elif arg == '--cibw-name':
            state.cibw_name = next(args)
        
        elif arg == '--cibw-pyodide':
            state.cibw_pyodide = int(next(args))
        
        elif arg == '--cibw-pyodide-version':
            state.cibw_pyodide_version = next(args)
        
        elif arg == '--cibw-skip-add-defaults':
            state.cibw_skip_add_defaults = int(next(args))
        
        elif arg == '-e':
            _nv = next(args)
            assert '=' in _nv, f'-e <name>=<value> does not contain "=": {_nv!r}'
            _name, _value = _nv.split('=', 1)
            state.env_extra[_name] = _value
        
        elif arg == '--graal':
            state.graal = int(next(args))
        
        elif arg in ('-h', '--help'):
            show_help = True
        
        elif arg == '-i':
            _name = next(args)
            _location = next(args)
            add_package(_name, _location, args.pos - 1)
        
        elif arg in ('--pymupdf_layout', '--layout', '-l'):
            add_package('pymupdf_layout', next(args), args.pos - 1)
        
        elif arg in ('--mupdf', '-m'):
            add_package('mupdf', next(args), args.pos - 1)
        
        elif arg == '-o':
            state.os_names += next(args).lower().split(',')
            names = ('linux', 'windows', 'darwin')
            for os_name in state.os_names:
                assert os_name in names, f'OS names should be from {names!r} but {names=}.'
        
        elif arg in ('--pymupdf', '-p'):
            add_package('pymupdf', next(args), args.pos - 1)
        
        elif arg in ('--pymupdfpro', '--pro', '-P'):
            add_package('pymupdfpro', next(args), args.pos - 1)
        
        elif arg == '-r':
            remote_arg = args.pos
            remote = next(args)
        
        elif arg == '--run':
            package = next(args)
            command = next(args)
            state.run_commands.append((package, command))
        
        elif arg == '-t':
            _names = next(args).split(',')
            apply_deltas(state.packages_test, _names)
        
        elif arg == '--pybind':
            state.pybind = int(next(args))
        
        elif arg == '--pytest':
            state.pytest_options = next(args)
        
        elif arg == '--pytest-path':
            state.pytest_paths.append(next(args))
        
        elif arg == '--pytest-wrap':
            state.pytest_wrap = next(args)
        
        elif arg == '--python':
            python_args_pos = args.pos
            python = next(args)
        
        elif arg.startswith('--release-'):
            pos = args.pos - 1
            assert args.pos == 1 and len(args.argv) == 1, f'args `--release-*` must be only arg.'
            if arg == '--release-1':
                new_args = '-r @github -u 1 -p git: -P git: -l git: cibw --sdists 1'
            elif arg == '--release-2':
                new_args = '-r @github -u 1 -p git: -P git: -l git: cibw -o linux -e CIBW_ARCHS_LINUX=aarch64 -e "CIBW_BUILD=cp310*"'
            elif arg == '--release-3':
                new_args = '-r @github -u 1 -p git: cibw -o windows -e CIBW_ARCHS_WINDOWS=x86 --cibw-skip-add-defaults 0'
            else:
                assert 0, f'Unrecognised {arg=}, should be one of --release-1, --release-2, --release-3.'
            new_args = shlex.split(new_args)
            args.argv[pos:] = new_args
            args.pos = pos
            pipcl.log(f'{args.pos=}: {args.argv=}')
            sys.exit(0)
        
        elif arg == '--remote-do':
            remote_do = int(next(args))
        
        elif arg == '--remote-github-workflow':
            remote_github_workflow_id = next(args)
        
        elif arg == '--remote-github-yml':
            state.remote_github_yml = next(args)
            assert state.remote_github_yml.endswith('.yml'), (
                    f'Should end with `.yml`: {state.remote_github_yml=}'
                    )
            
        elif arg == '--remote-github-yml-inputs':
            state.remote_github_yml_inputs = next(args)
            
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
        
        elif arg == '--ticker':
            ticker = float(next(args))
        
        elif arg == '-u':
            state.github_upload = int(next(args))
        
        elif arg == '-v':
            state.venv = int(next(args))
            assert state.venv in (0, 1, 2, 3), f'Invalid {state.venv=} should be 0, 1, 2 or 3.'
        
        elif arg.startswith('-'):
            assert 0, f'Unrecognised option: {arg=}.'
            
        elif arg in ('build', 'cibw', 'run', 'test'):
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
            argv[python_args_pos] = ''  # pylint: disable=used-before-assignment
            e = pipcl.run(f'{python} {shlex.join(argv)}', check=0)
            sys.exit(e)
            
    # Hard-coded ssh/git key paths.
    pymupdfpro_key_path_leaf = 'thirdparty-so-key'
    artifex_software_ssh_key = 'artifex-software-ssh-key'
    
    if state.commands or remote == '@github':
        if venv:
            # Rerun ourselves inside a venv if not already in a venv.
            if venv_in():
                pipcl.log(f'Already in venv')
            else:
            
                if state.graal:
                    if 'cibw' in state.commands:
                        # We don't create graal/pyenv so wheel/build commands
                        # will not work.
                        assert 'build' not in state.commands
                if state.graal and 'cibw' not in state.commands:
                    # Re-run ourselves in a pyenv/Graal venv.
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
                    # Re-run ourselves in a Python venv.
                    venv_name = f'venv-aptest-{platform.python_version()}-{int.bit_length(sys.maxsize+1)}'
                    e = venv_run(
                            sys.argv,
                            venv_name,
                            recreate=(venv>=2),
                            clean=(venv>=3),
                            )
                sys.exit(e)
    
    if remote:  # pylint: disable=too-many-nested-blocks
        argv = args.argv[:]
        argv[remote_arg] = ''   # Change `-r github` to `-r ''`. # pylint: disable=used-before-assignment.
        if remote == '@github':
            pipcl.run('pip install requests')
            branch = f'aptest-{os.environ["USER"]}'    # -{time.strftime("%F-%T")}'
            pipcl.log(f'{branch=}.')

            github_name = 'ArtifexSoftware/aptest'
            if remote_github_workflow_id:
                workflow_id = remote_github_workflow_id
            else:
                # Push ourselves to Git.
                git_push(g_root, 'git@github.com:ArtifexSoftware/aptest.git', branch)

                # Push specified local package repository to Github and update args to
                # point to new location.
                for package_name, (package_location, args_pos) in list(state.packages.items()) + list(state.packages2.items()):
                    if not package_location.startswith(('git:', 'pip:')):
                        # Push to a Github branch and update argv[] to refer to this
                        # Github branch.
                        info = NameInfo(package_name)
                        pipcl.log(f'{package_name=}.')
                        pipcl.log(f'{info.git_remote=}.')
                        git_push(package_location, info.git_remote, branch)
                        argv[args_pos] = f'git:-b {branch} {info.git_remote}'

                if state.remote_github_yml:
                    # Run .yml directly.
                    pipcl.log(f'Running .yml instead of aptest.py: {state.remote_github_yml}')
                    assert len(state.packages) == 1, f'Running yml directly requires exactly one package, but {len(state.packages)=}.'
                    for package_name, (package_location, args_pos) in state.packages.items():
                        pass
                    info = NameInfo(package_name)
                    github_name = info.github_name
                    data = dict()
                    data['ref'] = branch
                    if state.remote_github_yml_inputs:
                        inputs = dict()
                        for nv in state.remote_github_yml_inputs.split(','):
                            n, v = nv.split('=', 1)
                            inputs[n] = v
                        data['inputs'] = inputs
                    workflow_id = github.gh_run_workflow(
                            f'https://api.github.com/repos/{github_name}',
                            state.remote_github_yml,
                            data,
                            )
                else:
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
                    f'https://api.github.com/repos/{github_name}',
                    'test.yml',
                    workflow_id,
                    #extra_wheels=upload_extra_wheels,
                    upload='pypi' if state.github_upload else None,
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
                label = remote
                remote = None
            elif remote_ssh:
                ssh_command = remote
                remote = None
                label = ssh_command
            else:
                ssh_command = 'ssh'
                label = remote
            pipcl.log(f'{ssh_command=}')

            if remote_do:
                git_paths = list()
                for package_name, (package_location, args_pos) in list(state.packages.items()) + list(state.packages2.items()):
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
                pipcl.log(f'{command=}')
                pipcl.log(f'{ssh_command=}')

                tee_simple = f'out-{remote}'
                tee = f'{tee_simple}-{time.strftime("%F-%H-%M-%S")}'
                try:
                    pipcl.run(
                            command,
                            prefix=f'{label}: ',
                            out='log',
                            tee=tee,
                            ticker=ticker,
                            )
                finally:
                    # Update softlink after remote command has finished. Avoids
                    # continuoue updates.
                    pipcl.run(f'ln -sf {tee} {tee_simple}')

            if 1:
                # Copy remote wheels back to local machine.
                filters = list()
                for package in state.packages_build:
                    filters.append(f'--include={package}-*.whl')
                    filters.append(f'--include={package}-*.tar.gz')
                filters.append('--exclude=*')
                sync_reverse(
                        remote, remote_dir,
                        f'aptest-wheelhouse/',
                        f'aptest-wheelhouse/',
                        ssh_command=ssh_command,
                        filters=filters,
                        )

        return
        
    if not state.commands and not remote_github_workflow_id:
        pipcl.log(f'##Warning, no commands specified so nothing to do.')
    
    if state.run_commands and 'run' not in state.commands:
        pipcl.log(f'## Warning, --run was specified but no `run` command.')
    
    # Clone/update/build swig if specified.
    swig_binary = pipcl.swig_get(state.swig, state.swig_quick)
    pipcl.log(f'{state.swig=}')
    pipcl.log(f'{swig_binary=}')
    if swig_binary:
        # Prevent individual builds from installing default swig.
        state.env_extra['PYMUPDF_SETUP_SWIG'] = swig_binary
        state.env_extra['PYMUPDFPRO_SETUP_SWIG'] = swig_binary
        state.env_extra['PYMUPDF_LAYOUT_SETUP_SWIG'] = swig_binary
    
    # Set environment variables to give access to required git repositories.
    #
    paths_to_delete = list()
    if 1:
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
            pipcl.log(f'## May not be able to clone/update/test pymupdfpro/layout because ARTIFEX_SOFTWARE_SSH_KEY unset and file {artifex_software_ssh_key!r} does not exist')
            state.ssh_key_path_abs = None
        if state.ssh_key_path_abs:
            # We need to use forward slashes on Windows.
            ssh_key_path_abs = state.ssh_key_path_abs.replace('\\', '/')
            GIT_SSH_COMMAND = f'ssh -i {ssh_key_path_abs} -o StrictHostKeyChecking=no'
            state.env_extra['GIT_SSH_COMMAND'] = GIT_SSH_COMMAND
            pipcl.log(f'Using {GIT_SSH_COMMAND=}.')
            #APTEST_SSH_KEY = os.path.abspath(key_path)
            #state.env_extra['APTEST_SSH_KEY'] = APTEST_SSH_KEY

    if 'pymupdfpro' in state.packages_build:
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
                pipcl.log(f'## May not be able to build pymupdfpro because PYMUPDFPRO_SETUP_SOT_KEY unset and file {PYMUPDFPRO_SETUP_SOT_KEY_PATH!r} does not exist')
    
    def build_sdist(package, directory):
        if package == 'pymupdf':
            pipcl.run(
                    f'cd {directory} && python setup.py -d {g_root_abs}/wheelhouse sdist',
                    prefix='sdist {package}: ',
                    )
    
    if (1
            and os.environ.get('GITHUB_ACTIONS') == 'true'
            and pipcl.darwin()
            and platform.machine()=='x86_64'
            ):
        # We need to set MACOSX_DEPLOYMENT_TARGET here to avoid build errors
        # with mupdf's tesseract code.
        #
        MACOSX_DEPLOYMENT_TARGET = os.environ.get('MACOSX_DEPLOYMENT_TARGET')
        pipcl.log(f' {MACOSX_DEPLOYMENT_TARGET=}.')
        MACOSX_DEPLOYMENT_TARGET = '10.15'
        pipcl.log(f' {MACOSX_DEPLOYMENT_TARGET=}.')
        state.env_extra['MACOSX_DEPLOYMENT_TARGET'] = MACOSX_DEPLOYMENT_TARGET
    
    try:    # pylint: disable=too-many-nested-blocks.
        # Handle commands.
        #
        for command in state.commands:
            pipcl.log(f'### {command=}.')
            if 0:
                pass

            elif command == 'build':

                pipcl.run(f'pip install --upgrade piprepo setuptools')
                pypi_local = os.path.abspath(f'aptest-pypi')
                wheelhouse_local = os.path.abspath(f'aptest-wheelhouse')
                pipcl.fs_ensure_empty_dir(pypi_local)
                pipcl.fs_ensure_empty_dir(wheelhouse_local)
                pipcl.run(f'piprepo build {pypi_local}')

                for package in state.packages_build:
                    pipcl.log(f'{package=}')
                    location, args_pos = state.packages[package]
                    if not location:
                        continue
                    if location.startswith('pip:'):
                        assert package != 'mupdf', f'Not a package on pypi.org: {package}'
                        command = f'pip install -v'
                        command += f' {package}{location[4:]}'
                        pipcl.run(command)
                    else:
                        directory = _get_local(package, state)
                        directory_abs = os.path.abspath(directory)
                        pipcl.log(f'{package=}')
                        if package == 'mupdf':
                            state.env_extra['PYMUPDF_SETUP_MUPDF_BUILD'] = directory_abs
                            # fixme: be able to set to '' for system install?
                        else:
                            pipcl.run(f'pip uninstall -y {package}')
                            
                            if state.sdists:
                                build_sdist(package, directory)

                            if (package == 'pymupdf'
                                    and state.graal
                                    and (
                                        'pymupdfpro' in state.packages_build
                                        or 'layout' in state.packages_build
                                        )
                                    ):
                                # As of 2025-08-07, pipcl does graal builds by
                                # running a non-graal build with graal python's
                                # include and library paths.
                                #
                                # In the non-graal build, out setup.py will
                                # still want to do `import pymupdf`, so we
                                # prepare a non-graal venv containing its own
                                # build of the specified pymupdf, and tell
                                # pipcl to use it when it does the non-graal
                                # build. Thus pymupdfpro's setup.py will be
                                # able to do `import pymupdf` etc.
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
                                # builds pymupdfpro/layout later on.
                                state.env_extra['PIPCL_GRAAL_NATIVE_VENV'] = os.path.abspath(venv_native)

                            if state.build_type:
                                if package == 'pymupdf':
                                    state.env_extra['PYMUPDF_SETUP_MUPDF_BUILD_TYPE'] = state.build_type
                                if package == 'pymupdfpro':
                                    state.env_extra['PYMUPDFPRO_SETUP_BUILD_TYPE'] = state.build_type
                                if package == 'pymupdf_layout':
                                    state.env_extra['PYMUPDF_LAYOUT_SETUP_BUILD_TYPE'] = state.build_type
                                    
                            new_files = pipcl.NewFiles(f'{wheelhouse_local}/{package}*.whl')
                            pipcl.run(
                                    #f'pip wheel -v --extra-index-url file://{pypi_local}/simple --no-cache-dir -w {wheelhouse_local} {directory_abs}',
                                    f'pip wheel -v --extra-index-url file://{pypi_local}/simple -w {wheelhouse_local} {directory_abs}',
                                    env_extra=state.env_extra,
                                    prefix=f'build {package}: ',
                                    )
                            wheel = new_files.get_one()
                            pipcl.run(
                                    #f'pip install -v --extra-index-url file://{pypi_local}/simple --no-cache-dir {wheel}',
                                    f'pip install -v --extra-index-url file://{pypi_local}/simple {wheel}',
                                    env_extra=state.env_extra,
                                    prefix=f'install {package}: ',
                                    )
                        pipcl.run(
                                f'piprepo sync {wheelhouse_local} {pypi_local}',
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
                    state.env_extra['CIBW_PYODIDE_VERSION'] = state.cibw_pyodide_version
                    state.env_extra['CIBW_ENABLE'] = 'pyodide-prerelease'

                packages = list()
                for package in state.packages_build:
                    pipcl.log(f'{package=}')
                    directory = _get_local(package, state)
                    if not directory:
                        # location is pip.
                        # cibuildwheel will download from pypi as required.
                        continue
                    directory_abs = os.path.abspath(directory)
                    if package == 'mupdf':
                        if platform.system() == 'Linux' and not state.cibw_pyodide:
                            # Need /host/ prefix so accessible from within manylinux docker.
                            state.env_extra['PYMUPDF_SETUP_MUPDF_BUILD'] = f'/host{directory_abs}'
                        else:
                            state.env_extra['PYMUPDF_SETUP_MUPDF_BUILD'] = directory_abs
                        # fixme: be able to set to '' for system install?
                        continue
                    
                    if state.sdists and platform.system() == 'Linux':
                        build_sdist(package, directory)

                    # Tell cibuildwheel how to test <package>.
                    if package in state.packages_test:
                        CIBW_TEST_COMMAND = f'python {{project}}/scripts/test.py test'
                        if state.pytest_options:
                            if package == 'pymupdf':
                                CIBW_TEST_COMMAND += f' -p {shlex.quote(state.pytest_options)}'
                            elif package == 'pymupdfpro':
                                CIBW_TEST_COMMAND += f' -t {shlex.quote(state.pytest_options)}'
                            elif package == 'pymupdf_layout':
                                CIBW_TEST_COMMAND += f' -t {shlex.quote(state.pytest_options)}'
                            else:
                                pipcl.log(f'Unable to add {state.pytest_options=} to CIBW_TEST_COMMAND.')
                        state.env_extra['CIBW_TEST_COMMAND'] = CIBW_TEST_COMMAND
                                
                    else:
                        pipcl.log(f'Not testing because not in state.packages_test: {package=}')
                    # fixme: prefer to just run pytest directly. Needs
                    # test/conftest.py to always `pip install` packages
                    # required for testing.
                    #state.env_extra['CIBW_TEST_COMMAND'] = f'pytest {{project}}/tests'

                    # Use a copy of state.env_extra because we modify it if
                    # using manylinux docker.
                    #
                    env_extra = state.env_extra.copy()
                    
                    if platform.system() == 'Linux':
                        prefix = '/host'
                        # Update GIT_SSH_COMMAND and
                        # PYMUPDFPRO_SETUP_SOT_KEY_PATH if set, to be within
                        # /host in manylinux docker. Otherwise for example
                        # tests that access remote git repositories will not
                        # use the appropriate key.
                        GIT_SSH_COMMAND_0 = env_extra.get('GIT_SSH_COMMAND')
                        if GIT_SSH_COMMAND_0:
                            GIT_SSH_COMMAND = f'ssh -i {prefix}{state.ssh_key_path_abs} -o StrictHostKeyChecking=no'
                            pipcl.log(f'Changing GIT_SSH_COMMAND from {GIT_SSH_COMMAND_0!r} to {GIT_SSH_COMMAND!r}.')
                            env_extra['GIT_SSH_COMMAND'] = GIT_SSH_COMMAND
                        
                        PYMUPDFPRO_SETUP_SOT_KEY_PATH = env_extra.get('PYMUPDFPRO_SETUP_SOT_KEY_PATH')
                        if PYMUPDFPRO_SETUP_SOT_KEY_PATH:
                            env_extra['PYMUPDFPRO_SETUP_SOT_KEY_PATH'] = f'{prefix}{os.path.abspath(PYMUPDFPRO_SETUP_SOT_KEY_PATH)}'
                    else:
                        prefix = ''
                    
                    if platform.system() == 'Linux' and package == 'pymupdfpro':
                        # Build will run inside a CentOS-7 container; we
                        # need to install fontconfig-devel so `#include
                        # <fontconfig/fonctconfig.h>` works. And for SO build
                        # we need ssh to allow its git submodule commands.
                        #
                        env_extra['CIBW_BEFORE_BUILD_LINUX'] = (
                                'echo "installing fontconfig-devel and ssh"'
                                ' && yum -y install fontconfig-devel'
                                ' && yum groupinstall -y fonts'
                                ' && yum install -y openssh-clients'
                                )
                    
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
                    CIBW_ENVIRONMENT_PASS_LINUX.append('PYMUPDFPRO_SETUP_SOT_KEY')  # This can be set in os.environ.
                    CIBW_ENVIRONMENT_PASS_LINUX.sort()
                    CIBW_ENVIRONMENT_PASS_LINUX = ' '.join(CIBW_ENVIRONMENT_PASS_LINUX)
                    env_extra['CIBW_ENVIRONMENT_PASS_LINUX'] = CIBW_ENVIRONMENT_PASS_LINUX

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

            elif command == 'run':
                for package, command in state.run_commands:
                    directory = _get_local(package, state)
                    pipcl.run(f'cd {directory} && {command}')

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
                
                failed_packages = list()
                
                for package in state.packages_test:
                    location, _ = state.packages[package]
                    if not location:
                        continue
                    if package == 'mupdf':
                        continue
                    directory = _get_local(package, state, test=1)
                    if not directory:
                        continue
                    command = f'pytest'
                    if state.pytest_options:
                        command += f' {state.pytest_options}'
                    if state.pytest_paths:
                        for path in state.pytest_paths:
                            command += f' {directory}/{path}'
                    else:
                        command += f' {directory}'
                    if state.pytest_wrap in ('valgrind', 'helgrind'):
                        if not state.pytest_options:
                            command += ' -sv'
                    if state.pytest_wrap:
                        command = f'python -m {command}'
                        if state.pytest_wrap == 'gdb':
                            command = f'gdb --args {command}'
                        elif state.pytest_wrap == 'valgrind':
                            state.env_extra['PYMUPDF_RUNNING_ON_VALGRIND'] = '1'
                            state.env_extra['PYTHONMALLOC'] = 'malloc'
                            command = (
                                    f' valgrind'
                                    f' --suppressions={g_root_abs}/valgrind.supp'
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
                    e = pipcl.run(
                            command,
                            env_extra=state.env_extra,
                            prefix=f'pytest {package}: ',
                            check=0,
                            )
                    if e:
                        failed_packages.append(package)
                    if failed_packages:
                        pipcl.log(f'Tests failed for these packages:')
                        for package in failed_packages:
                            pipcl.log(f'    {package}')
                        raise Exception(f'Packages failed tests: {failed_packages}')

            else:
                assert 0, f'{command=}'
    finally:
        for path in paths_to_delete:
            pipcl.fs_remove(path)


def _get_local(package, state, test=False):
    '''
    Returns local directory containing <package> checkout. Returns None if
    location is pip:.
    '''
    location, _ = state.packages[package]
    info = NameInfo(package)
    if location.startswith('pip:') and test:
        # Use second location of <package> if specified.
        location, _ = state.packages2.get(package, (None, None))
        if location is None:
            return None
        pipcl.log(f'Using second specified location for {package=}: {location}')
    if location.startswith('git:'):
        directory = pipcl.git_get(
                local=f'aptest-git-{package}',
                remote=info.git_remote,
                branch=info.git_branch,
                text=location,
                env_extra=state.env_extra,
                submodules=info.submodules,
                )
    else:
        directory = location
    return directory
    

def github_workflow_unimportant():
    '''
    Returns true if we are running a Github scheduled workflow but in a
    repository not called 'main'. This can be used to avoid consuming
    unnecessary Github minutes running workflows on non-main branches.
    '''
    GITHUB_EVENT_NAME = os.environ.get('GITHUB_EVENT_NAME')
    GITHUB_REPOSITORY = os.environ.get('GITHUB_REPOSITORY')
    if GITHUB_EVENT_NAME == 'schedule':
        _sha, _comment, _diff, branch = pipcl.git_info(g_root)
        if branch != 'main':
            pipcl.log(f'## This is an unimportant Github workflow on non-main branch.')
            pipcl.log(f'## {GITHUB_EVENT_NAME=}.')
            pipcl.log(f'## {GITHUB_REPOSITORY=}.')
            pipcl.log(f'## {branch=}.')
            return True
    return False


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


def fs_write_key(path, data):
    '''
    Writes <data> to <path>, ensuring that <path> is created with appropriate
    permissions.
    '''
    pipcl.fs_remove(path)
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
