#! /usr/bin/env python3

'''Developer build/test script for Artifex packages.

See README.rst for details.
'''

import atexit
import glob
import importlib.metadata
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import textwrap
import time
import xml.dom.minidom


class AptestUserError(Exception):
    pass


def Assert(ok, message):
    if not ok:
        raise AptestUserError(message)


try:
    import autovenv
except ImportError:
    from . import autovenv

# Things for bash command-line completion.
COMP_LINE = os.environ.get('COMP_LINE')
COMP_POINT = os.environ.get('COMP_POINT')
#COMP_TYPE = os.environ.get('COMP_TYPE')


# Use autovenv.py to create/enter a venv.
# Note that we don't have a way to use anything other than pypi's pipcl.
create = 2
verbose = 1
packages = ['pipcl']
if sys.argv[1:] == ['completion'] or COMP_LINE:
    # We don't want autovenv to output debug info because it'll badly mess
    # up completion. And we use `create = 1` for speed.
    create = 1
    verbose = 0
    packages = None

g_venv_prefix = f'venv-aptest'
autovenv.enter(
        venv_prefix=g_venv_prefix,
        create=create,
        packages=packages,
        verbose=verbose,
        )

import pipcl    # pylint:disable=wrong-import-position

# Import local files directly or from our package if we are installed.
try:
    import backtrace
    import cli
    import doct
    import graph
    import github
except ImportError:
    from . import backtrace
    from . import cli
    from . import doct
    from . import graph
    from . import github


# Get improved display of exceptions and stacktraces.
backtrace.exception_hook_install()

g_root_abs = os.path.abspath( f'{__file__}/..')
g_root = pipcl.relpath(g_root_abs)
g_date_time = time.strftime('%F-%H-%M-%S')

# With cibw we build and test Python 3.x for x in this range.
python_versions_minor = range(10, 14+1)

g_devel = False
g_atexit = None
g_log_tee = None    # Used to output final `Aptest: log output is in: aptest-out-2026-03-18-15-40-15`.

# We use APTEST_NESTED to indicate that we are being re-run inside a venv or on
# a remote machine, by an outer aptest invocation.
#
APTEST_NESTED = os.environ.get('APTEST_NESTED')

# Sometimes we modify defaults if running on Github.
GITHUB_ACTIONS = os.environ.get('GITHUB_ACTIONS')


def cibw_cp(*version_minors):
    '''
    Returns <version_tuples> in 'cp39*' format, e.g. suitable for CIBW_BUILD.
    '''
    ret = list()
    for version_minor in version_minors:
        ret.append(f'cp3{version_minor}*')
    return ' '.join(ret)


def git_push(path, repository, remote_branch, state, *, tmpcommit=True, doit=True):
    '''
    Pushes <path> to <repository> (or 'origin' if None).
    
    If <tmpcommit> is true, we do a temporary commit of any uncommitted changes
    before pushing, then restore. Note that this will forget about newly added
    files.
    
    Used by `-r @github`.
    '''
    _sha, _comment, _diff, branch = pipcl.git_info(path)
    if not doit:
        return branch
    if tmpcommit:
        diff = pipcl.run(f'cd {path} && git diff --ignore-submodules=dirty', capture=1)
        if diff:
            # `git stash && git apply` leaves everything unchanged, but creates
            # an item on stash list that will restore all changes including
            # newly-added files.
            pipcl.run(f'cd {path} && git stash && git stash apply')
            pipcl.run(f'cd {path} && git commit -m "Aptest temporary commit" -a')
    tmp_path_remove = None
    try:
        key_path, key_env = _get_key(state, repository)
        if key_path or key_env:
            if not key_path:
                key_path = os.path.abspath('aptest-tmp-git-key')
                tmp_path_remove = key_path
                pipcl.fs_write_key(key_path, os.environ[key_env])
            GIT_SSH_COMMAND = f'ssh -i {os.path.abspath(key_path)} -o StrictHostKeyChecking=no'
            GIT_SSH_COMMAND = GIT_SSH_COMMAND.replace('\\', '/')    # Required on windows.
            env_extra = state.env_extra | dict(GIT_SSH_COMMAND = GIT_SSH_COMMAND)
        else:
            env_extra = state.env_extra
        pipcl.run(
                f'cd {path} && git push -fv {repository or "origin"} HEAD:{remote_branch}',
                prefix='git push: ',
                env_extra=env_extra,
                )
    finally:
        if tmpcommit and diff:
            # Restore all uncommitted changes, including newly added files.
            pipcl.run(f'cd {path} && git reset --hard HEAD~1')
            pipcl.run(f'cd {path} && git stash pop')
        if tmp_path_remove:
            assert '-tmp-' in tmp_path_remove
            pipcl.fs_remove(tmp_path_remove)
    return branch


def sync_reverse(
        remote,
        remote_dir,
        path_remote,
        path_local,
        *,
        ssh_command,
        state,
        filters=None,
        verbose=1,
        doit=1,
        extra=None,
        check=1,
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
    extra:
        Extra rsync args, for example --ignore-missing-args.
    '''
    ssh_command2 = ssh_command
    if remote:
        ssh_command2 += f' {remote}'
    command = f'rsync -aizr'
    if not doit:
        command += ' -n'
    if verbose:
        command += ' --stats'
    if extra:
        command += f' {extra}'
    command += f' --rsh {shlex.quote(ssh_command2)}'
    if filters:
        if isinstance(filters, str):
            #filters = (filters,)
            command += f' {filters}'
        else:
            command += f' {shlex.join(filters)} '
    command += (
            f' :{remote_dir}/{path_remote} {path_local}'
            )
    return pipcl.run(command, prefix=f'reverse sync {path_remote} => {path_local}: ', log=1, check=check, ticker=state.ticker)
        

def sync(remote, remote_dir, path, ssh_command, verbose, state):    # pylint: disable=too-many-positional-arguments
    '''
    Syncs <path> to <remote>:<remote_dir>/ using rsync.
    
    If <path>/.git is a directory we sync only files known to git and return true.
    
    Otherwise we sync the entire directory and return false.
    '''
    ret = None
    ssh_command2 = f'{ssh_command}'
    if remote:
        ssh_command2 += f' {remote}'
    command = (
            f'rsync -Raizr '
            f'{"--stats " if verbose else ""}'
            f'--rsh {shlex.quote(ssh_command2)} '
            )
    if state.remote_rsync_path:
        command += f'--rsync-path {shlex.quote(state.remote_rsync_path)} '
    if state.remote_rsync_wsl:
        command += f'--no-p --rsync-path "wsl rsync" '
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
            pipcl.log(f'{filenames_path=}')
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
        pipcl.run(command, prefix=f'sync {path}: ', out='log', ticker=state.ticker)
    finally:
        if filenames_path:
            pipcl.fs_remove(filenames_path)
    return ret


# Hard-coded information about supported packages. This used when deferring
# to Github with `-r @github`. The `aliases` items are used when looking at
# command-line arguments etc.
#
g_package_info = {
        'aptest':
            {
                'git_remote': 'git@github.com:ArtifexSoftware/aptest.git',
                'git_branch': 'main',
                'aliases':  [],
                'order': -1,
            },
        'mupdf':
            {
                'git_remote': 'git@github.com:ArtifexSoftware/mupdf.git',
                'git_branch': 'master',
                'aliases':  ['m'],
                'order': 0,
            },
        'pdf2docx':
            {
                'git_remote': 'git@github.com:ArtifexSoftware/pdf2docx.git',
                'git_branch': 'master',
                'aliases':  [],
                'order': 2,
            },
        'pymupdf':
            {
                'git_remote': 'git@github.com:pymupdf/PyMuPDF.git',
                'git_branch': 'main',
                'aliases':  ['p'],
                'order': 1,
            },
        'pymupdf4llm':
            {
                'git_remote': 'git@github.com:pymupdf/pymupdf4llm.git',
                'git_branch': 'main',
                'aliases':  ['4llm'],
                'order': 3, # Need to be higher than pymupdf_layout.
            },
        'pdf4llm':
            {
                'git_remote': 'git@github.com:pymupdf/pymupdf4llm.git',
                'git_branch': 'main',
                'aliases':  [],
                'order': 4, # Need to be higher than pymupdf_layout.
            },
        'pymupdfpro':
            {
                'git_remote': 'git@github.com:ArtifexSoftware/PyMuPDFPro.git',
                'git_branch': 'main',
                'aliases':  ['pro'],
                'order': 2,
            },
        'pymupdf_layout':
            {
                'git_remote': 'git@github.com:ArtifexSoftware/sce.git',
                'git_branch': 'master',
                'aliases':  ['layout'],
                'submodules': False,
                'order': 2,
            },
        'langchain_pymupdf_layout':
            {
                'git_remote': 'git@github.com:pymupdf/langchain-pymupdf-layout.git',
                'git_branch': 'main',
                'aliases':  ['langchain'],
                'order': 4,
            },
        'smartoffice':
            {
                'git_remote': 'git@gitlab.artifex.com:smartoffice/sot.git',
                'git_branch': 'master',
                'aliases':  ['sot'],
                'submodules': False,
                'order': 1, # Fetch before Layout
            },
        'smartoffice-marina':
            {
                'git_remote': 'git@github.com:epapyrusinc/marina.git',
                'git_branch': 'master',
                'aliases':  ['marina'],
                'submodules': True,
                'order': 1, # Fetch before Layout
            },
        'smartoffice-neo':
            {
                'git_remote': 'git@gitlab.artifex.com:smartoffice/smartoffice.git',
                'git_branch': 'master',
                'aliases':  ['sot-neo', '--neoso'],
                'submodules': True,
                'order': 1, # Fetch before Layout
            },
        'pdf_feature_inspector':
            {
                'git_remote': 'git@github.com:ArtifexSoftware/pdf_feature_inspector.git',
                'git_branch': 'main',
                'aliases':  ['pfi'],
                'order': 5,
            },
        
        'pipcl':
            {
                'git_remote': 'git@github.com:ArtifexSoftware/pipcl.git',
                'git_branch': 'main',
                'aliases':  [],
                'order': -2,
            },
        
        # Experimental, doesn't work.
        'presidio':
            {
                'git_remote': 'git@github.com:ArtifexSoftware/presidio.git',
                'git_branch': 'main',
                'aliases':  list(),
                'order': 4,
            },
        
        'swig':
            {
                'git_remote': None,
                'order': -1,
                'aliases':  list(),
            },
        }

for name, value in g_package_info.items():
    assert 'aliases' in value, f'g_package_info[{name!r}] has no alias list'
    if value.get('submodules') is None:
        value['submodules'] = True
    assert 'git_remote' in value, f'Need "git_remote" entry in {name}={value}'


def arg_alias(arg):
    '''
    Returns full name if arg is --<alias> in g_package_info.
    
    If <arg> is upper-case we return upper-case full name.
    '''
    for fullname, info in g_package_info.items():
        for alias in [fullname] + info.get('aliases', list()):
            alias = f'-{alias}' if len(alias) == 1 else f'--{alias}'
            if arg == alias:
                return fullname
            elif arg == alias.upper():
                return fullname.upper()


def package_alias(package):
    '''
    Returns full name if arg is an alias in g_package_info.
    '''
    for fullname, info in g_package_info.items():
        #pipcl.log(f'{fullname=} {info=}')
        if package in [fullname] + info['aliases']:
            return fullname
    Assert(0, f'Unrecognised package name/alias: {package!r}')


def package_aliases(packages):
    '''
    Returns list of full names, from list of names/aliases or string containing
    comma-separated names/aliases.
    '''
    if isinstance(packages, cli.Arg):
        packages = packages.as_text()
    if isinstance(packages, str):
        packages = packages.split(',')
    ret = list()
    for package in packages:
        for fullname, info in g_package_info.items():
            if package in [fullname] + info.get('aliases', list()):
                ret.append(fullname)
    return ret


def gh_runner_alias(name):
    '''
    Returns full name if arg is an alias for a github runner OS.
    '''
    runner_aliases = [
            ('macos-14',         ['macos', 'macos-arm']),
            ('macos-15-intel',   ['macos-intel']),
            ('ubuntu-24.04-arm', ['linux-arm']),
            ('ubuntu-latest',    ['linux', 'linux-intel']),
            ('windows-11-arm',   ['windows-arm']),
            ('windows-2022',     ['windows', 'windows-intel']),
            ]
    for fullname, aliases in runner_aliases:
        if name in [fullname] + aliases:
            return fullname
    
    pipcl.log(f'Using unrecognised Github runner {name=}.')
    return name


def name_info(state, package):
    '''
    Returns dict with info about a package from g_package_info, or a dict with
    empty info if not found.
    '''
    ret = g_package_info.get(package)
    if ret:
        for a, b in sorted(state.git_remote_modifications, reverse=1):
            git_remote0 = ret['git_remote']
            if git_remote0.startswith(a):
                git_remote = b + git_remote0[len(a):]
                ret = ret.copy()
                ret['git_remote'] = git_remote
                pipcl.log(f'For {package=} have changed git_remote from {git_remote0!r} to {git_remote!r}.')
                break
        return ret
    ret = {
            'git_remote': None,
            'git_branch': None,
            'aliases':  list(),
            'submodules': True,
            'order': 0,
            }
    return ret


def _test_completion(COMP_LINE):
    '''
    Internal, runs with COMP_LINE set to mimic completion request from shell.
    '''
    pipcl.log('\n\n\n')
    os.environ['COMP_LINE'] = COMP_LINE
    os.environ['COMP_POINT'] = str(len(COMP_LINE))
    os.environ['COMP_TYPE'] = '63'
    text = pipcl.run(COMP_LINE, capture=str, check=1)
    print(text)


def dummy_completion1():
    '''
    >>> _test_completion(f'{__file__} --sdi')
        --sdists
    '''
    
def dummy_completion2():
    '''
    >>> _test_completion(f'{__file__} --sdists=')
        0
        false
        False
        1
        true
        True
    '''

def dummy_completion3():
    '''
    >>> _test_completion(f'{__file__} -r')   # doctest: +REPORT_UDIFF +ELLIPSIS
        <class 'str'>
    '''


def apply_deltas(items, deltas, check=1, aliasfn=lambda name: name):
    '''
    Modifies <items> according to <deltas>.
    
    items:
        A list of strings.
    deltas:
        List of strings. Each is '+', '-' or '', followed by a name, or alias
        for a name as decide by <aliasfn>.
    check:
        If true we raise an exception if asked to remove a name that is not in
        <items>.
    aliasfn:
        Function that takes an alias and returns the full name.
    '''
    if deltas and not deltas[0].startswith(('+', '-')):
        del items[:]

    for delta in deltas:
        if delta == '-':
            del items[:]
        elif delta.startswith('-'):
            try:
                items.remove(aliasfn(delta[1:]))
            except Exception:
                #pipcl.log(f'Failed to remove {delta[1:]=} from {items=}')
                if check:
                    raise
        else:
            if delta.startswith('+'):
                delta = delta[1:]
            delta = aliasfn(delta)
            items.append(delta)

    
def add_package(state, name, location):
    '''
    Used by `-i` and alias options such as `--layout`.
    '''
    assert isinstance(name, str)
    assert isinstance(location, cli.Arg)
    if not location.text.startswith(('git:', 'pip:')):
        # Match with local checkouts to help arg completion.
        ok_locations = list()
        for path in sorted(glob.glob(f'*/.git/')):
            #ok_locations.append(path[:-5])  # With trailing `/`.
            ok_locations.append(path[:-6])
        ok_locations.sort()
        if location not in ok_locations and not os.path.isdir(f'{location.as_str()}/.git'):
            if COMP_LINE:
                # Raise exception to force listing of available checkouts.
                Assert(location in ok_locations, f'Location is not a Git checkout in current directory: {location}')
            else:
                # Just output a warning.
                pipcl.log(f'Warning, location is not a Git checkout in current directory: {location=}')
    
    if name.lower() != name:
        # Upper case names are defaults for making releases, for which we use
        # state.packages_for_release.
        state.packages_for_release[name.lower()] = location # A cli.Arg.
        return
    
    location_str = location.as_str()
    
    # Internal debugging only.
    if pipcl.windows() and not location.text.startswith(('git:', 'pip:')):
        APTEST_PACKAGE_LOCATION_LOWERCASE = state.env_extra.get(f'APTEST_PACKAGE_LOCATION_LOWERCASE')
        pipcl.log(f'{APTEST_PACKAGE_LOCATION_LOWERCASE=}')
        pipcl.log(f'{name=}')
        pipcl.log(f'{location=}')
        if APTEST_PACKAGE_LOCATION_LOWERCASE == name:
            pipcl.log(f'{APTEST_PACKAGE_LOCATION_LOWERCASE=} Forcing lower case for {location_str=}.')
            location_str = location_str.lower()
            pipcl.log(f'{location_str=}')
    
    location_pos = (location_str, location.pos)
    
    if name in state.packages:
        pipcl.log(f'Adding second location for {name=} testing only: {location=}')
        state.packages2[name] = location_pos
        return
    
    state.packages[name] = location_pos
    
    n_smartoffice = 0
    for p in state.packages:
        if p.startswith('smartoffice'):
            n_smartoffice += 1
    Assert(n_smartoffice <= 1, f'Only one `smartoffice*` package can be specified.')
    
    state.packages_build.append(name)
    state.packages_test.append(name)

    def keyfn(name):
        info = g_package_info.get(name)
        if info:
            return info['order']
        else:
            return 0
    state.packages_build.sort(key=keyfn)
    state.packages_test.sort(key=keyfn)


def _add_key(state, prefix, path, env, pos):
    if path:
        path = os.path.expanduser(path)
    state.keys.append((prefix, path, env, pos))
    state.keys.sort(reverse=True)
    

def get_args(argv):
    '''
    Parses command-line args in <argv> and returns a State instance. Any
    changes to behaviour of this function should be added to README.md.

    If we are being called by bash for command-line completion, we return
    None.
    '''
    if COMP_LINE:
        # Bash completion; we must not write to stdout.
        del pipcl._log_f[:] # pylint: disable=protected-access
        APTEST_COMPLETION_DEBUG = os.environ.get('APTEST_COMPLETION_DEBUG')
        #print(f'{APTEST_COMPLETION_DEBUG=}', file=sys.stderr, flush=1)
        if APTEST_COMPLETION_DEBUG:
            f = open(APTEST_COMPLETION_DEBUG, 'a')   # pylint: disable=consider-using-with
            pipcl._log_f.append(f)  # pylint: disable=protected-access
        pipcl.log(f'{COMP_LINE=}')
        pipcl.log(f'os.environ COMP_*:')
        for n in sorted(os.environ.keys()):
            if n.startswith('COMP_'):
                v = os.environ[n]
                pipcl.log(f'    {n}: {v!r}')
    
    if argv[1:] == ['completion']:
        # Write bash completion script to stdout and exit.
        print(textwrap.dedent(f'''
                _aptest_py() {{
                    COMPREPLY=($( \\
                            COMP_LINE="$COMP_LINE" \\
                            COMP_POINT="$COMP_POINT" \\
                            COMP_TYPE="$COMP_TYPE" \\
                            {os.path.abspath(argv[0])} \\
                            ))
                }}
                complete -F _aptest_py aptest.py
                '''))
        sys.exit()
    
    class State:
        '''
        Represents parsed args, with protection against adding a new member
        after _frozen` has been set to true.
        '''
        _frozen = False # So self._frozen exists at start of __init__().
        def __init__(self):
            pass
        
        def freeze(self):
            self._frozen = True
        
        def __setattr__(self, name, value):
            if self._frozen:
                assert hasattr(self, name), f'Unrecognised state {name=}.'
            super().__setattr__(name, value)
    
    state = State()
    
    state.build_type = None
    state.build_pip_no_clean = False
    state.check_pushed = False
    state.check_unchanged = False
    state.cibw_ignore_test_failures = False
    state.cibw_name = 'cibuildwheel'
    state.cibw_pyodide = None
    state.cibw_pyodide_version = None
    state.cibw_skip_add_defaults = True
    state.clean_git = list()
    state.clean_setup = list()
    state.clean_setup_all = list()
    state.clean_wheelhouse = 'auto'
    state.commands = list()
    state.devel = False
    state.draft_location = None
    state.env_extra = dict()
    state.git_depth = 1
    state.git_local_detailed = False
    state.git_remote_modifications = list()
    state.github_upload = None
    state.gnn_doit = False
    state.gnn_show_graph = None
    state.gnn_show_text = None
    state.gnn_show_paths = list()
    state.gnn_show_select = None
    state.gnn_show_select_root = None
    state.graal = False
    
    state.keys = list()
    if GITHUB_ACTIONS == 'true':
        # Add known keys from aptest's Github repository secrets. This is
        # required - otherwise scheduled workflow runs are unable to clone
        # Github/Gitlab repositories.
        _add_key(state, 'git@github.com:', '', 'ARTIFEX_SOFTWARE_SSH_KEY', 0)
        _add_key(state, 'git@gitlab.artifex.com:', '', 'PYMUPDFPRO_SETUP_SOT_KEY', 0)
    
    state.os_names = list()
    state.packages2 = dict()   # map from name to location.
    state.packages_build = list() # Sorted list of names.
    state.packages = dict()   # map from name to location.
    state.packages_test = list()  # Sorted list of names.
    state.packages_for_release = dict()
    state.pytest_junit_xml = False
    state.pytest_options = ''
    state.pytest_paths = list()
    state.pytest_timeout = None
    state.pytest_timeout_method = None
    state.pytest_wrap = None
    state.python = None
    state.remote_dir = 'artifex-remote'
    state.remote_arg = None
    state.remote_do = True
    state.remote_github_workflow_id = None
    state.remote_github_runners = [
            'macos-14',
            #'macos-15-intel',
            'ubuntu-latest',
            'windows-2022',
            ]
    state.remote_github_yml_inputs = None
    state.remote_github_yml = None
    state.remote = None
    state.remote_prefix = None
    state.remote_prefix_default = dict()
    state.remote_rsync_path = None
    state.remote_rsync_wsl = False
    state.run_commands = list()
    state.sdists = False
    state.show_help = False
    state.ssh_key_path_abs = None
    state.swig = None
    state.swig_quick = None
    state.system_packages = True if GITHUB_ACTIONS == 'true' else False   # pylint: disable=simplifiable-if-expression
    state.system_site_packages = False
    state.tee_auto = False
    state.test_extra_packages = list()
    state.test_gnn_cache = False
    state.test_gnn_det = None
    state.test_gnn_extra = dict()
    state.test_gnn_limit = 0
    state.test_gnn_out = None
    state.test_gnn_push = 0
    state.ticker = 0
    state.valgrind = False
    state.venv = 2
    state.venv_name = None
    
    state.verbose = False
    if GITHUB_ACTIONS == 'true':
        state.verbose = True
    
    state.wheelhouse = 'aptest-wheelhouse'
    state.wheelhouse_release = None
    
    global g_devel
    g_devel = state.devel

    global g_atexit
    
    # Prevent future additions to items in <state>. We can still modify
    # existing values.
    state.freeze()
    
    # Parse args and update the above state. We do this before moving into a
    # venv, partly so we can return errors immediately.
    #
    args_list = list()
    args_list += [argv[0]]
    
    regions = list()
    
    # First read args from ~/.aptest if it exists.
    if os.environ.get('APTEST_DOT_APTEST') != '0' and not APTEST_NESTED:
        aptest_config_path = os.path.expanduser(f'~/.aptest')
        if os.path.exists(aptest_config_path):
            aptest_config = pipcl.fs_read(aptest_config_path)
            aptest_config2 = ''
            for line in aptest_config.split('\n'):
                if not line.startswith('#'):
                    aptest_config2 += f'{line}\n'
            aptest_config = shlex.split(aptest_config2)
            regions.append( ('~/.aptest', len(args_list)))
            args_list += aptest_config
    
    # Read args from APTEST_options if set.
    APTEST_options = os.environ.get('$APTEST_options')
    if APTEST_options:
        APTEST_options = shlex.split(APTEST_options)
        regions.append( ('APTEST_options', len(args_list)))
        args_list += APTEST_options
    
    if COMP_LINE:
        # Bash completion, get args from COMP_LINE instead of sys.argv.
        line = COMP_LINE
        # We don't seem to need to use COMP_POINT.
        if 0 and COMP_POINT:    # pylint: disable=condition-evals-to-constant
            COMP_POINT_int = int(COMP_POINT)
            assert COMP_POINT_int <= len(line)
            line = line[:COMP_POINT_int]
        args_list += shlex.split(line)[1:]
        pipcl.log(f'     {args_list=}')
    else:
        # Normal operation, get args from <argv>.
        regions.append( ('command line', len(args_list)))
        args_list += argv[1:]
        if 0:
            pipcl.log(f'args_list ({len(args_list)}):')
            for i in args_list:
                pipcl.log(f'    {i}')
    args = cli.Args(args_list, 1)
    #pipcl.log(f'{args.args_eq.argv=}')
    try:
        i = 0
        while 1:
            pos0 = args.pos # We sometimes use this below.
            
            # Allow `--foo=bar` here.
            arg = args.next(spliteq=1)
            
            #pipcl.log(f'{arg=}')
            if 0:
                pass

            elif arg == '-a':
                pos1 = args.pos
                pipcl.log(f'{pos0=}')
                pipcl.log(f'{pos1=}')
                _name = next(args).as_text()
                _value = os.environ.get(_name, '')
                pos2 = args.pos
                pipcl.log(f'{pos2=}')
                new_args = shlex.split(_value)
                args.args_eq.replace(pos0, pos2, new_args)
            
            elif arg == '--atexit':
                g_atexit = next(args).as_text()
                args.argv[args.pos-1] = ''  # Omit if we recurse.

            elif arg == '-b':
                _names = next(args).as_text()
                _names = _names.split(',') if _names else list()
                apply_deltas(state.packages_build, _names, aliasfn=package_alias)
                for p in state.packages_build:
                    Assert(p in state.packages, f'Package location not specified: {p}.')

            elif arg == '--build-pip-no-clean':
                state.build_pip_no_clean = args.get_bool()
            
            elif arg == '--build-type':
                build_type = next(args)
                Assert(build_type in ('release', 'debug', 'memento'), f'Unrecognised {build_type=} should be one of: release debug memento')
                state.build_type = build_type.as_text()
            
            elif arg == '--check-pushed':
                state.check_pushed = args.get_bool()

            elif arg == '--check-unchanged':
                state.check_unchanged = args.get_bool()

            elif arg == '--cibw-ignore-test-failures':
                state.cibw_ignore_test_failures = args.get_bool()

            elif arg == '--cibw-name':
                state.cibw_name = next(args)

            elif arg == '--cibw-pyodide':
                state.cibw_pyodide = args.get_bool()

            elif arg == '--cibw-pyodide-version':
                state.cibw_pyodide_version = next(args).as_str()

            elif arg == '--cibw-skip-add-defaults':
                state.cibw_skip_add_defaults = args.get_bool()
            
            elif arg == '--clean-git':
                packages = package_aliases(next(args))
                state.clean_git += packages
            
            elif arg == '--clean-setup':
                packages = package_aliases(next(args))
                state.clean_setup += packages
            
            elif arg == '--clean-setup-all':
                packages = package_aliases(next(args))
                state.clean_setup_all += packages
            
            elif arg == '--clean-wheelhouse':
                state.clean_wheelhouse = args.get_bool()
            
            elif arg == '--clean-wheelhouse-auto':
                state.clean_wheelhouse = 'auto'
            
            elif arg == '--devel':
                state.devel = args.get_bool()
                g_devel = state.devel

            elif arg == '--draft-location':
                state.draft_location = next(args).as_str()

            elif arg == '-e':
                _nv = next(args).as_text()
                Assert('=' in _nv, f'-e <name>=<value> does not contain "=": {_nv!r}')
                _name, _value = _nv.split('=', 1)
                state.env_extra[_name] = _value
            
            elif arg == '--git-depth':
                state.git_depth = next(args).as_int()
            
            elif arg == '--git-local-detailed':
                state.git_local_detailed = args.get_bool()
            
            elif arg == '--git-remote-modify':
                a = next(args).as_str()
                b = next(args).as_str()
                state.git_remote_modifications.append( (a, b))
            
            elif arg == '--gnn-doit':
                state.gnn_doit = args.get_bool()
            
            elif arg == '--gnn-show-graph':
                state.gnn_show_graph = next(args).as_text()
            
            elif arg == '--gnn-show-path':
                state.gnn_show_paths += next(args).as_text().split(',')
            
            elif arg == '--gnn-show-select':
                state.gnn_show_select = next(args).as_text()
            
            elif arg == '--gnn-show-text':
                state.gnn_show_text = next(args).as_text()
            
            elif arg == '--graal':
                state.graal = args.get_bool(overwrite=0)

            elif arg in ('-h', '--help'):
                state.show_help = True

            elif arg == '-i':
                _name = next(args).as_str()
                add_package(state, _name, next(args))
            
            elif arg == '--key':
                prefix = next(args).as_str()
                pos = args.pos
                text = next(args).as_str().split(',')
                if len(text) == 1:
                    path, env = text[0], None
                elif len(text) == 2:
                    path, env = text
                else:
                    Assert(0, f'Expected one or two comma-separted items in {text!r}')
                    path = env = None # Keep pylint happy.
                _add_key(state, prefix, path, env, pos)
            
            elif arg == '--log-prefix':
                _prefix = next(args).as_text()
                if not APTEST_NESTED and not COMP_LINE:
                    pipcl._log_prefix_stack.append(_prefix) # pylint: disable=protected-access
            
            elif package := arg_alias(arg):
                location = next(args)
                add_package(state, package, location)
            
            elif arg == '-o':
                state.os_names += next(args).as_text().lower().split(',')
                names = ('linux', 'windows', 'darwin', 'openbsd')
                for os_name in state.os_names:
                    Assert(os_name in names, f'{os_name=} should be one of {names!r}.')

            elif arg == '--pytest':
                state.pytest_options = next(args).as_text()
            
            elif arg == '--pytest-junit-xml':
                state.pytest_junit_xml = args.get_bool()

            elif arg == '--pytest-path':
                state.pytest_paths.append(next(args).as_text())
            
            elif arg == '--pytest-timeout':
                state.pytest_timeout = next(args).as_float()

            elif arg == '--pytest-timeout-method':
                state.pytest_timeout_method = next(args).as_str()

            elif arg == '--pytest-wrap':
                state.pytest_wrap = next(args)
                Assert(state.pytest_wrap in ('gdb', 'valgrind', 'helgrind'), f'{state.pytest_wrap=} should be one of: gdb valgrind helgrind')

            elif arg == '--python':
                pos = args.pos
                state.python = next(args).as_text()
                args.args_eq.set(pos, '')   # Avoid recursion when we rerun ourselves.
            
            elif arg == '-r':
                state.remote_arg = args.pos
                _remote = next(args)
                # Provide useful command-line completion if _remote starts with @.
                if _remote.startswith('@'):
                    Assert(_remote == '@github', f'{_remote=} should be `@github`.')
                state.remote = _remote.as_text()

            elif arg.startswith('--release-'):
                # Must be last arg.
                #assert args.pos[0] == len(args.argv), f'{len(args.argv)=} {args.pos=}.'
                new_args = ''
                new_args += f' --log-prefix {shlex.quote(arg.as_str() + ": ")}'
                pipcl.log(f'{new_args=}')
                new_args += ' -r @github cibw'
                new_args += ' --check-unchanged'
                new_args += ' --use-release-args'
                
                # If `--MUPDF=...` has been specified, then we need to include
                # mupdf in the list of packages to build. (Usually it is not
                # specified so that pymupdf's default mupdf is used.)
                b_mupdf = 'mupdf,' if 'mupdf' in state.packages_for_release else ''
                
                if 0:
                    pass
                
                elif arg == '--release-test':
                    # Undocumented test option, for quick test of github.
                    new_args += f' --sdists -b {b_mupdf}pymupdf4llm --cibw-ignore-test-failures'
                
                elif arg == '--release-1':
                    # Build core wheels and sdist.
                    # [pymupdf4llm is pure python so doesn't need to be
                    # mentioned in other --release-* options.]
                    new_args += f' --sdists -b {b_mupdf}pymupdf,pymupdfpro,pymupdf_layout,pymupdf4llm,pdf4llm'
                
                elif arg == '--release-2':
                    # Build macos-intel and linux-arm wheels.
                    new_args += f' -b {b_mupdf}pymupdf,pymupdfpro,pymupdf_layout,pymupdf4llm,pdf4llm --remote-github-runners macos-intel,linux-arm'
                
                elif arg == '--release-3':
                    # Build for win-x32.
                    new_args += f' -b {b_mupdf}pymupdf --remote-github-runners windows -e CIBW_ARCHS_WINDOWS=x86 --cibw-skip-add-defaults=0'
                
                elif arg == '--release-4':
                    # Build for linux-musllinux.
                    new_args += f' -b {b_mupdf}pymupdf --remote-github-runners linux -e "CIBW_BUILD=cp310-musllinux_x86_64" --cibw-skip-add-defaults=0'
                
                elif arg == '--release-5':
                    # Build for Pyodide.
                    new_args += f' -b {b_mupdf}pymupdf --cibw-pyodide --remote-github-runners linux'
                
                elif arg == '--release-6':
                    # Build for cp314t.
                    #
                    # We use PYMUPDF_SETUP_PY_LIMITED_API=0 because
                    # py_limited_api and Py_GIL_DISABLED are not supported
                    # together as of 2026-02-20, e.g. see PEP 803 and PEP 809.
                    #
                    new_args += f' -b {b_mupdf}pymupdf --remote-github-runners linux --cibw-skip-add-defaults=0 -e CIBW_BUILD="cp314t*" -e CIBW_SKIP="*musllinux*" -e PYMUPDF_SETUP_PY_LIMITED_API=0'
                
                else:
                    Assert(0, f'Unrecognised {arg=}.')
                
                new_args = shlex.split(new_args)
                args.args_eq.replace(arg.pos, args.pos, new_args)
                continue
            
            elif arg == '--remote-do':
                state.remote_do = args.get_bool()

            elif arg == '--remote-github-runners':
                _deltas = next(args).as_text()
                _deltas = _deltas.split(',') if _deltas else list()
                apply_deltas(state.remote_github_runners, _deltas, aliasfn=gh_runner_alias)

            elif arg == '--remote-github-workflow-id':
                state.remote_github_workflow_id = next(args).as_text()

            elif arg == '--remote-github-yml':
                _yml = next(args)
                state.remote_github_yml = _yml.as_text()
                Assert(
                        state.remote_github_yml.endswith('.yml'),
                        f'remote_github_yml={state.remote_github_yml} must end with .yml',
                        )

            elif arg == '--remote-github-yml-inputs':
                state.remote_github_yml_inputs = next(args).as_text()

            elif arg == '--remote-prefix':
                state.remote_prefix = next(args).as_text()

            elif arg == '--remote-prefix-default':
                remote = next(args).as_text()
                prefix = next(args).as_text()
                state.remote_prefix_default[remote] = prefix

            elif arg == '--remote-rsync-path':
                state.remote_rsync_path = next(args).as_text()

            elif arg == '--remote-rsync-wsl':
                state.remote_rsync_wsl = args.get_bool()

            elif arg == '--run':
                package = next(args)
                command = next(args)
                state.run_commands.append((package.as_text(), command.as_text()))

            elif arg == '--sdists':
                state.sdists = args.get_bool()

            elif arg == '--set-swig':
                state.swig = next(args).as_text()
                #pipcl.log(f'{state.swig=}')

            elif arg == '--set-swig-quick':
                state.swig_quick = args.get_bool()

            elif arg == '--system-packages':
                state.system_packages = int(next(args))

            elif arg == '--system-site-packages':
                state.system_site_packages = args.get_bool()

            elif arg == '-t':
                _names = next(args).as_text()
                _names = _names.split(',') if _names else list()
                apply_deltas(state.packages_test, _names, aliasfn=package_alias)

            elif arg == '--tee-auto':
                tee_auto = args.get_bool()
                # Ignore if we are being run by an outer aptest or by bash completion.
                if APTEST_NESTED or COMP_LINE:
                    pass
                elif tee_auto:
                    state.tee_auto = tee_auto
                    global g_log_tee
                    if state.tee_auto:
                        g_log_tee = f'aptest-out-{g_date_time}'
                        pipcl.log_tee(g_log_tee, 'aptest-out')
                else:
                    g_log_tee = None
                    pipcl.log_tee(None)

            elif arg == '--tee-path':
                pos = args.pos
                path = next(args).as_text()
                #args.args_eq.set(pos, '')
                # Ignore if we are being rerun by an outer aptest or by bash completion.
                if path and not APTEST_NESTED and not COMP_LINE:
                    state.tee_path = path
                    pipcl.log_tee(state.tee_path)

            elif arg == '--test-extra-packages':
                state.test_extra_packages += next(args).as_text().split(',')
            
            elif arg == '--test-gnn-cache':
                state.test_gnn_cache = args.get_bool()
            
            elif arg == '--test-gnn-det':
                test_gnn_det = next(args)
                Assert(
                        test_gnn_det in (
                            'eval/eval_gnn.py',
                            'eval/eval_oracle_gnn.py',
                            'eval/eval_pymupdf4llm.py',
                            'eval/eval_pymupdf_layout.py',
                            ),
                        f'Unrecognised {test_gnn_det=}',
                        )
                state.test_gnn_det = test_gnn_det.as_str()
                
            elif arg == '--test-gnn-extra':
                nv = next(args).as_text()
                n, v = nv.split('=', 1)
                state.test_gnn_extra[n] = v

            elif arg == '--test-gnn-limit':
                state.test_gnn_limit = next(args).as_int()

            elif arg == '--test-gnn-out':
                state.test_gnn_out = next(args).as_text()

            elif arg == '--test-gnn-push':
                state.test_gnn_push = args.get_bool()
            
            elif arg == '--ticker':
                _ticker = next(args).as_float()
                if not APTEST_NESTED and GITHUB_ACTIONS != 'true':
                    state.ticker = _ticker

            elif arg == '-u':
                state.github_upload = args.get_bool()
            
            elif arg == '--use-release-args':
                Assert(state.packages_for_release, f'No release package locations specified - use upper-case specifications such as `-P git:`.')
                Assert(state.wheelhouse_release, f'No release wheelhouse specified, use `--wheelhouse-release <directory-name>`.')
                Assert(state.wheelhouse_release != state.wheelhouse, f'{state.wheelhouse_release=} is not different from {state.wheelhouse=}.')
                state.wheelhouse = state.wheelhouse_release
                # We never clean the release wheelhouse.
                state.clean_wheelhouse = False
                for package, location in state.packages_for_release.items():
                    add_package(state, package, location)

            elif arg == '-v':
                _venv = next(args)
                Assert(_venv in ('0', '1', '2', '3'), f'Invalid venv={_venv.text}.')
                state.venv = _venv.as_int()
            
            elif arg == '--venv-name':
                state.venv_name = next(args).as_text()
            
            elif arg == '-V':
                state.verbose = next(args).as_int()
                Assert(state.verbose in (0, 1), f'Verbose level should be 0 or 1')
            
            elif arg == '--wheelhouse':
                state.wheelhouse = next(args).as_str()

            elif arg == '--wheelhouse-release':
                state.wheelhouse_release = next(args).as_str()

            elif arg in (
                    'build',
                    'cibw',
                    'docs',
                    'draft',
                    'gnn-download',
                    'gnn-show',
                    'gnn-select-show',
                    'gnn-train',
                    'run',
                    'populate',
                    'test',
                    'test-gnn',
                    'upload',
                    'windows-show-vs-instances',
                    ):
                state.commands.append(arg.as_str())

            else:
                if arg.text is StopIteration:
                    break
                Assert(0, f'Unrecognised argument: {arg.text!r}.')

    finally:
        # cli.Args.final() will handle writing out completions if COMP_LINE is
        # set, or writing out diagnostics if parsing the command line failed.
        args.final(regions)
    #pipcl.log(f'{args.args_eq.argv=}')
    
    return args, state


def _get_key(state, url, on_error=None):
    '''
    Finds key for specified url or git remote.
    
    Returns (<path>, <env>), where:
    * <path> is None or path of file containing key.
    * <env> is None or name of environment variable containing key.
    '''
    ret_path = None
    ret_env = None
    if url:
        for prefix, path, env, _pos in state.keys:
            if url.startswith(prefix):
                pipcl.log(f'{url=}: {path=} {env=}')
                pipcl.log(f'{os.path.exists(path)=}')
                pipcl.log(f'{env and env in os.environ=}')
                if path and os.path.exists(path):
                    ret_path = path
                if env and env in os.environ:
                    ret_env = env
                if ret_path or ret_env:
                    break
    pipcl.log(f'_get_key(): {url=} returning {ret_path=} {ret_env=}.')
    if (ret_path, ret_env) == (None, None):
        if on_error == 'raise':
            raise Exception(f'Failed to find key for {url=}.')
    return ret_path, ret_env


def _get_key2(state, url, on_error=None):
    '''
    Wrapper for _get_key(), returning the key itself from contents of path or
    env.
    '''
    key_path, key_env = _get_key(state, url, on_error)
    ret = None
    if key_path:
        ret = pipcl.fs_read(key_path)
    elif key_env:
        ret = os.environ[key_env]
    pipcl.log(f'Returning {url=} => {ret=}.')
    return ret


def _get_key_github_rest(state, on_error='raise'):
    return _get_key2(state, 'https://api.github.com/', on_error).strip()


def _get_key_pypi(state, on_error='raise'):
    return _get_key2(state, 'https://upload.pypi.org/', on_error).strip()


def github_api_url(info):
    git_remote = info['git_remote']
    m = re.match('^git@github.com:(.+).git$', git_remote)
    Assert(m, f'Unrecognised remote: {git_remote=}')
    name = m.group(1)
    return f'https://api.github.com/repos/{name}'


def do_remote_github(state, args):
    assert isinstance(args, cli.Args)
    pipcl.run('pip install requests')
    pipcl.run(f'pip install --upgrade piprepo "setuptools<81"')
    pipcl.run('pip install piprepo')
    if platform.system() == 'Windows':
        branch = f'aptest-{os.environ["USERNAME"]}'
    else:
        branch = f'aptest-{os.environ["USER"]}'    # -{g_date_time}'
    pipcl.log(f'{branch=}.')
    
    token_github_rest = _get_key_github_rest(state)

    if state.remote_github_workflow_id:
        # Wait for existing workflow instead of creating a new one.
        workflow_id = state.remote_github_workflow_id
        remote_github_workflow_package = 'aptest'
        info = name_info(state, remote_github_workflow_package)
    else:
        # Push ourselves to Git.
        git_push(g_root, 'git@github.com:ArtifexSoftware/aptest.git', branch, state, doit=state.remote_do)

        # Push specified local packages to Github and update args to point to
        # new location.
        for package_name, (package_location, args_pos) in list(state.packages.items()) + list(state.packages2.items()):
            if not package_location.startswith(('git:', 'pip:')):
                # Push to a Github branch and update argv[] to refer to this
                # Github branch.
                info = name_info(state, package_name)
                pipcl.log(f'{package_name=}.')
                pipcl.log(f'{info["git_remote"]=}.')
                git_push(package_location, info["git_remote"], branch, state, doit=state.remote_do)
                args.args_eq.set(args_pos, f'git:-b {branch} {info["git_remote"]}')

        if state.remote_github_yml:
            # Run specific .yml directly.
            pipcl.log(f'Running .yml instead of aptest.py: {state.remote_github_yml}')
            if not state.packages:
                # Run on aptest.
                info = name_info(state, 'aptest')
            elif len(state.packages) == 1:
                for package_name, (package_location, args_pos) in state.packages.items():
                    pass
                info = name_info(state, package_name)
            else:
                Assert(0, 'Running yml directly requires exactly zero or one package, but {len(state.packages)=}.')
            data = dict()
            data['ref'] = branch
            if state.remote_github_yml_inputs:
                inputs = dict()
                for nv in state.remote_github_yml_inputs.split(','):
                    try:
                        n, v = nv.split('=', 1)
                    except Exception as e:
                        raise Exception(f'Expected <name>=<value> in {nv!r} from {state.remote_github_yml_inputs=}.') from e
                    inputs[n] = v
                data['inputs'] = inputs
            workflow_id = github.gh_run_workflow(
                    token_github_rest,
                    github_api_url(info),
                    state.remote_github_yml,
                    data,
                    doit=state.remote_do,
                    )
        else:
            # Run ourselves on Github using test.yml, passing argv.
            info = name_info(state, 'aptest')
            args_string = shlex.join(args.args_eq.argv[1:])
            # Force a fixed wheelhouse so we can download artifacts easily.
            args_string += ' --wheelhouse aptest-wheelhouse'
            # We define the .yml's `matrix: os: ...` by passing in a dict encoded with json, as
            # expected by test.yml's workflow_dispatch:inputs:matrix
            Assert(state.remote_github_runners, f'No Github runners specified.')
            matrix = {
                    'os': state.remote_github_runners,
                    }
            matrix_json = json.dumps(matrix)
            data = dict(
                    ref = branch,
                    inputs = dict(
                            args=args_string,
                            matrix=matrix_json),
                            
                    )
            pipcl.log(f'args_string is:')
            args_string_lines = '\n-'.join(args_string.split(' -'))
            pipcl.log(textwrap.indent(args_string_lines, '    '))
            yml = 'test.yml'
            key = _get_key_github_rest(state)
            workflow_id = github.gh_run_workflow(
                    key,
                    github_api_url(info),
                    yml,
                    data,
                    doit=state.remote_do,
                    )
            
    if state.remote_do:
        assert isinstance(workflow_id, str)
        url = github_api_url(info)
        upload = 'pypi' if state.github_upload else None
        pipcl.log(f'Calling github.gh_workflow_download_multiple() with {url=} {workflow_id=} {upload=}.')
        github.gh_workflow_download_multiple(
                token_github_rest,
                url,
                workflow_id,
                #extra_wheels=upload_extra_wheels,
                upload=upload,
                token_pypi=_get_key_pypi(state) if upload else None,
                local_dir_union=state.wheelhouse,
                )
        pipcl.run(
                f'piprepo build {state.wheelhouse}',
                prefix='piprepo build: ',
                )

def do_remote(state, argv):
    remote = state.remote
    remote_dir = state.remote_dir
    verbose = 0
    jumps = None
    if ' ' not in remote:
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
    elif ' ' in remote:
        ssh_command = remote
        remote = None
        label = ssh_command
    else:
        ssh_command = 'ssh'
        label = remote
    pipcl.log(f'{ssh_command=}')

    if state.remote_do:
        git_paths = list()

        def sync2(path):
            return sync(
                    remote,
                    remote_dir,
                    path,
                    ssh_command=ssh_command,
                    verbose=verbose,
                    state=state,
                    )

        # Sync each package.
        all_packages = list(state.packages.items()) + list(state.packages2.items())
        for _package_name, (package_location, _args_pos) in all_packages:
            if not package_location.startswith(('git:', 'pip:')):
                pipcl.log(f'{remote=} {remote_dir=} {package_location=} {ssh_command=}')
                if sync2(package_location):
                    git_paths.append(package_location)

        # Sync aptest itself.
        if sync2(g_root):
            git_paths.append(g_root)

        # Sync keys.
        for _prefix, path, _env, _pos in state.keys:
            if path and os.path.exists(path):
                sync2(path)

        # Run remote command.
        #
        remote_command = f'cd {remote_dir} && '
        for git_path in git_paths:
            # We exclude *.tar.gz to avoid pymupdf re-downloading mupdf .tar.gz file.
            remote_command += f'(cd {git_path} && git clean -e "*.tar.gz" -f) && '
        remote_command += f'APTEST_NESTED=1 '
        if state.remote_prefix:
            remote_command += f'{state.remote_prefix} '
        elif (remote_prefix_default := state.remote_prefix_default.get(state.remote)) is not None:
            #pipcl.log(f'Using {remote_prefix_default=}')
            remote_command += f'{remote_prefix_default} '
        elif remote and 'windows' in remote:
            remote_command += f'py '
        remote_command += f'{os.path.basename(g_root_abs)}/aptest.py {shlex.join(argv[1:])}'

        command = f'{ssh_command} {remote if remote else ""} {shlex.quote(remote_command)}'
        pipcl.log(f'{command=}')
        pipcl.log(f'{ssh_command=}')

        if state.tee_auto:
            def make_tee_out_remote():
                from_ = f'aptest-out-{remote}'
                to_ = g_log_tee
                #pipcl.log(f'Creating symlink {from_} => {to_}.')
                pipcl.fs_symlink(from_, to_)
            atexit.register(make_tee_out_remote)
        
        pipcl.run(
                command,
                prefix=f'{label}: ',
                out='log',
                #tee=tee,
                ticker=state.ticker,
                )

    if 1:
        # Copy remote wheels back to local machine.
        filters = list()
        for package in state.packages_build:
            filters.append(f'--include={package}-*.whl')
            filters.append(f'--include={package}-*.tar.gz')
            filters.append(f'--include={package}-*.xml')
        filters.append('--exclude=*')
        sync_reverse(
                remote,
                remote_dir,
                f'{state.wheelhouse}/',
                f'{state.wheelhouse}/',
                ssh_command=ssh_command,
                state=state,
                filters=filters,
                )
    if 1:
        # Copy test-gnn-results/ back to local machine. Macmini's rsync appears
        # too old for `--ignore-missing-args` so we ignore any error.
        e = sync_reverse(
                remote,
                remote_dir,
                'test-gnn-results/',
                'test-gnn-results/',
                ssh_command=ssh_command,
                state=state,
                extra='--ignore-missing-args',
                check=0,
                )
        if e:
            pipcl.log(f'[Ignoring failure of reverse rsync of test-gnn-results/: {e=}.]')


def build_sdist(state, package, directory):
    '''
    Build sdist if <package> is allowed to have a sdist.
    '''
    if package in (
            'pdf2docx',
            'pdf4llm',
            'pymupdf',
            'pymupdf4llm',
            'pipcl',
            ):
        # pymupdf4llm's setup.py requires `-d` is after `sdist`.
        pipcl.run(
                f'cd {directory} && python setup.py sdist -d {os.path.abspath(state.wheelhouse)}',
                prefix=f'sdist {package}: ',
                )


def _modify_build_env(state, package):
    '''
    Set state.env_extra PYMUPDFPRO_SETUP_SOT_KEY_PATH /
    PYMUPDFPRO_SETUP_SOT_KEY if required.
    '''
    if (package == 'pymupdfpro'
            and 'smartoffice' not in state.packages
            and 'smartoffice-neo' not in state.packages
            and 'smartoffice-marina' not in state.packages
            ):
        # Pro's setup.py needs PYMUPDFPRO_SETUP_SOT_KEY or
        # PYMUPDFPRO_SETUP_SOT_KEY_PATH to be set in order to clone
        # smartoffice.
        #
        # This will need to be changed if/when we change pro to use
        # smartoffice-marina by default.
        #
        if 'smartoffice-marina' in state.packages:
            key_path, key_env = _get_key(state, 'git@github.com:', on_error='raise')
        else:
            key_path, key_env = _get_key(state, 'git@gitlab.artifex.com:', on_error='raise')
        
        if key_path:
            state.env_extra['PYMUPDFPRO_SETUP_SOT_KEY_PATH'] = os.path.abspath(key_path)
        elif key_env:
            state.env_extra['PYMUPDFPRO_SETUP_SOT_KEY'] = os.environ[key_env]


def _4llm_new_layout(directory):
    '''
    Returns true if pymupdf4llm checkout <directory> has new layout from 2026-3, with
    top-level setup.py.
    '''
    return os.path.exists(f'{directory}/setup.py')


def do_build_single(state, package):
    '''
    Build and install <package>.
    '''
    
    # We use `pip --extra-index-url {pip_index_url}` so that pip
    # finds prerequisite wheels in state.wheelhouse.
    pip_index_url = f'file://{os.path.abspath(state.wheelhouse)}/simple'
    
    # pip fails if pip_index_url contains back-slashes, with
    # `ERROR: Could not install packages due to an OSError: [Errno
    # 13] Permission denied:...`.
    pip_index_url = pip_index_url.replace('\\', '/')
    
    ret_wheel = None
    location, _args_pos = state.packages[package]
    if not location:
        return ret_wheel
    if package == 'aptest':
        return ret_wheel
    pip_wheel_no_clean = ' --no-clean' if state.build_pip_no_clean else ''

    new_files = pipcl.NewFiles(f'{state.wheelhouse}/{package}*.whl')

    if location.startswith('pip:'):
        Assert(package != 'mupdf', f'Not a package on pypi.org: {package}')
        name = location[4:]
        if not name.endswith(('.whl', '.tar.gz')):
            name = f'{package}{name}'
        # Get wheel from pypi.org and put into our wheelhouse
        # so it is available for later builds. Then install;
        # pip uses a cache so will not download twice.
        #
        # We need to know the name of the wheel file (we return it). This
        # is calculated using pipcl.NewFiles so we need to force download
        # so wheel file is new. We do this by first removing matching
        # wheels from pip cache and wheelhouse.
        #
        pipcl.run(f'pip cache list')
        pipcl.run(f'pip cache remove {name}')
        pipcl.run(f'pip cache list')
        for p in glob.glob(f'{state.wheelhouse}/{package}-*.whl'):
            pipcl.log(f'Removing: {p}')
            pipcl.fs_remove(p)
        pipcl.run(f'pip wheel{pip_wheel_no_clean} --no-cache-dir -w {state.wheelhouse} {name}')
        ret_wheel = new_files.get_one()
        pipcl.run(f'pip uninstall -y {name}')
        pipcl.run(f'pip install -v {name}')
    else:
        directory = _get_local(package, state)

        if package == 'pymupdf4llm' and not _4llm_new_layout(directory):
            # setup.py is in subdirectory pymupdf4llm/.
            directory += '/pymupdf4llm'
        elif package == 'pdf4llm':
            # setup.py is in subdirectory.
            directory += '/pdf4llm'
        directory_abs = os.path.abspath(directory)
        pipcl.log(f'{package=} {directory=}')
        if package == 'mupdf':
            state.env_extra['PYMUPDF_SETUP_MUPDF_BUILD'] = directory_abs
            # fixme: be able to set to '' for system install?
        elif package.startswith('smartoffice'):
            # We don't build smartoffice here, instead we tell pymupdfpro
            # where the local smartoffice checkout is.
            state.env_extra['PYMUPDFPRO_SETUP_SOT'] = directory_abs
            #if package == 'smartoffice-marina':
            #    state.env_extra['PYMUPDFPRO_SOT_MARINA'] = '1'
        elif package == 'swig':
            swig_env_extra = dict()
            pipcl.swig_prepare_build(swig_env_extra)
            pipcl.run(
                    f'cd {directory} && ./autogen.sh --prefix install',
                    env_extra=swig_env_extra,
                    prefix='{directory} autogen.sh: ',
                    )
            pipcl.run(
                    f'cd {directory} && mkdir -p build/build && cd build/build && ../../configure',
                    env_extra=swig_env_extra,
                    prefix='{directory} configure: ',
                    )
            pipcl.run(
                    f'cd {directory}/build/build && make',
                    env_extra=swig_env_extra,
                    prefix='{directory} make: ',
                    )
        else:
            if package:
                pipcl.run(f'pip uninstall -y {package}')

            if state.sdists:
                build_sdist(state, package, directory)

            if (package == 'pymupdf'
                    and state.graal
                    and (
                        'pymupdfpro' in state.packages_build
                        or 'pymupdf_layout' in state.packages_build
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
            
            _modify_build_env(state, package)

            if state.build_type:
                if package == 'pymupdf':
                    state.env_extra['PYMUPDF_SETUP_MUPDF_BUILD_TYPE'] = state.build_type
                if package == 'pymupdfpro':
                    state.env_extra['PYMUPDFPRO_SETUP_BUILD_TYPE'] = state.build_type
                if package == 'pymupdf_layout':
                    state.env_extra['PYMUPDF_LAYOUT_SETUP_BUILD_TYPE'] = state.build_type
            
            pipcl.run(
                    f'pip wheel{pip_wheel_no_clean} -v --extra-index-url {pip_index_url} -w {state.wheelhouse} {directory_abs}',
                    env_extra=state.env_extra,
                    prefix=f'build {package}: ',
                    )
            ret_wheel = new_files.get_one()

            pipcl.run(
                    f'pip install -v --extra-index-url {pip_index_url} {ret_wheel}',
                    env_extra=state.env_extra,
                    prefix=f'install {package}: ',
                    )

    if 0 and package == 'pymupdf':  # pylint: disable=condition-evals-to-constant
        # Set PYMUPDF_SETUP_VERSION so subsequent builds are configured
        # for the PyMuPDF we have just built.
        PYMUPDF_SETUP_VERSION = importlib.metadata.version('pymupdf')
        state.env_extra['PYMUPDF_SETUP_VERSION'] = PYMUPDF_SETUP_VERSION
        pipcl.log(f'### Have set {PYMUPDF_SETUP_VERSION=}')

    return ret_wheel


def set_pseudo_package_env(state):
    '''
    Set state.env_extra[] to force build of specified pseudo packages.
    '''
    if 'mupdf' in state.packages:
        directory = _get_local('mupdf', state)
        if directory:
            state.env_extra['PYMUPDF_SETUP_MUPDF_BUILD'] = os.path.abspath(directory)
    
    if 'mupdf' in state.packages and 'mupdf' not in state.packages_build:
        PYMUPDF_SETUP_MUPDF_REBUILD = '0'
        pipcl.log(f'Setting {PYMUPDF_SETUP_MUPDF_REBUILD=}')
        state.env_extra['PYMUPDF_SETUP_MUPDF_REBUILD'] = PYMUPDF_SETUP_MUPDF_REBUILD
    
    for p in state.packages:
        if p.startswith('smartoffice'):
            directory = _get_local(p, state)
            if directory:
                PYMUPDFPRO_SETUP_SOT = os.path.abspath(directory)
                pipcl.log(f'Setting {PYMUPDFPRO_SETUP_SOT=}')
                state.env_extra['PYMUPDFPRO_SETUP_SOT'] = PYMUPDFPRO_SETUP_SOT
            if p not in state.packages_build:
                PYMUPDFPRO_SETUP_SOT_BUILD = '0'
                pipcl.log(f'Setting {PYMUPDFPRO_SETUP_SOT_BUILD=}')
                state.env_extra['PYMUPDFPRO_SETUP_SOT_BUILD'] = PYMUPDFPRO_SETUP_SOT_BUILD
        if p == 'smartoffice-marina':
            state.env_extra['PYMUPDFPRO_SOT_MARINA'] = '1'


def do_build(state):
    
    set_pseudo_package_env(state)
    
    package_to_wheel = dict()
    
    # We install packages in reverse order (e.g. pymupdf_layout before pymupdf)
    # so that packages specified to aptest override any package prerequisites.
    #
    # For example with `-p pip:==1.26.3 --layout pip:=1.26.5`, installation of
    # pymupdf_layout will install prerequisite pymupdf-1.26.5, which we then
    # override with installation of pymupdf-1.26.3.
    #
    
    for package in state.packages_build:
        wheel = do_build_single(state, package)
        package_to_wheel[package] = wheel
        pipcl.run(
                f'piprepo build {state.wheelhouse}',
                prefix='piprepo build: ',
                )
    
    for package in reversed(state.packages_build):
        # Always uninstall first, to ensure we always install the package from
        # the specified location.
        #
        pipcl.run(f'pip uninstall -y {package}')
        wheel = package_to_wheel[package]
        pipcl.run(f'pip install {wheel}')


def do_cibw(state):
    '''
    Build wheels for each package with cibuildwheel, adding to wheelhouse,
    and using piprepo to update a local pypi-style tree.
    '''
    pipcl.run(
            f'pip install --upgrade --force-reinstall {state.cibw_name}',
            prefix=f'pip install {state.cibw_name}: ',
            )
    pipcl.run(f'pip install --upgrade pytest')
    if state.pytest_timeout:
        pipcl.run(f'pip install --upgrade pytest-timeout')

    set_pseudo_package_env(state)
    
    # Some general flags.
    if 'CIBW_BUILD_VERBOSITY' not in state.env_extra:
        state.env_extra['CIBW_BUILD_VERBOSITY'] = '1'

    # Add default flags to CIBW_SKIP.
    # 2025-10-07: `cp3??t-*` excludes free-threading.

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
    
    # Tell cibuildwheel not to use `auditwheel` on Windows. As of 2026-06-10
    # cibuildwheel uses delvewheel which complains that it cannot find
    # mupdfcpp64.dll.
    state.env_extra['CIBW_REPAIR_WHEEL_COMMAND_WINDOWS'] = ''

    # Specify python versions.
    CIBW_BUILD = state.env_extra.get('CIBW_BUILD')
    pipcl.log(f'{CIBW_BUILD=}')
    
    if CIBW_BUILD == 'all':
        CIBW_BUILD = cibw_cp(*python_versions_minor)
    elif CIBW_BUILD is None:
        if state.graal:
            CIBW_BUILD = 'gp*'
            state.env_extra['CIBW_ENABLE'] = 'graalpy'
        elif state.cibw_pyodide:
            # Using python-3.13 fixes problems with MuPDF's setjmp/longjmp.
            CIBW_BUILD = 'cp313*'
        elif GITHUB_ACTIONS == 'true':
            # Build/test all supported Python versions.
            CIBW_BUILD = cibw_cp(*python_versions_minor)
            if platform.system() == 'Windows':
                # 2026-02-06: cibuildwheel appears to fail on windows with python-3.14 when testing pymupdfpro.
                # It looks like pip fails to find pymupdf wheel in our piprepo wheelhouse.
                #
                # cibw pymupdfpro: + pip install 'D:\a\aptest\aptest\aptest-wheelhouse\pymupdfpro-1.27.1-cp310-abi3-win_amd64.whl'
                # cibw pymupdfpro: Looking in indexes: https://pypi.org/simple, file://D:/a/aptest/aptest/aptest-wheelhouse/simple
                # cibw pymupdfpro: Processing d:\a\aptest\aptest\aptest-wheelhouse\pymupdfpro-1.27.1-cp310-abi3-win_amd64.whl
                # cibw pymupdfpro: WARNING: Location 'file://D:/a/aptest/aptest/aptest-wheelhouse/simple/pymupdf/' is ignored: it is neither a file nor a directory.
                # cibw pymupdfpro: INFO: pip is looking at multiple versions of pymupdfpro to determine which version is compatible with other requirements. This could take a while.
                # cibw pymupdfpro: ERROR: Ignored the following yanked versions: 1.18.11
                # cibw pymupdfpro: ERROR: Could not find a version that satisfies the requirement PyMuPDF==1.27.1 (from pymupdfpro) (from versions: 1.11.2, 1.12.5, 1.13.20, 1.14.19.post2, 1.14.20, 1.14.21, 1.16.0, 1.16.1, 1.16.2, 1.16.3, 1.16.4, 1.16.5, 1.16.6, 1.16.7, 1.16.8, 1.16.9, 1.16.10, 1.16.11, 1.16.12, 1.16.13, 1.16.14, 1.16.15, 1.16.16, 1.16.17, 1.16.18, 1.17.0, 1.17.1, 1.17.2, 1.17.3, 1.17.4, 1.17.5, 1.17.6, 1.17.7, 1.18.0, 1.18.1, 1.18.2, 1.18.3, 1.18.4, 1.18.5, 1.18.6, 1.18.7, 1.18.8, 1.18.9, 1.18.10, 1.18.12, 1.18.13, 1.18.14, 1.18.15, 1.18.16, 1.18.17, 1.18.18, 1.18.19, 1.19.0, 1.19.1, 1.19.2, 1.19.3, 1.19.4, 1.19.5, 1.19.6, 1.20.0, 1.20.1, 1.20.2, 1.21.0, 1.21.1, 1.22.0, 1.22.1, 1.22.2, 1.22.3, 1.22.5, 1.23.0rc1, 1.23.0rc2, 1.23.0, 1.23.1, 1.23.2rc1, 1.23.2, 1.23.3, 1.23.4, 1.23.5, 1.23.6, 1.23.7, 1.23.8, 1.23.9rc1, 1.23.9rc2, 1.23.9, 1.23.10, 1.23.11, 1.23.12, 1.23.13, 1.23.14, 1.23.15, 1.23.16, 1.23.18, 1.23.19, 1.23.20, 1.23.21, 1.23.22, 1.23.23, 1.23.24, 1.23.25, 1.23.26, 1.24.0, 1.24.1, 1.24.2, 1.24.3, 1.24.4, 1.24.5, 1.24.6, 1.24.7, 1.24.8, 1.24.9, 1.24.10, 1.24.11, 1.24.12, 1.24.13, 1.24.14, 1.25.0, 1.25.1, 1.25.2, 1.25.3, 1.25.4, 1.25.5, 1.26.0, 1.26.1, 1.26.3, 1.26.4, 1.26.5, 1.26.6, 1.26.7)
                # cibw pymupdfpro: ERROR: No matching distribution found for PyMuPDF==1.27.1
                #
                # cibuildwheel seems to force use of pip==25.3.
                #
                CIBW_BUILD = CIBW_BUILD.replace(' cp314*', '')
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

    for package in state.packages_build:    # pylint: disable=too-many-nested-blocks
        pipcl.log(f'{package=}')
        directory = _get_local(package, state)
        
        if not directory:
            # location is pip.
            pipcl.log(f'Unable to process with cibuildwheel because location is pip: {package=} and no second location')
            continue
            
            # Experimental code to try to get cibw to test an existing wheel.
            #directory = _get_local(package, state, test=1)
            #if not directory:
            #    pipcl.log(f'Unable to process with cibuildwheel because location is pip: {package=} and now second location')
            #    continue
            #
            #location, _args_pos = state.packages[package]
            #assert location.startswith('pip:')
            #if location.endswith(('.whl', '.tar.gz')):
            #    pipcl.log(f'Unable to process with cibuildwheel because location is pip: .whl/.tar.gz. {package=} {location=}')
            #    continue
            #name = f'{package}{location[4:]}'
            #state.env_extra['CIBW_BUILD_FRONTEND'] = f'pip wheel {name}'
        
        if package == 'pymupdf4llm' and not _4llm_new_layout(directory):
            # setup.py is in subdirectory pymupdf4llm/.
            directory += '/pymupdf4llm'
        elif package == 'pdf4llm':
            directory += '/pdf4llm'
        
        pipcl.log(f'{package} _get_local() => {directory=}')
        directory_abs = os.path.abspath(directory)
        
        if package == 'mupdf':
            if platform.system() == 'Linux' and not state.cibw_pyodide:
                # Need /host/ prefix so accessible from within manylinux docker.
                state.env_extra['PYMUPDF_SETUP_MUPDF_BUILD'] = f'/host{directory_abs}'
            else:
                state.env_extra['PYMUPDF_SETUP_MUPDF_BUILD'] = directory_abs
            # fixme: be able to set to '' for system install?
            continue
        
        if package.startswith('smartoffice'):
            if platform.system() == 'Linux' and not state.cibw_pyodide:
                # Need /host/ prefix so accessible from within manylinux docker.
                state.env_extra['PYMUPDFPRO_SETUP_SOT'] = f'/host{directory_abs}'
                
                # This doesn't work:
                #
                # 2026-03-20: attempt to workaround failure on github when building pro:
                # test_4158(): PYMUPDFPRO_SETUP_SOT='/host/home/runner/work/aptest/aptest/aptest-git-smartoffice'
                # ../../../project/tests/test_simple.py:348:test_4158(): Running: env_extra=None cd /host/home/runner/work/aptest/aptest/aptest-git-smartoffice && git show -s --format=%cI HEAD
                # fatal: detected dubious ownership in repository at '/host/home/runner/work/aptest/aptest/aptest-git-smartoffice'
                # To add an exception for this directory, call:
                # git config --global --add safe.directory /host/home/runner/work/aptest/aptest/aptest-git-smartoffice
                #
                #
                # Maybe we need to run it inside docker? Or in the test itself?
                #
                pipcl.run(f'git config --global --add safe.directory {directory_abs}', check=0)
            else:
                state.env_extra['PYMUPDFPRO_SETUP_SOT'] = directory_abs
            
            if package == 'smartoffice-marina':
                state.env_extra['PYMUPDFPRO_SOT_MARINA'] = '1'
                
            if 0 and platform.system() == 'Linux' and package == 'smartoffice-marina':
                # Building with cmake in a manylinux docker can go wrong if we've previously built marina
                # outside of manylinux, because the CMakeCache.txt will contains the non-manylinux paths, leading to:
                #
                #   CMake Error: The current CMakeCache.txt directory
                #   /host/home/.../epage/cmake-build/lib/CMakeCache.txt
                #   is different than the directory
                #   /home/.../epage/cmake-build/lib where CMakeCache.txt was
                #   created. This may result in binaries being created in the
                #   wrong place. If you are not sure, reedit the CMakeCache.txt
                #
                pipcl.fs_remove(f'{directory_abs}/epage/cmake-build/lib/CMakeCache.txt')
            
            continue
        
        if state.sdists and platform.system() == 'Linux':
            pipcl.log(f'Calling build_sdist() {package=} {directory=}.')
            build_sdist(state, package, directory)

        python_version_tuple = (
                int(platform.python_version_tuple()[0]),
                int(platform.python_version_tuple()[1]),
                )
        
        # As of 2026-03-23, no onnxruntime wheel is available for macos-intel
        # python-3.14. For python<=3.13, wheels for older releases are
        # available.
        if (1
                and python_version_tuple == (3, 14)
                and package in ('pdf4llm', 'pymupdf4llm')
                and platform.system() == 'Darwin'
                and platform.machine() == 'x86_64'
                ):
            pipcl.log(f'Not doing build/test on macos/intel/python-3.14 because onnxruntime not available: {package=}')
        
        elif package in ('pdf2docx', 'pdf4llm', 'pymupdf4llm', 'pipcl'):
            # Build/test directly.
            pipcl.log(f'Not using cibuildwheel for {package=} because cibuildwheel does not support pure python wheels.')
            new_files = pipcl.NewFiles(f'{state.wheelhouse}/*.whl')
            do_build_single(state, package)
            failed_packages = list()
            do_test_single(state, package, failed_packages)
            
            # Delete any new prerequisite wheels that are not for <package>, so
            # we behave like cibuildwheel.
            new_wheels = new_files.get()
            for wheel_path in new_wheels:
                assert wheel_path.endswith('.whl')
                if not os.path.basename(wheel_path).startswith(f'{package}-'):
                    pipcl.log(f'Deleting {wheel_path=}.')
                    pipcl.fs_remove(wheel_path)
            
            if failed_packages:
                raise Exception(f'Test failed for {package=}.')
        
        else:
            # Run cibuildwheeel.
            
            _modify_build_env(state, package)
            
            # Tell cibuildwheel how to test <package>.
            if package in state.packages_test:
                CIBW_TEST_COMMAND = f'pip install --upgrade pytest'
                if state.pytest_timeout:
                    CIBW_TEST_COMMAND += f' && pip install --upgrade pytest-timeout'
                CIBW_TEST_COMMAND += f' && pytest'
                if state.pytest_timeout:
                    CIBW_TEST_COMMAND += f' --timeout {state.pytest_timeout}'
                if state.pytest_timeout_method:
                    CIBW_TEST_COMMAND += f' --timeout-method {state.pytest_timeout_method}'
                if state.pytest_junit_xml:
                    CIBW_TEST_COMMAND += f' --junit-xml={os.path.abspath(state.wheelhouse)}/aptest-pytest-junit.xml'
                if state.pytest_options:
                    CIBW_TEST_COMMAND += f' {state.pytest_options}'
                if state.pytest_paths:
                    for path in state.pytest_paths:
                        CIBW_TEST_COMMAND += f' {{project}}/{path}'
                else:
                    CIBW_TEST_COMMAND += f' {{project}}/tests'
                if state.cibw_ignore_test_failures:
                    CIBW_TEST_COMMAND += ' || true'
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

            CIBW_ENVIRONMENT_PASS_LINUX = list(env_extra.keys())
            
            if platform.system() == 'Linux':
                prefix = '/host'
                # Update key files to be within /host in manylinux
                # docker. Otherwise for example tests that access remote git
                # repositories will not use the appropriate key.
                #
                # Also add key environment variables to CIBW_ENVIRONMENT_PASS_LINUX.
                #
                new_keys = list()
                for url_prefix, path, env, pos in state.keys:
                    if path or env:
                        if path:
                            path = f'{prefix}{os.path.abspath(path)}'
                        if env:
                            CIBW_ENVIRONMENT_PASS_LINUX.append(env)
                        new_keys.append((url_prefix, path, env, pos))
                state.keys += new_keys
                state.keys.sort(reverse=True)
                    
            else:
                prefix = ''

            if platform.system() == 'Linux' and package == 'pymupdfpro':
                # Build will run inside a CentOS-7 container; we
                # need to install fontconfig-devel so `#include
                # <fontconfig/fonctconfig.h>` works. And for SO build
                # we need ssh to allow its git submodule commands.
                #
                CIBW_BEFORE_BUILD_LINUX = (
                        'echo "aptest: installing fontconfig-devel and ssh"'
                        ' && yum -y install fontconfig-devel'
                        ' && yum groupinstall -y fonts'
                        ' && yum install -y openssh-clients'
                        )
                # We also need to declare that PYMUPDFPRO_SETUP_SOT is
                # a safe git directory if set, because ownership of
                # PYMUPDFPRO_SETUP_SOT in /host/... in docker may have
                # different owner from current user.
                PYMUPDFPRO_SETUP_SOT = state.env_extra.get('PYMUPDFPRO_SETUP_SOT')
                if PYMUPDFPRO_SETUP_SOT:
                    CIBW_BEFORE_BUILD_LINUX += f' && git config --global --add safe.directory {PYMUPDFPRO_SETUP_SOT}'
                
                env_extra['CIBW_BEFORE_BUILD_LINUX'] = CIBW_BEFORE_BUILD_LINUX

            PIP_EXTRA_INDEX_URL = f'file://{prefix}{os.path.abspath(state.wheelhouse)}/simple'.replace('\\', '/')

            # Ensure that when cibuildwheel runs pip to
            # install prerequisite packages, it also looks in
            # state.wheelhouse. PIP_EXTRA_INDEX_URL is equivalent to
            # pip's `--extra-index-url`.
            env_extra['PIP_EXTRA_INDEX_URL'] = PIP_EXTRA_INDEX_URL

            if (1
                    and package == 'pymupdf_layout'
                    and platform.system() == 'Darwin'
                    and platform.machine() == 'x86_64'
                    ):
                # 2026-02-08: onnxruntime is not available on macos-intel-python3.14.
                #
                pipcl.log(f'Excluding cp314* because onnxruntime not available on macos-intel/python-3.14.')
                env_extra['CIBW_BUILD'] = CIBW_BUILD.replace(' cp314*', '')
            else:
                env_extra['CIBW_BUILD'] = CIBW_BUILD

            # Pass all the environment variables we have set in
            # state.env_extra, to Linux docker. Note that this will
            # miss any settings in the original environment.
            CIBW_ENVIRONMENT_PASS_LINUX.append('PYMUPDFPRO_SETUP_SOT_KEY')  # This can be set in os.environ.
            # Some tests look at GITHUB_ACTIONS e.g. if known to fail on Github.
            CIBW_ENVIRONMENT_PASS_LINUX.append('GITHUB_ACTIONS')
            CIBW_ENVIRONMENT_PASS_LINUX.append('PIP_EXTRA_INDEX_URL')
            CIBW_ENVIRONMENT_PASS_LINUX.sort()
            CIBW_ENVIRONMENT_PASS_LINUX = ' '.join(CIBW_ENVIRONMENT_PASS_LINUX)
            env_extra['CIBW_ENVIRONMENT_PASS_LINUX'] = CIBW_ENVIRONMENT_PASS_LINUX

            pipcl.run(
                    f'cd {directory} && cibuildwheel{cibw_pyodide_args}'
                        f' --output-dir {os.path.abspath(state.wheelhouse)}',
                    env_extra=env_extra,
                    prefix=f'{package}: ',
                    )
        
        pipcl.log(f'Build/test succeeded for {package=}.')
        
        pipcl.run(f'ls -ld {state.wheelhouse}/*')
        pipcl.run(f'piprepo build {state.wheelhouse}')

        if 1:
            pipcl.log(f'Contents of: {state.wheelhouse=} are:')
            for dirpath, dirnames, filenames in os.walk(state.wheelhouse):
                for filename in filenames:
                    path = os.path.join(dirpath, filename)
                    st = os.stat(path)
                    pipcl.log(f'{st=}: {path=}')
                for dirname in dirnames:
                    path_dir = os.path.join(dirpath, dirname)
                    st = os.stat(path_dir)
                    pipcl.log(f'{st=}: {path_dir=}')
    
    pipcl.log(f'Build/test succeeded for packages {state.packages_build}.')


def do_gnn_download(state):
    pipcl.log(f'Install CUDA from; https://developer.nvidia.com/cuda-12-1-0-download-archive')
    layout_location = _get_local('pymupdf_layout', state)
    pipcl.log(f'{layout_location=}')

    # pytorch-scatter does not specify torch as a build-time prerequisite. This is
    # deliberate because they say that usually needs to be built with
    # a specific torch.
    #
    # I don't understand this. The only way to make things work
    # is to install the latest versions on pypi.prg, and build
    # torch-scatter without isolation so that it can build with
    # the installed torch.
    pipcl.run('pip install -v torch')
    pipcl.run('pip install -v --no-build-isolation torch-scatter')

    pipcl.run(f'pip install -r {layout_location}/train/requirements.txt')

    pipcl.run(f'pip install datasets')
    pipcl.run(f'pip install huggingface_hub[hf_xet]')
    #import datasets
    import huggingface_hub  # pylint: disable=import-error

    if 0:
        # List all huggingface datasets.
        pipcl.log(f'huggingface_hub.list_datasets():')
        for dataset in huggingface_hub.list_datasets():
            pipcl.log(f'    {dataset.id=}')

    if 1:

        # Set up as described in
        # https://github.com/ArtifexSoftware/sce/wiki/How-to-train-GNN

        # Download zip files.
        pipcl.run('pip install --upgrade requests')
        url_doclaynet_core_zip = 'https://codait-cos-dax.s3.us.cloud-object-storage.appdomain.cloud/dax-doclaynet/1.0.0/DocLayNet_core.zip'
        url_doclaynet_extra_zip = 'https://codait-cos-dax.s3.us.cloud-object-storage.appdomain.cloud/dax-doclaynet/1.0.0/DocLayNet_extra.zip'

        def download(url):
            '''
            Downloads to basename(url), but does nothing if already
            exists. We download to temporary and rename, so this
            should never overwrite an existing download.
            '''
            path = os.path.basename(url)
            if os.path.exists(path):
                pipcl.log(f'Already exists: {path=}')
            else:
                if state.gnn_doit:
                    github._gh_download(_get_key_github_rest(state), url, path, gh=0)    # pylint: disable=protected-access
                else:
                    assert 0, f'Would download but {state.gnn_doit=}: {url} {path=}'
        download(url_doclaynet_core_zip)
        download(url_doclaynet_extra_zip)

        def marker_ok(marker, infile=None):
            '''
            Returns true if <marker> exists (and is newer than
            <infile> if not None).
            '''
            if os.path.exists(marker):
                mtime_marker = os.stat(marker).st_mtime
                mtime_infile = os.stat(infile).st_mtime if infile else 0
                if mtime_marker > mtime_infile:
                    pipcl.log(f'Already up to date: {marker=}.')
                    return 1
            if not state.gnn_doit:
                assert 0, f'Would return false for {marker=}, but {state.gnn_doit=}'

        def marker_create(marker):
            with open(marker, 'w'):
                pass
            pipcl.log(f'Have created {marker=}.')

        def ensure_unzip(url, directory):
            '''
            Unzips leafname(url) into <directory> if it has not
            already been done.

            If marker file exists and is newer than zip file,
            does nothing. Otherwise unzips leafname(url) into
            <directory> and creates marker file.
            '''
            path_zip = os.path.basename(url)
            marker = f'{directory}/_marker_{path_zip}'
            if marker_ok(marker, path_zip):
                return
            import zipfile
            pipcl.log(f'Opening {path_zip=}')
            with zipfile.ZipFile(path_zip) as z:
                pipcl.log(f'Extacting {path_zip=} into {directory=}.')
                os.makedirs(directory, exist_ok=1)
                z.extractall(directory)
            marker_create(marker)

        if 1:
            # Unzip.
            ensure_unzip(url_doclaynet_core_zip, 'datasets/DocLayNet')
            ensure_unzip(url_doclaynet_extra_zip, 'datasets/DocLayNet')

        if 1:
            # Generate PKL.

            marker_pkl = '_marker_pkl'
            if marker_ok(marker_pkl):
                pass
            else:
                pipcl.run(f'{sys.executable}'
                        f' {layout_location}/train/tools/make_pkl_data_from_COCO_json.py'
                        f' --json datasets/DocLayNet/COCO/train.json'
                        f' --img_dir datasets/DocLayNet/PNG'
                        f' --save_dir workspace/pkl_data/train'
                        )
                with open(marker_pkl, 'w'):
                    pipcl.log(f'Have created {marker_pkl=}.')

            marker_pkl_validation = '_marker_pkl_validation'
            if marker_ok(marker_pkl_validation):
                pass
            else:
                pipcl.run(f'{sys.executable}'
                        f' {layout_location}/train/tools/make_pkl_data_from_COCO_json.py'
                        f' --json datasets/DocLayNet/COCO/val.json'
                        f' --img_dir datasets/DocLayNet/PNG'
                        f' --save_dir workspace/pkl_data/val'
                        )
                with open(marker_pkl_validation, 'w'):
                    pipcl.log(f'Have created {marker_pkl_validation=}.')

        if 0:
            # Doesn't work - No such file or directory: 'workspace/checkpoints/model.yaml.
            pipcl.run(f'pip install --upgrade torchvision')
            pipcl.run(
                    f'{sys.executable} {layout_location}/train/tools/test_gnn.py {layout_location}/train/cfgs/config.yaml',
                    env_extra=dict(PYTHONPATH=layout_location),
                    )

    if 0:
        # Alternative ways of getting data.

        # Get data using `datasets` module.

        #doclaynet_core = datasets.load_dataset('doclaynet_core')
        #doclaynet_core = datasets.load_dataset('doclaynet_extra')
        # From https://huggingface.co/datasets/pierreguillou/DocLayNet-large:

        # Get data using huggingface_hub.snapshot_download().
        # From https://huggingface.co/datasets/pierreguillou/DocLayNet-large.
        dataset_id='pierreguillou/DocLayNet-large'

        huggingface_key = None
        if state.huggingface_key_path_abs:
            with open(state.huggingface_key_path_abs) as f:
                huggingface_key = f.read().strip()

        pipcl.log(f'huggingface_hub.snapshot_download()')
        huggingface_hub.snapshot_download(dataset_id, token=huggingface_key, repo_type='dataset', max_workers=1)


def do_gnn_show(state):
    prefix = 'gnn-show: '
    if state.gnn_show_select_root:
        pattern = f'{state.gnn_show_select_root}/test-gnn-*.json'
    else:
        pattern = f'test-gnn-*.json'
    if state.gnn_show_select:
        pipcl.log(f'{state.gnn_show_select=}')
        gnn_select_code = compile(state.gnn_show_select, '', 'eval')
        def selectfn(results):  # pylint: disable=unused-argument
            #r = eval(gnn_select_code, globals=dict(results=results))
            r = eval(gnn_select_code)   # pylint: disable=eval-used
            return r
    paths = list()
    if state.gnn_show_paths:
        pattern_matches = state.gnn_show_paths
    else:
        pattern_matches = glob.glob(pattern)
    for path in pattern_matches:
        if state.gnn_show_select:
            with open(path) as f:
                results = json.load(f)
            # Convert to a Doct so that selectfn() can use dotted notation.
            results = doct.Doct(results)
            s = selectfn(results)
        else:
            s = True
        if s:
            #pipcl.log(f'{command}: Selecting: {path!r}')
            paths.append(path)
    #pipcl.log(f'{prefix}Selected gnn paths ({len(paths)}/{len(pattern_matches)}:')
    #pipcl.log(f'{paths=}')
    for path in paths:
        pipcl.log(f'{prefix}    {path!r}')

    if state.gnn_show_text == '':
        out_text = None
    elif state.gnn_show_text is None:
        out_text = f'gnn-text-{g_date_time}.txt'
        #out_text_simple = f'gnn-text.txt'
    else:
        out_text = state.gnn_show_text
        #out_text_simple = None

    if state.gnn_show_graph == '':
        out_graph = None
        out_graph_simple = None
    elif state.gnn_show_graph is None:
        out_graph = f'gnn-graph-{g_date_time}.html'
        out_graph_simple = f'gnn-graph.html'
    else:
        out_graph = state.gnn_show_graph
        out_graph_simple = None

    if 1:
        graph.plot_gnn_html(paths, out_text, out_graph)
        pipcl.log(f'Have created: {out_text=} {out_graph=}')
        if out_graph_simple:
            pipcl.fs_remove(out_graph_simple)
            try:
                os.symlink(out_graph, out_graph_simple)
            except Exception as e:
                pipcl.log(f'Warning: failed to create link from {out_graph_simple=} to {out_graph=}: {e}')
            pipcl.log(f'Have created softlink {out_graph_simple=} => {out_graph=}')
    else:
        pipcl.log(f'Not creating graph output; {state.gnn_show_graph=}.')


def dicts_equal(a, b, verbose=0):
    import difflib
    ret = a == b
    if not ret:
        if verbose:
            aa =json.dumps(a, indent='    ', sort_keys=1)
            bb =json.dumps(b, indent='    ', sort_keys=1)
            lines = difflib.unified_diff(
                    aa.split('\n'),
                    bb.split('\n'),
                    lineterm='',
                    )
            # Skip initial lines.
            #assert next(lines) == '--- '
            #assert next(lines) == '+++ '
            lines = list(lines)
            pipcl.log(f'Diff lines: {len(lines)=}')
            pipcl.log(textwrap.indent('\n'.join(lines), '    '))
            if not lines:
                pipcl.log(f'json identical but a!=b.')
                pipcl.log(f'{a=}')
                pipcl.log(f'{b=}')
    return ret


if 0:
    with open('test-gnn-pymupdf4llm-2025-12-19-17-46-09.json') as f:
        a = json.load(f)
    with open('test-gnn-pymupdf4llm-2025-12-19-17-48-56.json') as f:
        b = json.load(f)
    pipcl.log(f'{dicts_equal(a, b)=}')
        

def do_test_gnn(state):
    layout_location = _get_local('pymupdf_layout', state)

    pipcl.run(f'pip install tqdm')
    pdf_dir = 'datasets/DocLayNet/PDF'
    
    ret = dict()

    ret['python'] = dict()
    ret['python']['platform.machine()'] = platform.machine()
    ret['python']['platform.system()'] = platform.system()
    ret['python']['platform.python_implementation()'] = platform.python_implementation()
    ret['python']['platform.python_version()'] = platform.python_version()
    ret['python']['platform.uname()'] = list(platform.uname())
    ret['python']['platform.system()'] = platform.system()
    ret['python']['sys.version'] = sys.version
    ret['python']['sys.version_info'] = list(sys.version_info)

    ret['wordsize'] = sys.maxsize.bit_length() + 1

    ret['environ'] = dict()
    ret['environ']['USER'] = os.environ.get('USER')

    ret['state'] = dict()
    ret['state']['test_gnn_det'] = state.test_gnn_det
    ret['state']['pdf_dir'] = pdf_dir
    ret['state']['limit'] = state.test_gnn_limit

    for n, v in state.test_gnn_extra.items():
        ret[n] = v

    ret['packages'] = dict()
    for package, (location, _) in state.packages.items():
        if package == 'mupdf':
            # There is no mupdf package - it's only part of pymupdf.
            directory = None
            metadata_version = None
        else:
            directory = _get_local(package, state)
            metadata_version = importlib.metadata.version(package)
        ret['packages'][package] = dict()
        ret['packages'][package]['location'] = location
        ret['packages'][package]['directory'] = directory
        ret['packages'][package]['metadata_version'] = metadata_version
        if directory:
            sha, comment, diff, branch = pipcl.git_info(directory)
            author_date = pipcl.git_info_author_date(directory)
            committer_date = pipcl.git_info_committer_date(directory)
            ret['packages'][package]['gitinfo'] = dict(
                    sha=sha,
                    comment=comment,
                    diff=diff,
                    branch=branch,
                    author_date=author_date,
                    committer_date=committer_date,
                    )

    # Provide version info for all installed packages. This
    # is helpful if for example pymupdf was not specified -
    # in this case the latest version on pypi will have been
    # installed as a prerequisite by pip.
    text = pipcl.run(f'pip list --format json', capture=1)
    pip_list_packages = json.loads(text)
    ret['pip-list'] = pip_list_packages

    # Check <ret> only contains simple types. Otherwise comparisons can
    # show spurious differences.
    def check(d):
        if isinstance(d, dict):
            for k, v in d.items():
                assert isinstance(k, str)
                check(v)
        elif isinstance(d, list):
            for v in d:
                check(v)
        elif d is None:
            pass
        elif isinstance(d, (str, int, float)):
            pass
        else:
            assert 0, f'Unrecognised item {type(d)=}: {d=}'
    check(ret)

    out_json = None
    if state.test_gnn_cache:
        # See whether an identical run has already been done.
        import copy
        ret0 = copy.deepcopy(ret)
        ignore_keys = ('results', 't_start', 't_duration', 'pip-list')
        for key in ignore_keys:
            ret0.pop(key, None)
        for path in glob.glob(f'test-gnn-results/test-gnn-*.json'):
            if path.endswith('-raw.json'):
                continue
            with open(path) as f:
                r = json.load(f)
            for key in ignore_keys:
                r.pop(key, None)
            pipcl.log(f'Comparing with {path=}.')
            equal = dicts_equal(r, ret0)
            if equal:
                pipcl.log(f'Found matching previous run: {path=}.')
                out_json = path
                break
        if not out_json:
            pipcl.log(f'Did not find any matching previous run.')
    
    if out_json:
        # Nothing to do.
        pass
        #with open(out_json) as f:
        #    results = json.load(f)
    else:
        # Run the test.
        out_csv = f'test-gnn-results/test-gnn-{g_date_time}.csv'
        out_json = f'test-gnn-results/test-gnn-{g_date_time}.json'
        out_json_raw = f'test-gnn-results/test-gnn-{g_date_time}-raw.json'
        pipcl.fs_ensure_dir('test-gnn-results')
        
        command = textwrap.dedent(f'''
                cd {layout_location}
                && python {state.test_gnn_det}
                    --pdf_dir {os.path.abspath(pdf_dir)}
                    --result_csv_path {os.path.abspath(out_csv)}
                    --result_json_path {os.path.abspath(out_json_raw)}
                    --limit {state.test_gnn_limit}
                 ''')
        ret['t_start'] = time.time()
        
        pipcl.run(command)
        
        ret['t_duration'] = time.time() - ret['t_start']
        with open(out_json_raw) as f:
            ret['results'] = json.load(f)
        ret['results_csv'] = pipcl.fs_read(out_csv)
        
        with open(out_json, 'w') as f:
            json.dump(ret, f, indent='    ', sort_keys=1)
        
        if state.test_gnn_push:
            push_results(out_json, state.env_extra)
        else:
            pipcl.log(f'Not pushing results to PyMuPDF-performance-results: {out_json=}')
    
    out_json_simple = 'test-gnn-results/test-gnn.json'
    pipcl.fs_symlink(out_json_simple, out_json)
    
    if state.test_gnn_out:
        pipcl.fs_symlink(state.test_gnn_out, out_json)


def do_test_single(state, package, failed_packages):
    location, _ = state.packages[package]
    if not location:
        return
    if package == 'mupdf':
        return
    if package.startswith(f'smartoffice'):
        return
    directory = _get_local(package, state, test=1)
    if not directory:
        return
    
    with pipcl.LogPrefix(f'test {package}: '):
        if package == 'langchain_pymupdf_layout':
            command = f'{sys.executable} {directory}/simple_test.py'
            e = pipcl.run(
                    command,
                    env_extra=state.env_extra,
                    check=0,
                    )
            pipcl.log(f'langchain_pymupdf_layout command returned {e=}.')
        elif package == 'pdf2docx':
            # No pytest tests, instead a Makefile.
            if platform.system() == 'Windows':
                pipcl.log(f'Not attempting to test on Windows because needs make.')
                e = 0
            else:
                pipcl.run(f'pip install pytest-cov')
                e = pipcl.run(f'cd {directory} && make test', check=0)
        elif package == 'swig':
            e = pipcl.run(f'cd {directory}/build/build && make check-python-test-suite', check=0)
        else:
            #pipcl.run(f'pip install pytest-reportlog')
            # Change directory into package checkout, otherwise on Github pytest
            # can use aptest's pytest.ini, and not find any matching test files.
            if package == 'aptest':
                pipcl.run(f'pip install swig')

            if state.pytest_junit_xml:
                path_junit_xml = f'{os.path.abspath(state.wheelhouse)}/{package}-pytest-junit.xml'

            command = f'pytest'
            if state.pytest_timeout:
                command += f' --timeout {state.pytest_timeout}'
            if state.pytest_timeout_method:
                command += f' --timeout-method {state.pytest_timeout_method}'
            #command += f' --report-log=aptest-pytest.jsonl'
            if state.pytest_junit_xml:
                command += f' --junit-xml={path_junit_xml}'
            #command += f' --durations=10'
            if state.pytest_options:
                command += f' {state.pytest_options}'
            if state.pytest_paths:
                for path in state.pytest_paths:
                    command += f' {path}'
            elif package == 'pdf4llm':
                command += f' pdf4llm/tests'
            else:
                # We need to somehow limit things to {package}/tests/
                # because otherwise pytest can recurse into other
                # directories (e.g. mupdf checkout in pympdf) and get
                # hopelessly confused.
                #
                # Would like to do `pytest {directory}` and let
                # pytest.ini identify `tests/` as the directory look
                # in for tests. But unfortunately pytest configuration
                # doesn't seem to allow this sort of thing, for example
                # `testpaths = tests` only effects `cd {package} &&
                # pytest` - i.e. running pytest on current directory
                # without specifying any location.
                #
                command += f' tests'

            if state.pytest_wrap in ('valgrind', 'helgrind'):
                if not state.pytest_options:
                    command += ' -sv'
            if state.pytest_wrap:
                command = f'python -m {command}'
                if state.pytest_wrap == 'gdb':
                    command = f'gdb -ex "set print inferior-events off" --args {command}'
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
            command = f'cd {directory} && {command}'
            e = pipcl.run(
                    command,
                    env_extra=state.env_extra,
                    check=0,
                    )
            if state.pytest_junit_xml:
                try:
                    junit_xml_pretty = xml.dom.minidom.parse(path_junit_xml).toprettyxml()
                    pipcl.fs_write(f'{path_junit_xml}.xml', junit_xml_pretty)
                except Exception as ee:
                    e = ee
                    pipcl.log(f'Failed to prettyfy {path_junit_xml=}: {e}')
        if e:
            pipcl.log(f'Tests failed for {package=}.')
            if state.cibw_ignore_test_failures:
                pipcl.log(f'Ignoring test failure for {package=} because {state.cibw_ignore_test_failures=}.')
            else:
                failed_packages.append(package)
        else:
            pipcl.log(f'Tests succeeded for {package=}.')


def do_test(state):
    if state.pytest_wrap in ('valgrind', 'helgrind'):
        if state.system_packages:
            pipcl.log('Installing valgrind.')
            pipcl.run(f'sudo apt update')
            pipcl.run(f'sudo apt install --upgrade valgrind')
        pipcl.run(f'valgrind --version')

    pipcl.run(f'pip install --upgrade pytest')
    if state.pytest_timeout:
        pipcl.run(f'pip install --upgrade pytest-timeout')
    pipcl.log(f'packages_test:')
    for i in state.packages_test:
        pipcl.log(f'    {i!r}')

    failed_packages = list()

    if state.test_extra_packages:
        command = 'pip install'
        for p in state.test_extra_packages:
            command += f' {shlex.quote(p)}'
        pipcl.run(command)
    
    pipcl.log(f'pip list')

    for package in state.packages_test:
        with pipcl.LogPrefix(f'{package}: '):
            do_test_single(state, package, failed_packages)
    
    if failed_packages:
        pipcl.log(f'Tests failed for these packages:')
        for package in failed_packages:
            pipcl.log(f'    {package}')
        raise Exception(f'Packages failed tests: {failed_packages}')


def get_self_gitinfo():
    sha, comment, diff, branch = pipcl.git_info(g_root)
    if sha:
        return sha, comment, diff, branch
    try:
        from . import gitinfo
    except ImportError:
        return None, None, None, None
    else:
        return (
                gitinfo.sha,
                gitinfo.comment,
                gitinfo.diff,
                gitinfo.branch,
                )


def main(argv):
    
    if github_workflow_unimportant():
        return
    
    args, state = get_args(argv)
    if args is None:
        # COMP_LINE.
        return 0
    
    # It's important that we do not use <argv> any more - we need to use
    # args.argv instead, because this contains any args from ~/.aptest and
    # `-a <name>`, and more importantly will have had some items set to empty
    # string, for example `-r foo` will have been converted to `foo ''`, which
    # avoids recursion when we rerun ourselves on local or remote machine.
    del argv
    
    # Update convenience link to venv.
    try:
        pipcl.fs_symlink(g_venv_prefix, os.path.relpath(sys.prefix))
    except Exception as e:
        pipcl.log(f'Warning: unable to create symlink from {g_venv_prefix!r} to {os.path.relpath(sys.prefix)!r}: {e}')
        
    if state.devel:
        # Leave pipcl's default, which includes elapsed time and file:line:fn.
        pass
    elif APTEST_NESTED:
        # No log prefix.
        pipcl.g_log_format = f'{os.path.basename(sys.prefix)}: '
    else:
        # Just output elapsed time by default.
        pipcl.g_log_format = f'[+%d]: {os.path.basename(sys.prefix)}: '
    
    sha, comment, diff, _branch = get_self_gitinfo()
    pipcl.log(f'Aptest gitinfo: {sha=}: {comment}')
    pipcl.log(f'Command line: {shlex.join(args.argv)}')

    if state.show_help:
        p = os.path.abspath(f'{__file__}/../README.rst')
        with open(p) as f:
            text = f.read()
        pipcl.log(text)
        return
    
    # Check whether we should run with `-o <osname>`.
    if not state.remote:
        os_self = platform.system().lower()
        oss = [os_self]
        #pipcl.log(f'{oss=}')
        #pipcl.log(f'{state.os_names=}')
        apply_deltas(oss, state.os_names, check=0)
        #pipcl.log(f'{oss=}')
        if os_self not in oss:
            pipcl.log(f'Not running on {os_self=}: {state.os_names=} {oss=}')
            return
    
    # Rerun with different python if `--python` is specified.
    if not state.remote and state.python:
        python_version = pipcl.run(
                f'{state.python} -c "import platform;'
                    f' print(platform.python_version())"',
                capture=1,
                )
        python_version_tuple = tuple(python_version.split('.'))
        if platform.python_version_tuple()[:2] == python_version_tuple[:2]:
            pipcl.log(
                    f'Already running on required python.'
                        f' {platform.python_version_tuple()=} {python_version_tuple=}'
                    )
        else:
            pipcl.log(
                    f'{state.python=}: rerunning because'
                        f' {platform.python_version_tuple()[:2]=}'
                        f' != {python_version_tuple[:2]=}'
                    )
            e = pipcl.run(
                    f'{state.python} {shlex.join(args.argv)}',
                    check=0,
                    env_extra=dict(APTEST_NESTED='1'),
                    )
            sys.exit(e)
    
    # Rerun ourselves in a Graal venv if necessary.
    if not state.remote and state.graal:
        if 'cibw' in state.commands:
            # We don't create graal/pyenv, so wheel/build commands
            # will not work.
            assert 'build' not in state.commands
        else:
            # Re-run ourselves in a pyenv/Graal venv.
            # 2025-07-24: We need the latest pyenv.
            graalpy = 'graalpy-24.2.1'
            venv_name = f'venv-aptest-{graalpy}'
            pyenv_dir = f'{g_root_abs}/pyenv-git'
            os.environ['PYENV_ROOT'] = pyenv_dir
            os.environ['PATH'] = f'{pyenv_dir}/bin:{os.environ["PATH"]}'
            os.environ['PIPCL_GRAAL_PYTHON'] = sys.executable

            if state.venv >= 3:
                assert venv_name.startswith('venv-')
                pipcl.fs_remove(venv_name)
            if state.venv == 1 and os.path.exists(pyenv_dir) and os.path.exists(venv_name):
                pipcl.log(
                        f'{state.venv=} and {venv_name=} already exists'
                            f' so not building pyenv or creating venv.'
                        )
            else:
                pipcl.git_get(
                        pyenv_dir,
                        remote='https://github.com/pyenv/pyenv.git',
                        branch='master',
                        )
                pipcl.run(f'cd {pyenv_dir} && src/configure && make -C src')
                pipcl.run(f'which pyenv')
                pipcl.run(f'pyenv install -v -s {graalpy}')
                pipcl.run(f'{pyenv_dir}/versions/{graalpy}/bin/graalpy -m venv {venv_name}')
            e = pipcl.run(f'. {venv_name}/bin/activate && python {shlex.join(args.argv)}',
                    check=False,
                    prefix='{venv_name}: ',
                    env_extra=dict(APTEST_NESTED='1'),
                    )
            sys.exit(e)
    
    if state.verbose:
        pipcl.show_system()
        sha, comment, diff, _branch = pipcl.git_info(g_root)
        pipcl.log(f'aptest: {sha=}')
        pipcl.log(f'aptest: {comment=}')
        pipcl.log(f'aptest: diff:\n{textwrap.indent(diff, "    ")}')
        
    clean_wheelhouse = state.clean_wheelhouse
    if clean_wheelhouse == 'auto':
        if (
                set(state.packages) == set(state.packages_build)
                and (
                    'build' in state.commands
                    or 'cibw' in state.commands
                    )
                ):
            # We're building all packages, so clean wheelhouse.
            clean_wheelhouse = True
        else:
            # We're not building all packages, don't clean wheelhouse so that
            # tests can still be run.
            pipcl.log(f'Not removing {state.wheelhouse=} because not building all packages.')
            clean_wheelhouse = False
    if clean_wheelhouse:
        pipcl.log(f'Removing {state.wheelhouse=}.')
        pipcl.fs_remove(state.wheelhouse)
    os.makedirs(state.wheelhouse, exist_ok=1)
        
    # Set environment variable values in <state.env_extra> to give access to
    # required git repositories.
    #
    paths_to_delete = list()

    if state.remote:  # pylint: disable=too-many-nested-blocks
        args.args_eq.set(state.remote_arg, '')  # So we don't recurse.
        if state.remote == '@github':
            if GITHUB_ACTIONS == 'true':
                pipcl.log(
                        f'Ignoring {state.remote=} because already running on Github,'
                            f' {GITHUB_ACTIONS=}.'
                        )
            else:
                return do_remote_github(state, args)
        else:
            # Use rsync/ssh to sync to/run on remote machine.
            return do_remote(state, args.argv)
        
    if not state.commands and not state.remote_github_workflow_id:
        pipcl.log(f'## Warning, no commands specified so nothing to do.')
    
    if state.run_commands and 'run' not in state.commands:
        pipcl.log(f'## Warning, --run was specified but no `run` command.')
    
    # Clone/update/build swig if specified.
    with pipcl.LogPrefix('--set-swig: '):
        swig_binary = pipcl.swig_get(state.swig, state.swig_quick)
    #pipcl.log(f'{state.swig=}')
    #pipcl.log(f'{swig_binary=}')
    if swig_binary:
        # Prevent individual builds from installing default swig.
        state.env_extra['PYMUPDF_SETUP_SWIG'] = swig_binary
        state.env_extra['PYMUPDFPRO_SETUP_SWIG'] = swig_binary
        state.env_extra['PYMUPDF_LAYOUT_SETUP_SWIG'] = swig_binary
    
    if (1
            and GITHUB_ACTIONS == 'true'
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
            
            with pipcl.LogPrefix(f'{command}: '):
            
                if command in ('build', 'cibw'):
                    # 2025-11-14: piprepo seems to also required setuptools.
                    # 2026-02-08: we need setuptools<81 otherwise there is no pkg_resources module.
                    pipcl.run(f'pip install --upgrade piprepo "setuptools<81"')
                    #pipcl.fs_ensure_empty_dir(state.wheelhouse)
                    pipcl.run(
                            f'piprepo build {state.wheelhouse}',
                            prefix='piprepo build: ',
                            )
                if 0:
                    pass

                elif command == 'build':
                    do_build(state)

                elif command == 'cibw':
                    do_cibw(state)
                
                elif command == 'docs':
                    pipcl.run('pip install -U docutils')
                    out = f'{g_root}/README.rst.html'
                    # -s Include a "View document source" link.
                    # -d Include the date at the end of the document (UTC).
                    # -t Include the time & date (UTC).
                    # -v Report all system messages.  (Same as "--report=1".)
                    # --pep-references Recognize and link to standalone PEP references (like "PEP 258").
                    # -g Include a "Generated by Docutils" credit and link.
                    #
                    pipcl.run(
                            f'docutils'
                                f' -g -d -s -t'
                                f' --halt=3'
                                f' --pep-references'
                                f' --compact-lists'
                                f' --stylesheet={g_root}/rst.css'
                                f' {g_root}/README.rst'
                                f' {out}'
                            )
                    if 1:
                        # Make lists more compact vertically.
                        html = pipcl.fs_read(out)
                        html = html.replace('<li><p>', '<li>')
                        html = html.replace('</p></li>', '</li>')
                        pipcl.fs_write(out, html)
                    pipcl.log(f'Have created: {out}')
                
                elif command == 'draft':
                    Assert(state.draft_location, f'<draft_location> unset')
                    command = f'rsync -ai {state.wheelhouse}/ {state.draft_location}/'
                    pipcl.run(command)

                elif command == 'gnn-download':
                    do_gnn_download(state)

                elif command == 'gnn-show':
                    do_gnn_show(state)

                elif command == 'gnn-train':
                    layout_location = _get_local('pymupdf_layout', state)
                    pipcl.run(f'pip install --upgrade torchvision')
                    layout_location_abs = os.path.abspath(layout_location)
                    pipcl.log(f'{layout_location=} {layout_location_abs=}')
                    pipcl.run(
                            f'cd gnn'
                                f' && {sys.executable}'
                                f' {layout_location_abs}/train/tools/test_gnn.py'
                                f' {layout_location_abs}/train/cfgs/config.yaml',
                            env_extra=dict(PYTHONPATH=layout_location_abs),
                            )

                elif command == 'populate':
                    for package in state.packages_build:
                        with pipcl.LogPrefix(f'{package}: '):
                            _location, _args_pos = state.packages[package]
                            if 1: # location.startswith('git:'):
                                directory = _get_local(package, state)
                                pipcl.log(f'Local directory for {package=} is: {directory!r}')

                elif command.startswith('test-gnn'):
                    do_test_gnn(state)

                elif command == 'run':
                    for package, command in state.run_commands:
                        directory = _get_local(package, state, test=True)
                        Assert(
                                directory,
                                f'Cannot run command within {package=} because no local directory.',
                                )
                        pipcl.run(f'cd {directory} && {command}')

                elif command == 'test':
                    do_test(state)
                
                elif command == 'upload':
                    github._upload( # pylint: disable=protected-access
                            token_pypi=_get_key_pypi(state),
                            local_dir_union=state.wheelhouse_release,
                            pyodide_wheels=None,
                            upload='pypi',
                            )
                
                elif command == 'windows-show-vs-instances':
                    pipcl.log(f'{command}:')
                    for vs in pipcl.wdev.windows_vs_multiple():
                        pipcl.log(vs.description_ml(indent='    '))

                else:
                    assert 0, f'{command=}'
    finally:
        for path in paths_to_delete:
            pipcl.fs_remove(path)


def _get_local(package, state, test=False):
    '''
    Returns local directory containing <package> checkout. Returns None if
    location is pip:.
    
    test: If true, we return second location if specified.
    '''
    location = None
    if test:
        # Use second location of <package> if specified.
        location, _ = state.packages2.get(package, (None, None))
        if location:
            pipcl.log(f'Using second specified location for {package=}: {location}')
    if location is None:
        location, _ = state.packages[package]
    
    if location is None or location.startswith('pip:'):
        return None
    if location.startswith('git:'):
        info = name_info(state, package)
        local = f'aptest-git-{package}'
        if state.git_local_detailed:
            if tail := location[len('git:'):]:
                # Append branch/tag etc to the local checkout name.
                pipcl.log(f'{tail=}')
                # Put different branches/tags into different directories.
                tail = re.sub('[\\/ "\':]', '_', tail)
                local += f'-{tail}'
        #pipcl.log(f'{local=}')
        with pipcl.LogPrefix(f'{local}: '):
            env_extra = state.env_extra
            pipcl.log(f'{package=}')
            
            ssh_key = None
            ssh_keyfile = None
            key_path, key_env = _get_key(
                    state,
                    name_info(state, package)['git_remote'],
                    on_error=None,
                    )
            if key_path:
                ssh_keyfile = key_path
            elif key_env:
                ssh_key = os.environ[key_env]
                
            pipcl.log(f'{ssh_key=}')
            pipcl.log(f'{ssh_keyfile=}')
            pipcl.log(f'{env_extra=}')
            # Ensure that we don't get Windows line endings for text files on
            # Github windows runners, which causes non-identical pure-python wheels depending
            # on where they are built. This is a workaround for pipcl-1.
            if GITHUB_ACTIONS == 'true':
                pipcl.run(f'git config --global core.autocrlf input')
            directory = pipcl.git_get(
                    local,
                    remote=info['git_remote'],
                    branch=info['git_branch'],
                    text=location,
                    env_extra=env_extra,
                    submodules=info['submodules'],
                    key=ssh_key,
                    keyfile=ssh_keyfile,
                    depth=state.git_depth,
                    # Ensure that we don't get Windows line endings for text
                    # files when running `git clone`; otherwise we can get
                    # non-identical pure-python wheels depending on where they
                    # were built.
                    #
                    # Enable this after pipcl-2 is released.
                    # clone_extra='--config core.autocrlf=input',
                    )
    else:
        directory = location
        if state.check_unchanged:
            _, _, diff, _ = pipcl.git_info(directory)
            Assert(
                    not diff,
                    f'{state.check_unchanged=} but checkout has uncommitted changes: {directory!r}.',
                    )
            pipcl.log(f'{state.check_unchanged=}, local checkout ok: {directory!r}')
        if state.check_pushed:
            out = pipcl.run(f'cd {directory} && git branch -r --contains', capture=1)
            assert isinstance(out, str)
            Assert(
                    out.strip(),
                    f'{state.check_pushed=} but local checkout has un-pushed commits: {directory!r}',
                    )
            pipcl.log(f'{state.check_pushed=}, local checkout ok ({out=}): {directory!r}')
    if not test:
        if package in state.clean_git:
            pipcl.run(
                    f'cd {directory} && git clean -fdx',
                    prefix=f'clean_git: ',
                    env_extra=state.env_extra,
                    )
        if package in state.clean_setup:
            pipcl.run(
                    f'cd {directory} && {sys.executable} setup.py clean',
                    prefix=f'clean_setup: ',
                    env_extra=state.env_extra,
                    )
        if package in state.clean_setup_all:
            pipcl.run(
                    f'cd {directory} && {sys.executable} setup.py clean --all',
                    prefix=f'clean_setup_all: ',
                    env_extra=state.env_extra,
                    )
    
    # Show information about the checkout, regardless of where it came from.
    sha, comment, diff, branch = pipcl.git_info(directory)
    with pipcl.LogPrefix(f'Local checkout of {package=}, {directory}: '):
        pipcl.log(f'{sha=}')
        pipcl.log(f'{branch=}')
        pipcl.log(f'comment:\n{textwrap.indent(comment or "", "    ")}')
        if diff:
            pipcl.log(f'diff:\n{textwrap.indent(diff or "", "    ")}')
        else:
            pipcl.log(f'{diff=}')
    
    if state.check_unchanged:
        Assert(
                not diff,
                f'Checkout is changed but {state.check_unchanged=}: {package=} {directory=}.',
                )
        # todo: also check that sha is on remote.
    
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


def push_results(
        path,
        env_extra,
        ):
    '''
    Pushes new performance data as a JSON file to Github repository
    ArtifexSoftware/PyMuPDF-performance-results.

    We clone the results repository, and write `results` to a file called
    `name` using json.dump(). And we create/overwrite a softlink called
    `name_latest` that points to `name`.

    Then we use `git add`, `git commit` and `git push` to push the new results
    file and `results-latest` softlink to the results repository.

    Args:
        path:
            Name of results file.
        name_latest:
            Name of softlink to create that links to `name`.

    We require environment variable PYMUPDF_PERFORMANCE_RESULTS_RW to be set to
    github access token. If not present, we return quietly.
    '''
    # Get results repository.
    remote = f'git@github.com:ArtifexSoftware/PyMuPDF-performance-results'
    local = 'aptest-git-pymupdf-performance-results'
    pipcl.git_get(
            local,
            remote='git@github.com:ArtifexSoftware/PyMuPDF-performance-results.git',
            branch='jules',
            env_extra=env_extra,
            )

    pipcl.run(f'cd {local} && git config user.email "julian.smith@artifex.com"')
    pipcl.run(f'cd {local} && git config user.name "aptest"')

    # Copy into results checkout.
    leaf = os.path.basename(path)
    shutil.copy2(path, f'{local}/{leaf}')
    
    # Push to results repository.
    pipcl.run(f'cd {local} && git add {leaf}')
    pipcl.run(f'cd {local} && git commit -m "{leaf}: new results."')
    pipcl.run(f'cd {local} && git push -v', env_extra=env_extra)

    pipcl.log(f'Have pushed results to {remote}.')


def main0():
    if sys.argv[1:2] == ['--doctest']:
        import doctest
        if sys.argv[2:]:
            for ff in sys.argv[2:]:
                fff = globals()[ff]
                doctest.run_docstring_examples(fff, globals())
        else:
            doctest.testmod(None)
    else:
        try:
            e = main(sys.argv)
        except BrokenPipeError:
            # We end up here if our output is being piped into less, then less
            # is killed.
            e = 1
        except Exception as ee:
            backtrace_limit = None
            if g_devel:
                pass
            else:
                # See whether any chained exception is a type for which we
                # don't need to show backtraces.
                #
                # * Failed commands will have generated diagnostics already.
                # * AptestUserError exceptions already contain enough
                #   information.
                #
                ee2 = ee
                while ee2:
                    if isinstance(
                            ee2,
                            (
                                subprocess.CalledProcessError,
                                subprocess.TimeoutExpired,
                                AptestUserError,
                                cli.CliError,
                            )
                            ):
                        backtrace_limit = 0
                        break
                    ee2 = ee2.__cause__
            backtrace.show(
                    reverse_chain=1,
                    limit=backtrace_limit,
                    brief=1,
                    )
            e = 1
        finally:
            if g_atexit:
                with pipcl.LogPrefix('atexit: '):
                    e = pipcl.run(g_atexit, check=0)
                    if e:
                        pipcl.log(f'Warning, {g_atexit=} failed: {e=}')
        
        if g_log_tee:
            pipcl.log(f'Aptest: log output is in: {g_log_tee}')
        if e:
            pipcl.log(f'Aptest: exiting with error {e}.')
        else:
            pipcl.log(f'Aptest: exiting with success.')
        sys.exit(e)


if __name__ == '__main__':
    main0()
