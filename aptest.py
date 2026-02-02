#! /usr/bin/env python3

'''Developer build/test script for Artifex packages.

See README.rst for details.
'''

import glob
import importlib.metadata
import json
import os
import platform
import shlex
import shutil
import subprocess
import sys
import sysconfig
import textwrap
import time
import traceback

import backtrace
import doct
import graph
import github
import pipcl

# Get improved display of exceptions and stacktraces.
backtrace.exception_hook_install()

g_root_abs = os.path.abspath( f'{__file__}/..')
g_root = pipcl.relpath(g_root_abs)


# With cibw we build and test Python 3.x for x in this range.
python_versions_minor = range(10, 14+1)


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
        pipcl.run(
                f'cd {path} && git push -fv {repository or "origin"} HEAD:{remote_branch}',
                prefix='git push: ',
                env_extra=state.env_extra,
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
        doit=1,
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
    command = f'rsync -aizr'
    if not doit:
        command += ' -n'
    if verbose:
        command += ' --stats'
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
    pipcl.run(command, prefix=f'reverse sync {path_remote} => {path_local}: ', log=1)
        

def sync(remote, remote_dir, path, ssh_command, verbose, state):    # pylint: disable=too-many-positional-arguments
    '''
    Syncs <path> to <remote>:<remote_dir>/ using rsync.
    
    If <path>/.git is a directory we sync only files known to git.

    Returns true if <path>/.git is a directory.
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
        pipcl.run(command, prefix=f'sync {path}: ', out='log', ticker=0.5)
    finally:
        if filenames_path:
            pipcl.fs_remove(filenames_path)
    return ret


# Hard-coded information about supported packages. This used when deferring
# to Github with `-r @github`. The `aliases` items are used when looking at
# command-line arguments.
#
g_package_info = {
        'aptest':
            {
                'github_name': 'ArtifexSoftware/aptest',
                'git_branch': 'main',
                'aliases':  [],
                'order': -1,
            },
        'mupdf':
            {
                'github_name': 'ArtifexSoftware/mupdf',
                'git_branch': 'master',
                'aliases':  ['m'],
                'order': 0,
            },
        'pymupdf':
            {
                'github_name': 'pymupdf/PyMuPDF',
                'git_branch': 'main',
                'aliases':  ['p'],
                'order': 1,
            },
        'pymupdf4llm':
            {
                'github_name': 'pymupdf/pymupdf4llm',
                'git_branch': 'main',
                'aliases':  ['4llm'],
                'order': 2,
            },
        'pymupdfpro':
            {
                'github_name': 'ArtifexSoftware/PyMuPDFPro',
                'git_branch': 'main',
                'aliases':  ['pro', 'P'],
                'order': 2,
            },
        'pymupdf_layout':
            {
                'github_name': 'ArtifexSoftware/sce',
                'git_branch': 'master',
                'aliases':  ['layout', 'l'],
                'submodules': False,
                'order': 2,
            },
        'langchain_pymupdf_layout':
            {
                'github_name': 'pymupdf/langchain-pymupdf-layout',
                'git_branch': 'main',
                'aliases':  ['langchain'],
                'order': 3,
            },
        'smartoffice':
            {
                'gitlab_name': 'smartoffice/sot',
                'git_branch': 'master',
                'aliases':  ['sot', 's'],
                'submodules': False,
                'order': 1, # Fetch before Layout
            },
        'pdf_feature_inspector':
            {
                'github_name': 'ArtifexSoftware/pdf_feature_inspector',
                'git_branch': 'main',
                'aliases':  ['pfi'],
                'order': 4,
            },
        
        # Experimental, doesn't work.
        'presidio':
            {
                'github_name': 'ArtifexSoftware/presidio',
                'git_branch': 'main',
                'aliases':  list(),
                'order': 4,
            }
        }

for name, value in g_package_info.items():
    if value.get('submodules') is None:
        value['submodules'] = True
    if "gitlab_name" in value:
        value['git_remote'] = f'git@gitlab.artifex.com:{value["gitlab_name"]}.git'
    else:
        value['git_remote'] = f'git@github.com:{value["github_name"]}.git'


def arg_alias(arg):
    '''
    Returns full name if arg is --<alias>.
    '''
    for fullname, info in g_package_info.items():
        for alias in [fullname] + info['aliases']:
            alias = f'-{alias}' if len(alias) == 1 else f'--{alias}'
            if arg == alias:
                return fullname

def package_alias(package):
    '''
    Returns full name if arg is an alias.
    '''
    for fullname, info in g_package_info.items():
        if package in [fullname] + info['aliases']:
            return fullname
    #return package


def name_info(package):
    ret = g_package_info.get(package)
    if ret:
        return ret
    ret = {
            'github_name': None,
            'git_branch': None,
            'aliases':  list(),
            'submodules': True,
            'order': 0,
            }
    return ret

class Arg:
    '''
    Represents an arg on aptest.py's command line. We add information about
    failed comparisons to the Args object so that we can use them later in
    diagnostics or arg completion.
    '''
    def __init__(self, args_iterator, text):
        self.text = text
        self.args_iterator = args_iterator
        self.pos = args_iterator.pos
    
    def __repr__(self):
        return self.text if isinstance(self.text, str) else 'StopIteration'
        #return f'Arg:{self.text!r}' if isinstance(self.text, str) else 'Arg:StopIteration'
    
    def __eq__(self, rhs):
        ret = self.text == rhs
        if not ret:
            # 9: <tab>  normal completion
            # 33: ! listing alternatives on partial word completion
            # 37: % menu completion
            # 63: ? listing completions after successive tabs
            # 64: @ list completions if the word is not unmodified
            if 1: # or os.environ.get('COMP_TYPE')=='63' or isinstance(self.text, StopIteration) or rhs.startswith(self.text):
                #pipcl.log(f'Adding suggestion {rhs=}. {COMP_TYPE=} {self.text=}')
                self.args_iterator._add_suggestion(rhs)
        return ret
    
    def startswith(self, rhs):
        if self.text is None or isinstance(self.text, StopIteration):
            return False
        return self.text.startswith(rhs)
    
    def as_bool(self):
        ret = None
        if self in ('1', 'true', 'True'):
            ret = True
        if self in ('0', 'false', 'False'):
            ret = False
        if ret is None:
            if isinstance(self.text, StopIteration):
                raise StopIteration
            raise Exception(f'Unrecognised bool value: {self.text!r}')
        return ret
    
    def as_float(self):
        try:
            return float(self.text)
        except Exception:
            self.args_iterator._add_suggestion('<FLOAT>')   # pylint: disable=protected-access
            raise
    
    def as_int(self):
        try:
            return int(self.text)
        except Exception:
            self.args_iterator._add_suggestion('<INT>') # pylint: disable=protected-access
            raise
    
    def as_text(self):
        if isinstance(self.text, str):
            return self.text
        else:
            self.args_iterator._add_suggestion('<TEXT>')    # pylint: disable=protected-access
            raise Exception(f'Expected <text>')
                
        
class Args:
    '''
    Represents all args on aptest.py's command line, and supports iteration
    through these args.
    '''
    def __init__(self, argv, pos=0):
        self.argv = argv
        self.pos = pos
        self.suggestions = list()
        self.current = None
    
    def __next__(self):
        self.suggestions.clear()
        if self.pos == len(self.argv):
            #pipcl.log(f'Returning StopIteration()')
            ret = StopIteration()
        else:
            self.suggestions.clear()
            ret = self.argv[self.pos]
            self.pos += 1
        ret = Arg(self, ret)
        self.current = ret
        return ret
    
    def _add_suggestion(self, suggestion):
        #pipcl.log(f'Adding {suggestion=}', caller=3)
        self.suggestions.append(suggestion)


def _test_completion(COMP_LINE):
    '''
    Internal, runs with COMP_LINE set to mimic completion request from shell.
    '''
    os.environ['COMP_LINE'] = COMP_LINE
    os.environ['COMP_POINT'] = str(len(COMP_LINE))
    os.environ['COMP_TYPE'] = '63'
    return main(shlex.split(COMP_LINE))


def dummy_completion1():
    '''
    >>> _test_completion('./aptest/aptest.py --sdi')
    --sdists
    0
    '''
    
def dummy_completion2():
    '''
    >>> _test_completion('./aptest/aptest.py --sdists')
    1
    true
    True
    0
    false
    False
    0
    '''
    
def dummy_completion3():
    '''
    >>> _test_completion('./aptest/aptest.py -r')   # doctest: +REPORT_UDIFF +ELLIPSIS
    <TEXT>
    0
    '''


def apply_deltas(items, deltas, check=1, aliasfn=lambda name: name):
    '''
    Modifies <items> according to <deltas>.
    
    items: list.
    deltas:
        List of strings. Each is '+', '-' or '', followed by a package name, or
        alias for a package name.
    '''
    #pipcl.log(f'{items=} {deltas=}')
    if deltas and not deltas[0].startswith(('+', '-')):
        del items[:]
        #pipcl.log(f'{items=} {deltas=}')

    for delta in deltas:
        #pipcl.log(f'{delta=}')
        if delta == '-':
            del items[:]
            #pipcl.log(f'{items=}')
        elif delta.startswith('-'):
            try:
                items.remove(aliasfn(delta[1:]))
            except Exception:
                #pipcl.log(f'Failed to remove {delta[1:]=} from {items=}')
                if check:
                    raise
            #pipcl.log(f'{items=}')
        else:
            if delta.startswith('+'):
                delta = delta[1:]
                #pipcl.log(f'{delta=}')
            delta = aliasfn(delta)
            #pipcl.log(f'{delta=}')
            items.append(delta)
            #pipcl.log(f'{items=}')

    
def add_package(state, name, location, args_pos):
    if isinstance(name, Arg):
        name = name.text
    if isinstance(location, Arg):
        if not location.text.startswith(('git:', 'pip:')):
            # Match with local checkouts to help arg completion.
            for path in glob.glob(f'*/.git/'):
                #pipcl.log(f'{path=}')
                d = path[:-6]
                if location == d:
                    break
            #else:
            #    assert 0, f'Directory does not exist: {location}'
        location = location.text
    if name in state.packages:
        pipcl.log(f'Adding second location for {name=} testing only: {location=}')
        state.packages2[name] = (location, args_pos)
        return
    state.packages[name] = (location, args_pos)
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


def get_args(argv):
    '''
    Parses command-line args in <argv> and returns a State instance.

    If we are being called by bash for command-line completion, we reuturn
    None.
    '''
    COMP_LINE = os.environ.get('COMP_LINE')
    COMP_POINT = os.environ.get('COMP_POINT')
    COMP_TYPE = os.environ.get('COMP_TYPE')
    #pipcl.log(f'{COMP_LINE=}')
    #pipcl.log(f'{COMP_POINT=}')
    if COMP_LINE:
        APTEST_COMPLETION_DEBUG = os.environ.get('APTEST_COMPLETION_DEBUG')
        #print(f'{APTEST_COMPLETION_DEBUG=}', file=sys.stderr, flush=1)
        if APTEST_COMPLETION_DEBUG:
            pipcl._log_f = open(APTEST_COMPLETION_DEBUG, 'a')   # pylint: disable=protected-access
        else:
            pipcl._log_f = open('/dev/null', 'a')   # pylint: disable=consider-using-with,protected-access
        pipcl.log(f'{COMP_LINE=}')
        pipcl.log(f'os.environ COMP_*:')
        for n in sorted(os.environ.keys()):
            if n.startswith('COMP_'):
                v = os.environ[n]
                pipcl.log(f'    {n}: {v!r}')
    
    if sys.argv[1:] == ['completion']:
        # Write bash completion script to stdout and exit.
        print(textwrap.dedent(f'''
                _aptest_py() {{
                    COMPREPLY=($( \\
                            COMP_LINE="$COMP_LINE" \\
                            COMP_POINT="$COMP_POINT" \\
                            COMP_TYPE="$COMP_TYPE" \\
                            {os.path.abspath(sys.argv[0])} \\
                            ))
                }}
                complete -F _aptest_py aptest.py
                '''))
        sys.exit()
    
    #if COMP_LINE:
    #    pipcl.log(f'COMP_LINE is set')
    
    class State:
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
    state.cibw_name = 'cibuildwheel'
    state.cibw_pyodide = None
    state.cibw_pyodide_version = None
    state.cibw_skip_add_defaults = True
    state.cibw_test_project = None
    state.cibw_test_project_setjmp = False
    state.clean = list()
    state.commands = list()
    state.devel = False
    state.env_extra = dict()
    state.github_upload = None
    state.gnn_doit = False
    state.gnn_show_graph = None
    state.gnn_show_text = None
    state.gnn_show_paths = list()
    state.gnn_show_select = None
    state.gnn_show_select_root = None
    state.graal = False
    state.huggingface_key_path_abs = None
    state.log_tee = False
    state.os_names = list()
    state.packages2 = dict()   # map from name to location.
    state.packages_build = list() # Sorted list of names.
    state.packages = dict()   # map from name to location.
    state.packages_test = list()  # Sorted list of names.
    state.path_artifex_key = 'artifex-software-ssh-key'
    state.path_huggingface_key = 'huggingface-key'
    state.path_pro_key = 'thirdparty-so-key'
    state.pybind = False
    state.pymupdf4llm_unified = False
    state.pytest_options = ''
    state.pytest_paths = list()
    state.pytest_wrap = None
    state.python = None
    state.python_args_pos = None
    state.remote_arg = None
    state.remote_dir = 'artifex-remote'
    state.remote_do = True
    state.remote_github_workflow_id = None
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
    state.system_packages = True if os.environ.get('GITHUB_ACTIONS') == 'true' else False   # pylint: disable=simplifiable-if-expression
    state.system_site_packages = False
    state.test_extra_packages = list()
    state.test_gnn_cache = False
    state.test_gnn_extra = dict()
    state.test_gnn_limit = None
    state.test_gnn_out = None
    state.test_gnn_push = 0
    state.ticker = 0.5
    state.valgrind = False
    state.venv = 2
    state.venv_name = None
    state.verbose = 0
    state.wheelhouse = 'aptest-wheelhouse'
    
    # Prevent future additions to items in <state>. We can still modify
    # existing values.
    state.freeze()
    
    # Parse args and update the above state. We do this before moving into a
    # venv, partly so we can return errors immediately.
    #
    args_list = list()
    args_list += [argv[0]]
    
    aptest_config_path = os.path.expanduser(f'~/.aptest')
    if os.path.exists(aptest_config_path):
        aptest_config = pipcl.fs_read(aptest_config_path)
        aptest_config = shlex.split(aptest_config)
        args_list += aptest_config
    
    APTEST_options = os.environ.get('APTEST_options', '')
    APTEST_options = shlex.split(APTEST_options)
    args_list += APTEST_options
    
    if COMP_LINE:
        line = COMP_LINE
        if 0: # and COMP_POINT:
            COMP_POINT_int = int(COMP_POINT)
            assert COMP_POINT_int <= len(line)
            line = line[:COMP_POINT_int]
        #pipcl.log(f'{COMP_LINE=}')
        #pipcl.log(f'     {line=}')
        args_list += shlex.split(line)[1:]
        pipcl.log(f'     {args_list=}')
    else:
        args_list += argv[1:]
    args = Args(args_list, 1)
    try:
        i = 0
        while 1:
            args.suggestions.clear()
            try:
                arg = next(args)
                #pipcl.log(f'{arg=}')
            except StopIteration:
                arg = None
                break
            #pipcl.log(f'{arg=} {COMP_LINE=}')
            if isinstance(arg.text, StopIteration):
                if COMP_LINE:
                    pass
                    #arg = Arg(args, None)
                else:
                    arg = None
                    break
            #pipcl.log(f'{arg=}')
            if 0:
                pass

            elif arg == '-a':
                pos1 = args.pos - 1
                _name = next(args).as_text()
                _value = os.environ.get(_name, '')
                pos2 = args.pos
                new_args = shlex.split(_value)
                args.argv[pos1:pos2] = new_args
                args.pos = pos1

            elif arg == '-b':
                _names = next(args).as_text().split(',')
                apply_deltas(state.packages_build, _names, aliasfn=package_alias)

            elif arg == '--build-type':
                state.build_type = next(args)
                assert state.build_type in ('release', 'debug', 'memento')

            elif arg == '--cibw-name':
                state.cibw_name = next(args)

            elif arg == '--cibw-pyodide':
                state.cibw_pyodide = next(args).as_bool()

            elif arg == '--cibw-pyodide-version':
                state.cibw_pyodide_version = next(args)

            elif arg == '--cibw-skip-add-defaults':
                state.cibw_skip_add_defaults = next(args).as_bool()
            
            elif arg == '--clean':
                packages = next(args).as_text().split(',')
                state.clean += packages
            
            elif arg == '--devel':
                state.devel = next(args).as_bool()

            elif arg == '-e':
                _nv = next(args).as_text()
                assert '=' in _nv, f'-e <name>=<value> does not contain "=": {_nv!r}'
                _name, _value = _nv.split('=', 1)
                state.env_extra[_name] = _value
            
            elif arg == '--gnn-doit':
                state.gnn_doit = next(args).as_bool()
            
            elif arg == '--gnn-show-graph':
                state.gnn_show_graph = next(args).as_text()
            
            elif arg == '--gnn-show-path':
                state.gnn_show_paths += next(args).as_text().split(',')
            
            elif arg == '--gnn-show-select':
                state.gnn_show_select = next(args).as_text()
            
            elif arg == '--gnn-show-text':
                state.gnn_show_text = next(args).as_text()
            
            elif arg == '--graal':
                state.graal_arg = args.pos
                state.graal = next(args).as_bool()

            elif arg in ('-h', '--help'):
                state.show_help = True

            elif arg == '-i':
                _name = next(args)
                _location = next(args)
                add_package(state, _name, _location, args.pos - 1)
            
            elif package := arg_alias(arg):
                add_package(state, package, next(args), args.pos - 1)
            
            elif arg == '--log-tee':
                state.log_tee = next(args).as_bool()
                if state.log_tee:
                    APTEST_LOG_TEE = os.environ.get('APTEST_LOG_TEE')
                    if APTEST_LOG_TEE == '0':
                        pass
                    else:
                        # Prevent further logging to date-stamped file in
                        # sub-commands, e.g. if we rerun ourselves inside a
                        # venv.
                        os.environ['APTEST_LOG_TEE'] = '0'
                        pipcl.log_tee()

            elif arg == '-o':
                state.os_names += next(args).as_text().lower().split(',')
                names = ('linux', 'windows', 'darwin', 'openbsd')
                for os_name in state.os_names:
                    assert os_name in names, f'{os_name=} should be one of {names!r}.'

            elif arg == '-r':
                state.remote_arg = args.pos
                state.remote = next(args).as_text()
                #pipcl.log(f'Found -r: {arg=} {state.remote=}')

            elif arg == '--run':
                package = next(args)
                command = next(args)
                state.run_commands.append((package, command))

            elif arg == '-t':
                _names = next(args).as_text().split(',')
                apply_deltas(state.packages_test, _names, aliasfn=package_alias)

            elif arg == '--pybind':
                state.pybind = next(args).as_bool()

            elif arg == '--4llm-unified':
                if next(args).as_bool():
                    state.pymupdf4llm_unified = True
                    g_package_info['pymupdf4llm']['github_name'] = 'ArtifexSoftware/sce'
                    g_package_info['pymupdf4llm']['git_branch'] = 'master'
                    g_package_info['pymupdf4llm']['submodules'] = False
            
            elif arg == '--pytest':
                state.pytest_options = next(args).as_text()

            elif arg == '--pytest-path':
                state.pytest_paths.append(next(args).as_text())

            elif arg == '--pytest-wrap':
                state.pytest_wrap = next(args)
                assert state.pytest_wrap in ('gdb', 'valgrind', 'helgrind')

            elif arg == '--python':
                state.python_args_pos = args.pos
                state.python = next(args).as_text()

            elif arg.startswith('--release-'):
                args.suggestions.clear()
                pos = args.pos - 1
                assert pos == 1 and len(args.argv) == 2, f'{pos=} {len(sys.argv)=} args `--release-*` must be only arg.'
                if arg == '--release-1':
                    new_args = '-r @github -u 1 -p git: -P git: -l git: cibw --sdists 1'
                elif arg == '--release-2':
                    new_args = '-r @github -u 1 -p git: -P git: -l git: cibw -o linux -e CIBW_ARCHS_LINUX=aarch64 -e "CIBW_BUILD=cp310*"'
                elif arg == '--release-3':
                    new_args = '-r @github -u 1 -p git: cibw -o windows -e CIBW_ARCHS_WINDOWS=x86 --cibw-skip-add-defaults 0'
                elif arg == '--release-4':
                    new_args = '-r @github -u 1 -p git: cibw -o linux -e "CIBW_BUILD=cp310-musllinux_x86_64" --cibw-skip-add-defaults 0'
                elif arg == '--release-5':
                    new_args = '-r @github -p git: cibw --cibw-pyodide 1 -o linux'
                else:
                    assert 0, f'Unrecognised {arg=}, should be one of --release-1, --release-2, --release-3.'
                new_args = shlex.split(new_args)
                args.argv[pos:] = new_args
                args.pos = pos
                #pipcl.log(f'{args.pos=}: {args.argv=}')
                continue

            elif arg == '--remote-do':
                state.remote_do = next(args).as_bool()

            elif arg == '--remote-github-workflow-id':
                state.remote_github_workflow_id = next(args).as_text()

            elif arg == '--remote-github-yml':
                state.remote_github_yml = next(args).as_text()
                assert state.remote_github_yml.endswith('.yml')

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
                state.remote_rsync_wsl = next(args).as_bool()

            elif arg == '--sdists':
                state.sdists = next(args).as_bool()

            elif arg == '--system-site-packages':
                state.system_site_packages = next(args).as_bool()

            elif arg == '--swig':
                state.swig = next(args).as_text()

            elif arg == '--swig-quick':
                state.swig_quick = next(args).as_bool()

            elif arg == '--system-packages':
                state.system_packages = int(next(args))

            elif arg == '--system-site-packages':
                state.system_site_packages = next(args).as_bool()

            elif arg == '--test-extra-packages':
                state.test_extra_packages += next(args).as_text().split(',')
            
            elif arg == '--test-gnn-cache':
                state.test_gnn_cache = next(args).as_bool()
                
            elif arg == '--test-gnn-extra':
                nv = next(args).as_text()
                n, v = nv.split('=', 1)
                state.test_gnn_extra[n] = v

            elif arg == '--test-gnn-limit':
                state.test_gnn_limit = next(args).as_int()

            elif arg == '--test-gnn-out':
                state.test_gnn_out = next(args).as_text()

            elif arg == '--test-gnn-push':
                state.test_gnn_push = next(args).as_bool()

            elif arg == '--ticker':
                state.ticker = next(args).as_float()

            elif arg == '-u':
                state.github_upload = next(args).as_int()

            elif arg == '-v':
                state.venv = next(args).as_int()
                assert state.venv in (0, 1, 2, 3), f'Invalid {state.venv=} should be 0, 1, 2 or 3.'
            
            elif arg == '--venv-name':
                state.venv_name = next(args).as_text()
            
            elif arg == '-V':
                state.verbose += 1

            elif arg.startswith('-'):
                assert 0, f'Unrecognised option: {arg=}.'

            elif arg in (
                    'build',
                    'cibw',
                    'gnn-download',
                    'gnn-show',
                    'gnn-select-show',
                    'gnn-train',
                    'run',
                    'populate',
                    'test',
                    'test-gnn',
                    'test-gnn-devel',
                    'test-gnn-pymupdf4llm',
                    'test-gnn-pymupdf_layout',
                    ):
                state.commands.append(arg)

            else:
                if isinstance(arg.text, StopIteration):
                    break
                #pipcl.log(f'{arg=}')
                #pipcl.log(f'{args.suggestions=}')
                assert 0, f'Unrecognised command: {arg=}.'
            
            #pipcl.log(f'End of loop: {args.current=} {args.suggestions=}')
            #if isinstance(args.current.text, StopIteration):
            #    raise args.current.text

    except Exception as e:
        # We write out detailed information about the error, including
        # information about what args would have been valid.
        if COMP_LINE:
            pipcl.log(f'{backtrace.show(file=str)}')
            pipcl.log(f'Exception: {e}')
            pipcl.log(f'{args.argv=}')
            pipcl.log(f'{args.pos=}')
            pipcl.log(f'{args.suggestions=}')
            pipcl.log(f'{arg=}')
            pipcl.log(f'{COMP_LINE=}')
            pipcl.log(f'{COMP_POINT=}')
            pipcl.log(f'{COMP_TYPE=}')
            try:
                # COMP_TYPE
                # 9: <tab>  normal completion
                # 33: ! listing alternatives on partial word completion
                # 37: % menu completion
                # 63: ? listing completions after successive tabs
                # 64: @ list completions if the word is not unmodified
                #
                for suggestion in args.suggestions:
                    #if COMP_TYPE == '63' or suggestion.startswith(arg):
                    if isinstance(args.current.text, StopIteration):
                        print(suggestion)
                    elif suggestion.startswith(args.current.text):
                        pipcl.log(f'Writing out {suggestion=}')
                        print(suggestion)
                    sys.stdout.flush()
                pipcl.log(f'Calling sys.exit()')
                #sys.exit()
                return None, None
                
            except Exception:
                pipcl.log(f'completion: error: {traceback.format_exc()}')
                #sys.exit(1)
                #return 1
            sys.exit(1)
        
        elif arg is not None:
            # Print command line with caret showing where error occurred.
            #pipcl.log(f'{args.current=}')
            if state.devel:
                backtrace.show()
            for i, arg in enumerate(args.argv):
                sys.stdout.write(f'{" " if i else ""}{shlex.quote(arg)}')
            sys.stdout.write('\n')
            for i, arg in enumerate(args.argv):
                if i:
                    sys.stdout.write(' ')
                if not isinstance(args.current.text, StopIteration) and i+1 == args.pos:
                    sys.stdout.write('^' * len(arg))
                    break
                sys.stdout.write(' ' * len(shlex.quote(arg)))
            if isinstance(args.current.text, StopIteration):
                sys.stdout.write('^')
            sys.stdout.write('\n')
            if isinstance(e, StopIteration):
                pipcl.log(f'Ran out of arguments.')
            if args.suggestions:
                pipcl.log(f'Expected one of:')
                for suggestion in args.suggestions:
                    pipcl.log(f'    {suggestion}')
            else:
                pipcl.log(f'(No suggestions.)')
                raise
            sys.exit(1)
            #return 1
        else:
            backtrace.show()
            sys.exit(1)
            #return 1
    
    if COMP_LINE:
        pipcl.log(f'completion: no error. {args.suggestions=}')
        pipcl.log(f'{sys.argv=}')
        for suggestion in args.suggestions:
            print(suggestion)
        sys.exit(1)
        #return 0
    
    return args, state


def do_remote_github(state, argv):
    pipcl.run('pip install requests')
    branch = f'aptest-{os.environ["USER"]}'    # -{time.strftime("%F-%T")}'
    pipcl.log(f'{branch=}.')

    if state.remote_github_workflow_id:
        # Wait for existing workflow instead of creating a new one.
        workflow_id = state.remote_github_workflow_id
        remote_github_workflow_package = 'aptest'
        info = name_info(remote_github_workflow_package)
    else:
        # Push ourselves to Git.
        git_push(g_root, 'git@github.com:ArtifexSoftware/aptest.git', branch, state)

        # Push specified local package repository to Github and update args to
        # point to new location.
        for package_name, (package_location, args_pos) in list(state.packages.items()) + list(state.packages2.items()):
            if not package_location.startswith(('git:', 'pip:')):
                # Push to a Github branch and update argv[] to refer to this
                # Github branch.
                info = name_info(package_name)
                pipcl.log(f'{package_name=}.')
                pipcl.log(f'{info["git_remote"]=}.')
                git_push(package_location, info["git_remote"], branch, state)
                argv[args_pos] = f'git:-b {branch} {info["git_remote"]}'

        if state.remote_github_yml:
            # Run .yml directly.
            pipcl.log(f'Running .yml instead of aptest.py: {state.remote_github_yml}')
            if not state.packages:
                # Run on aptest.
                info = name_info('aptest')
            elif len(state.packages) == 1:
                for package_name, (package_location, args_pos) in state.packages.items():
                    pass
                info = name_info(package_name)
            else:
                assert 0, 'Running yml directly requires exactly zero or one package, but {len(state.packages)=}.'
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
                    f'https://api.github.com/repos/{info["github_name"]}',
                    state.remote_github_yml,
                    data,
                    )
        else:
            # Run ourselves on Github using test.yml, passing argv.
            info = name_info('aptest')
            args = shlex.join(argv[1:])
            if not state.verbose:
                # Run with verbose on Github, e.g. to show os.environ etc.
                args += ' -V'
            data = dict(
                    ref = branch,
                    inputs = dict(args=args),
                    )
            workflow_id = github.gh_run_workflow(
                    f'https://api.github.com/repos/{info["github_name"]}',
                    'test.yml',
                    data,
                    )

    assert isinstance(workflow_id, str)
    url = f'https://api.github.com/repos/{info["github_name"]}'
    #pipcl.log(f'Calling github.gh_workflow_download_multiple() with {url=} {workflow_id=}.')
    github.gh_workflow_download_multiple(
            url,
            workflow_id,
            #extra_wheels=upload_extra_wheels,
            upload='pypi' if state.github_upload else None,
            )

def do_remote(state, argv):
    remote = state.remote
    remote_dir = state.remote_dir
    verbose = 1
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
        sync_artifex_software_ssh_key = False

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
            if package_location.startswith('git:'):
                sync_artifex_software_ssh_key = True

        # Sync aptest itself.
        if sync2(g_root):
            git_paths.append(g_root)

        # Sync Artifex github key.
        if sync_artifex_software_ssh_key:
            if os.path.isfile(state.path_artifex_key):
                sync2(state.path_artifex_key)
            else:
                pipcl.log(
                        f'## Warning: may not be able to remote'
                        f' clone/update pro or layout checkouts'
                        f' because not a file: {state.path_artifex_key}'
                        )

        # Sync Huggingface key.
        if 'gnn' in state.commands:
            if os.path.isfile(state.path_huggingface_key):
                sync2(state.path_huggingface_key)
            else:
                pipcl.log(
                        f'## Warning: may not be able to remote'
                        f' use Huggingface because not a file:'
                        f' {state.path_huggingface_key}'
                        )

        # Sync pymupdfpro build key.
        if 'pymupdfpro' in state.packages_build:
            if os.path.isfile(state.path_pro_key):
                sync2(state.path_pro_key)
            else:
                pipcl.log(
                        f'## Warning: may not be able to remote build'
                        f' SmartOffice because not a file:'
                        f' {state.path_artifex_key}'
                        )
            sync2(state.path_pro_key)

        # Run remote command.
        #
        remote_command = f'cd {remote_dir} && '
        for git_path in git_paths:
            # We exclude *.tar.gz to avoid pymupdf re-downloading mupdf .tar.gz file.
            remote_command += f'(cd {git_path} && git clean -e "*.tar.gz" -f) && '
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

        tee_simple = f'out-{remote}'
        tee = f'{tee_simple}-{time.strftime("%F-%H-%M-%S")}'
        try:
            pipcl.run(
                    command,
                    prefix=f'{label}: ',
                    out='log',
                    tee=tee,
                    ticker=state.ticker,
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
                remote,
                remote_dir,
                f'{state.wheelhouse}/',
                f'{state.wheelhouse}/',
                ssh_command=ssh_command,
                filters=filters,
                )
    if 1:
        # Copy test-gnn-*.json back to local machine.
        sync_reverse(
                remote,
                remote_dir,
                './',
                './',
                ssh_command=ssh_command,
                filters = '"--include=test-gnn-*.json" "--exclude=*"',
                )


def build_sdist(state, package, directory):
    if package == 'pymupdf':
        pipcl.run(
                f'cd {directory}'
                    f' && python setup.py -d {os.path.abspath(state.wheelhouse)} sdist',
                prefix='sdist {package}: ',
                )


def do_build(state):
    # We use `pip --extra-index-url {pip_index_url}` so that pip
    # finds prerequisite wheels in state.wheelhouse.
    pip_index_url = f'file://{os.path.abspath(state.wheelhouse)}/simple'
    # pip fails if pip_index_url contains back-slashes, with
    # `ERROR: Could not install packages due to an OSError: [Errno
    # 13] Permission denied:...`.
    pip_index_url = pip_index_url.replace('\\', '/')
    if 'mupdf' in state.packages:
        directory = _get_local('mupdf', state)
        if directory:
            state.env_extra['PYMUPDF_SETUP_MUPDF_BUILD'] = os.path.abspath(directory)
    if 'mupdf' in state.packages and 'mupdf' not in state.packages_build:
        PYMUPDF_SETUP_MUPDF_REBUILD = '0'
        pipcl.log(f'Setting {PYMUPDF_SETUP_MUPDF_REBUILD=}')
        state.env_extra['PYMUPDF_SETUP_MUPDF_REBUILD'] = PYMUPDF_SETUP_MUPDF_REBUILD
    
    package_to_wheel = dict()
    
    def do_package(package):
        ret_wheel = None
        location, _args_pos = state.packages[package]
        if not location:
            return ret_wheel
        if package == 'aptest':
            return ret_wheel

        new_files = pipcl.NewFiles(f'{state.wheelhouse}/{package}*.whl')
        
        if location.startswith('pip:'):
            assert package != 'mupdf', f'Not a package on pypi.org: {package}'
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
            pipcl.run(f'pip wheel --no-cache-dir -w {state.wheelhouse} {name}')
            ret_wheel = new_files.get_one()
            pipcl.run(f'pip install -v {name}')
        else:
            directory = _get_local(package, state)

            if package == 'pymupdf4llm' and not state.pymupdf4llm_unified:
                # setup.py is in subdirectory pymupdf4llm/.
                directory += '/pymupdf4llm'
            directory_abs = os.path.abspath(directory)
            pipcl.log(f'{package=} {directory=}')
            if package == 'mupdf':
                state.env_extra['PYMUPDF_SETUP_MUPDF_BUILD'] = directory_abs
                # fixme: be able to set to '' for system install?
            elif package == 'smartoffice':
                state.env_extra['PYMUPDFPRO_SETUP_SOT'] = directory_abs
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

                if state.build_type:
                    if package == 'pymupdf':
                        state.env_extra['PYMUPDF_SETUP_MUPDF_BUILD_TYPE'] = state.build_type
                    if package == 'pymupdfpro':
                        state.env_extra['PYMUPDFPRO_SETUP_BUILD_TYPE'] = state.build_type
                    if package == 'pymupdf_layout':
                        state.env_extra['PYMUPDF_LAYOUT_SETUP_BUILD_TYPE'] = state.build_type

                pipcl.run(
                        #f'pip wheel -v --extra-index-url {pip_index_url} --no-cache-dir -w {state.wheelhouse} {directory_abs}',
                        f'pip wheel -v --extra-index-url {pip_index_url} -w {state.wheelhouse} {directory_abs}',
                        env_extra=state.env_extra,
                        prefix=f'build {package}: ',
                        )
                ret_wheel = new_files.get_one()

                if package == 'pymupdf':
                    # Set PYMUPDF_SETUP_VERSION so subsequent builds are configured
                    # for the PyMuPDF we have just built.
                    PYMUPDF_SETUP_VERSION = os.path.basename(ret_wheel).split('-')[1]
                    state.env_extra['PYMUPDF_SETUP_VERSION'] = PYMUPDF_SETUP_VERSION
                    pipcl.log(f'### Have set {PYMUPDF_SETUP_VERSION=}')
                pipcl.run(
                        #f'pip install -v --extra-index-url {pip_index_url} --no-cache-dir {wheel}',
                        f'pip install -v --extra-index-url {pip_index_url} {ret_wheel}',
                        env_extra=state.env_extra,
                        prefix=f'install {package}: ',
                        )
                
            if package in state.clean:
                directory = _get_local(package, state)
                with pipcl.LogPrefix(f'{package=}: git clean -n: '):
                    pipcl.log(f'Showing post-build git-clean for {package=}.')
                    pipcl.run(f'cd {directory} && git clean -ndx')
    
        return ret_wheel

    # We install packages in reverse order (e.g. pymupdf_layout before pymupdf)
    # so that packages specified to aptest override any package prerequisites.
    #
    # For example with `-p pip:==1.26.3 --layout pip:=1.26.5`, installation of
    # pymupdf_layout will install prerequisite pymupdf-1.26.5, which we then
    # override with installation of pymupdf-1.26.3.
    #
    
    for package in state.packages_build:
        wheel = do_package(package)
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
        pipcl.run(f'pip install --no-deps {wheel}')


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

    for package in state.packages_build:
        pipcl.log(f'{package=}')
        directory = _get_local(package, state)
        
        if not directory:
            # location is pip.
            pipcl.log(f'Unable to process with cibuildwheel because location is pip: {package=} and now second location')
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
            build_sdist(state, package, directory)

        # Tell cibuildwheel how to test <package>.
        if package in state.packages_test:
            CIBW_TEST_COMMAND = f'pip install --upgrade pytest && pytest'
            if state.pytest_options:
                CIBW_TEST_COMMAND += f' {state.pytest_options}'
            CIBW_TEST_COMMAND += f' {{project}}/tests'
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
                env_extra['PYMUPDFPRO_SETUP_SOT_KEY_PATH'] = \
                        f'{prefix}{os.path.abspath(PYMUPDFPRO_SETUP_SOT_KEY_PATH)}'
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

        # Ensure that when cibuildwheel runs pip to
        # install prerequisite packages, it also looks in
        # state.wheelhouse. PIP_EXTRA_INDEX_URL is equivalent to
        # pip's `--extra-index-url`.
        env_extra['PIP_EXTRA_INDEX_URL'] = \
                f'file://{prefix}{os.path.abspath(state.wheelhouse)}/simple'.replace('\\', '/')

        env_extra['CIBW_BUILD'] = CIBW_BUILD

        # Pass all the environment variables we have set in
        # state.env_extra, to Linux docker. Note that this will
        # miss any settings in the original environment.
        CIBW_ENVIRONMENT_PASS_LINUX = env_extra.keys()
        CIBW_ENVIRONMENT_PASS_LINUX = list(CIBW_ENVIRONMENT_PASS_LINUX)
        CIBW_ENVIRONMENT_PASS_LINUX.append('PYMUPDFPRO_SETUP_SOT_KEY')  # This can be set in os.environ.
        # Some tests look at GITHUB_ACTIONS e.g. if known to fail on Github.
        CIBW_ENVIRONMENT_PASS_LINUX.append('GITHUB_ACTIONS')
        CIBW_ENVIRONMENT_PASS_LINUX.sort()
        CIBW_ENVIRONMENT_PASS_LINUX = ' '.join(CIBW_ENVIRONMENT_PASS_LINUX)
        env_extra['CIBW_ENVIRONMENT_PASS_LINUX'] = CIBW_ENVIRONMENT_PASS_LINUX

        pipcl.run(
                f'cd {directory} && cibuildwheel{cibw_pyodide_args}'
                    f' --output-dir {os.path.abspath(state.wheelhouse)}',
                env_extra=env_extra,
                prefix=f'cibw {package}: ',
                )

        pipcl.run(f'ls -ld {state.wheelhouse}/*')
        pipcl.run(f'piprepo build {state.wheelhouse}')

        if 0:
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
                    github._gh_download(url, path, gh=0)    # pylint: disable=protected-access
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
        out_text = f'gnn-text-{time.strftime("%Y-%m-%d-%H-%M-%S")}.txt'
        #out_text_simple = f'gnn-text.txt'
    else:
        out_text = state.gnn_show_text
        #out_text_simple = None

    if state.gnn_show_graph == '':
        out_graph = None
        out_graph_simple = None
    elif state.gnn_show_graph is None:
        out_graph = f'gnn-graph-{time.strftime("%Y-%m-%d-%H-%M-%S")}.html'
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
        

def do_test_gnn(state, command):
    layout_location = _get_local('pymupdf_layout', state)

    def run(command):
        t = time.time()
        try:
            pipcl.run(command)
        finally:
            t = time.time() - t
            pipcl.log(f'Command took {pipcl._duration(t)}.')    # pylint: disable=protected-access

    if command == 'test-gnn':
        run(f'cd {layout_location} && {sys.executable} eval/eval_gnn.py --pdf_dir ../datasets/DocLayNet/PDF')

    elif command == 'test-gnn-pymupdf_layout':
        run(f'cd {layout_location} && {sys.executable} eval/eval_pymupdf_layout.py --pdf_dir ../datasets/DocLayNet/PDF')

    elif command == 'test-gnn-pymupdf4llm':
        pipcl.run(f'pip install tqdm')
        sys.path.insert(0, f'{layout_location}/eval')
        try:
            import eval_util    # pylint: disable=import-error
            import eval_pymupdf4llm # pylint: disable=import-error
        finally:
            del sys.path[0]
        out_dir = 'test-gnn-devel'
        pipcl.fs_ensure_empty_dir(out_dir)
        vis_pdf_dir = f'{out_dir}/vis'
        pipcl.fs_ensure_empty_dir(vis_pdf_dir)
        result_csv_path = f'{out_dir}/result.csv'
        pdf_dirs = ['datasets/DocLayNet/PDF']
        gt_dir = f'{layout_location}/eval/resources/gt'
        det_func = eval_pymupdf4llm.det_func

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
        ret['state']['det_func'] = dict()
        ret['state']['det_func']['__name__'] = det_func.__name__
        ret['state']['det_func']['__module__'] = det_func.__module__
        ret['state']['pdf_dirs'] = pdf_dirs
        ret['state']['gt_dir'] = gt_dir
        ret['state']['limit'] = state.test_gnn_limit
        
        for n, v in state.test_gnn_extra.items():
            ret[n] = v

        ret['packages'] = dict()
        for package, (location, _) in state.packages.items():
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

        t_start = time.time()
        # Older pymupdf_layout's eval_util.evaluate_detection()
        # does not have <limit> arg, so we are careful to not pass
        # in <limit> if not specified.
        kwargs = dict(
                pdf_dirs=pdf_dirs,
                result_csv_path=result_csv_path,
                gt_dir=gt_dir,
                vis_error_count=0,
                vis_pdf_dir=vis_pdf_dir,
                )
        if state.test_gnn_limit:
            kwargs['limit'] = state.test_gnn_limit
        
        name_t = time.strftime('%Y-%m-%d-%H-%M-%S', time.gmtime(t_start))
        name = f'test-gnn-pymupdf4llm-{name_t}.json'
        
        out_json = None
        if state.test_gnn_cache:
            # See whether an identical run has already been done.
            import copy
            ret0 = copy.deepcopy(ret)
            ignore_keys = ('results', 't_start', 't_duration', 'pip-list')
            for key in ignore_keys:
                ret0.pop(key, None)
            for path in glob.glob(f'test-gnn-*.json'):
                with open(path) as f:
                    r = json.load(f)
                for key in ignore_keys:
                    r.pop(key, None)
                pipcl.log(f'Comparing with {path=}.')
                equal = dicts_equal(r, ret0)
                if equal:
                    pipcl.log(f'Found matching previous run: {path=}.')
                    #os.symlink(path, name)
                    out_json = path
                    break
            if not out_json:
                pipcl.log(f'Did not find any matching previous run.')

        if not out_json:
            results = eval_util.evaluate_detection(det_func, **kwargs)
            t_duration = time.time() - t_start
            assert len(results) == 1
            results = results[0]

            ret['results'] = results
            ret['t_start'] = t_start
            ret['t_duration'] = t_duration

            pipcl.log(f'Results are:\n{json.dumps(ret, indent="    ")}')

            name_t = time.strftime('%Y-%m-%d-%H-%M-%S', time.gmtime(t_start))
            out_json = f'test-gnn-pymupdf4llm-{name_t}.json'
            
            with open(out_json, 'w') as f:
                json.dump(ret, f, indent='    ', sort_keys=1)
            pipcl.log(f'Have written results to {out_json=}.')

            if state.test_gnn_push:
                push_results(name, state.env_extra)
            else:
                pipcl.log(f'Not pushing results to PyMuPDF-performance-results: {name=}')
        
        out_json_simple = 'test-gnn.json'
        pipcl.fs_remove(out_json_simple)
        os.symlink(out_json, out_json_simple)
        if state.test_gnn_out:
            pipcl.fs_remove(state.test_gnn_out)
            os.symlink(out_json, state.test_gnn_out)

    else:
        assert 0, f'Unrecognised command: {command=}'


def do_test(state):
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

    if state.test_extra_packages:
        pipcl.run(f'pip install {" ".join(state.test_extra_packages)}')

    for package in state.packages_test:
        location, _ = state.packages[package]
        if not location:
            continue
        if package == 'mupdf' or package == 'smartoffice':
            continue
        directory = _get_local(package, state, test=1)
        if not directory:
            continue
        if package == 'langchain_pymupdf_layout':
            command = f'{sys.executable} {directory}/simple_test.py'
            e = pipcl.run(
                    command,
                    env_extra=state.env_extra,
                    prefix=f'langchain_pymupdf_layout simple_test.py: ',
                    check=0,
                    )
            pipcl.log(f'langchain_pymupdf_layout command returned {e=}.')
        else:
            command = f'pytest'
            if state.pytest_options:
                command += f' {state.pytest_options}'
            if state.pytest_paths:
                for path in state.pytest_paths:
                    command += f' {directory}/{path}'
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
                command += f' {directory}/tests'
            
            if package == 'pymupdf4llm' and state.pymupdf4llm_unified:
                # Extra requirements for testing unified pymupdf4llm+layout. We
                # before this unification we didn't use pytest to run 4llm
                # tests..
                pipcl.run(f'pip install llama_index')
                pipcl.run(f'pip install pytest-asyncio')
                
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


def main(argv):
    
    if github_workflow_unimportant():
        return
    
    args, state = get_args(argv)
    if args is None:
        # COMP_LINE.
        return 0
        
    if not state.devel:
        # Don't output file:line etc, just output elapsed time.
        pipcl.g_log_format = '[+%d]: '
    
    if state.verbose:
        pipcl.show_system()
        
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
        python_version = pipcl.run(f'{state.python} -c "import platform; print(platform.python_version())"', capture=1)
        python_version_tuple = tuple(python_version.split('.'))
        if platform.python_version_tuple()[:2] == python_version_tuple[:2]:
            pipcl.log(f'Already running on required python. {platform.python_version_tuple()=} {python_version_tuple=}')
        else:
            pipcl.log(f'{state.python=}: rerunning because {platform.python_version_tuple()[:2]=} != {python_version_tuple[:2]=}')
            argv = args.argv[:]
            argv[state.python_args_pos] = ''  # _pylint: disable=used-before-assignment
            e = pipcl.run(f'{state.python} {shlex.join(argv[1:])}', check=0)
            sys.exit(e)
            
    # Rerun ourselves in a venv if necessary.
    if (not state.remote and state.commands) or state.remote == '@github':
        if state.venv:
            # Rerun ourselves inside a venv if not already in a venv.
            if venv_in(state.venv_name):
                pipcl.log(f'Already in venv; {sys.prefix=} {state.venv_name=}.')
            else:
            
                if not state.remote and state.graal:
                    if 'cibw' in state.commands:
                        # We don't create graal/pyenv so wheel/build commands
                        # will not work.
                        assert 'build' not in state.commands
                if not state.remote and state.graal and 'cibw' not in state.commands:
                    # Re-run ourselves in a pyenv/Graal venv.
                    # 2025-07-24: We need the latest pyenv.
                    graalpy = 'graalpy-24.2.1'
                    venv_name = f'venv-aptest-{graalpy}'
                    pyenv_dir = f'{g_root_abs}/pyenv-git'
                    os.environ['PYENV_ROOT'] = pyenv_dir
                    os.environ['PATH'] = f'{pyenv_dir}/bin:{os.environ["PATH"]}'
                    os.environ['PIPCL_GRAAL_PYTHON'] = sys.executable
                    
                    if state.venv >= 3:
                        shutil.rmtree(venv_name, ignore_errors=1)
                    if state.venv == 1 and os.path.exists(pyenv_dir) and os.path.exists(venv_name):
                        pipcl.log(f'{state.venv=} and {venv_name=} already exists so not building pyenv or creating venv.')
                    else:
                        pipcl.git_get(pyenv_dir, remote='https://github.com/pyenv/pyenv.git', branch='master')
                        pipcl.run(f'cd {pyenv_dir} && src/configure && make -C src')
                        pipcl.run(f'which pyenv')
                        pipcl.run(f'pyenv install -v -s {graalpy}')
                        pipcl.run(f'{pyenv_dir}/versions/{graalpy}/bin/graalpy -m venv {venv_name}')
                    e = pipcl.run(f'. {venv_name}/bin/activate && python {shlex.join(sys.argv)}',
                            check=False,
                            prefix='{venv_name}: ',
                            )
                else:
                    # Re-run ourselves in a Python venv.
                    pipcl.log(f'{state.venv=}')
                    Py_GIL_DISABLED = sysconfig.get_config_var('Py_GIL_DISABLED')
                    t = '-t' if Py_GIL_DISABLED else ''
                    if state.venv_name:
                        venv_name = state.venv_name
                    else:
                        venv_name = f'venv-aptest-{platform.python_version()}{t}-{int.bit_length(sys.maxsize+1)}'
                    e = venv_run(
                            sys.argv,
                            venv_name,
                            recreate=(state.venv>=2),
                            clean=(state.venv>=3),
                            makelink='venv-aptest',
                            )
                sys.exit(e)
    
    os.makedirs(state.wheelhouse, exist_ok=1)
        
    # Set environment variable values in <state.env_extra> to give access to
    # required git repositories.
    #
    paths_to_delete = list()
    if 1:
        # Allow access to private github.com/ArtifexSoftware/* repositories.
        
        # On Github ARTIFEX_SOFTWARE_SSH_KEY is set from repository secret.
        ARTIFEX_SOFTWARE_SSH_KEY = os.environ.get('ARTIFEX_SOFTWARE_SSH_KEY')
        if ARTIFEX_SOFTWARE_SSH_KEY:
            # Write to temp file.
            temp_key_path = f'{state.path_artifex_key}-tmp'
            paths_to_delete.append(temp_key_path)
            fs_write_key(temp_key_path, ARTIFEX_SOFTWARE_SSH_KEY)
            state.ssh_key_path_abs = os.path.abspath(temp_key_path)
        elif os.path.isfile(state.path_artifex_key):
            state.ssh_key_path_abs = os.path.abspath(state.path_artifex_key)
        else:
            pipcl.log(
                    f'## May not be able to clone/update/test pymupdfpro/layout'
                    f' because ARTIFEX_SOFTWARE_SSH_KEY unset and file'
                    f' {state.path_artifex_key!r} does not exist'
                    )
            state.ssh_key_path_abs = None
        if state.ssh_key_path_abs:
            # We need to use forward slashes on Windows.
            ssh_key_path_abs = state.ssh_key_path_abs.replace('\\', '/')
            GIT_SSH_COMMAND = f'ssh -i {ssh_key_path_abs} -o StrictHostKeyChecking=no'
            state.env_extra['GIT_SSH_COMMAND'] = GIT_SSH_COMMAND
            #pipcl.log(f'Using {GIT_SSH_COMMAND=}.')
        
        HUGGINGFACE_KEY = os.environ.get('ARTIFEX_HUGGINGFACE_KEY')
        if HUGGINGFACE_KEY:
            # Write to temp file.
            temp_key_path = f'{state.path_huggingface_key}-tmp'
            paths_to_delete.append(temp_key_path)
            fs_write_key(temp_key_path, HUGGINGFACE_KEY)
            state.huggingface_keys_path_abs = os.path.abspath(temp_key_path)
        elif os.path.isfile(state.path_huggingface_key):
            state.huggingface_key_path_abs = os.path.abspath(state.path_huggingface_key)

    if 'pymupdfpro' in state.packages_build:
        # The SmartOffice build requires remote git access.
        
        # On Github PYMUPDFPRO_SETUP_SOT_KEY is set from repository secret.
        PYMUPDFPRO_SETUP_SOT_KEY = os.environ.get('PYMUPDFPRO_SETUP_SOT_KEY')
        if PYMUPDFPRO_SETUP_SOT_KEY:
            pipcl.log(f'PYMUPDFPRO_SETUP_SOT_KEY is set.')
        else:
            # With non-github builds we rely on this file existing.
            PYMUPDFPRO_SETUP_SOT_KEY_PATH = os.path.abspath(state.path_pro_key)
            if os.path.isfile(PYMUPDFPRO_SETUP_SOT_KEY_PATH):
                state.env_extra['PYMUPDFPRO_SETUP_SOT_KEY_PATH'] = PYMUPDFPRO_SETUP_SOT_KEY_PATH
                pipcl.log(f'Using {PYMUPDFPRO_SETUP_SOT_KEY_PATH=}.')
            else:
                pipcl.log(
                        f'## May not be able to build pymupdfpro because'
                        f' PYMUPDFPRO_SETUP_SOT_KEY unset and file'
                        f' {PYMUPDFPRO_SETUP_SOT_KEY_PATH!r} does not exist'
                        )
    
    if state.remote:  # pylint: disable=too-many-nested-blocks
        argv = args.argv[:]
        argv[state.remote_arg] = ''   # Change `-r github` to `-r ''`. # pylint: disable=used-before-assignment.
        
        if state.remote == '@github':
            return do_remote_github(state, argv)
        else:
            # Use rsync/ssh to sync to/run on remote machine.
            return do_remote(state, argv)
        
    if not state.commands and not state.remote_github_workflow_id:
        pipcl.log(f'## Warning, no commands specified so nothing to do.')
    
    if state.run_commands and 'run' not in state.commands:
        pipcl.log(f'## Warning, --run was specified but no `run` command.')
    
    # Clone/update/build swig if specified.
    swig_binary = pipcl.swig_get(state.swig, state.swig_quick)
    #pipcl.log(f'{state.swig=}')
    #pipcl.log(f'{swig_binary=}')
    if swig_binary:
        # Prevent individual builds from installing default swig.
        swig_binary = os.path.abspath(swig_binary)
        state.env_extra['PYMUPDF_SETUP_SWIG'] = swig_binary
        state.env_extra['PYMUPDFPRO_SETUP_SWIG'] = swig_binary
        state.env_extra['PYMUPDF_LAYOUT_SETUP_SWIG'] = swig_binary
    
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
            
            with pipcl.LogPrefix(f'{command}: '):
            
                if command in ('build', 'cibw'):
                    # 2025-11-14: piprepo seems to also required setuptools.
                    pipcl.run(f'pip install --upgrade piprepo setuptools')
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
                            f'cd gnn && {sys.executable} {layout_location_abs}/train/tools/test_gnn.py {layout_location_abs}/train/cfgs/config.yaml',
                            env_extra=dict(PYTHONPATH=layout_location_abs),
                            )

                elif command == 'populate':
                    for package in state.packages_build:
                        _location, _args_pos = state.packages[package]
                        if 1: # location.startswith('git:'):
                            directory = _get_local(package, state)
                            pipcl.log(f'Local directory for {package=} is: {directory!r}')

                elif command.startswith('test-gnn'):
                    do_test_gnn(state, command)

                elif command == 'run':
                    for package, command in state.run_commands:
                        directory = _get_local(package, state)
                        pipcl.run(f'cd {directory} && {command}')

                elif command == 'test':
                    do_test(state)

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
        info = name_info(package)
        local = f'aptest-git-{package}'
        with pipcl.LogPrefix(f'{local}: '):
            env_extra = state.env_extra
            if package == 'smartoffice' and state.path_pro_key and os.path.isfile(state.path_pro_key):
                GIT_SSH_COMMAND = f'ssh -i {os.path.abspath(state.path_pro_key)} -o StrictHostKeyChecking=no'
                env_extra = env_extra | dict(GIT_SSH_COMMAND=GIT_SSH_COMMAND)
            directory = pipcl.git_get(
                    local,
                    remote=info['git_remote'],
                    branch=info['git_branch'],
                    text=location,
                    env_extra=env_extra,
                    submodules=info['submodules'],
                    )
    else:
        directory = location
    
    if not test:
        if package in state.clean:
            pipcl.run(f'cd {directory} && git clean -fdx')
    
    # Show information about the checkout, regardless of where it came from.
    sha, comment, diff, branch = pipcl.git_info(directory)
    with pipcl.LogPrefix(f'Local checkout {directory}: '):
        pipcl.log(f'{sha=}')
        pipcl.log(f'{branch=}')
        pipcl.log(f'comment:\n{textwrap.indent(comment, "    ")}')
        if diff:
            pipcl.log(f'diff:\n{textwrap.indent(diff, "    ")}')
        else:
            pipcl.log(f'{diff=}')
    
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


def venv_run(args, path, recreate=True, clean=False, makelink=None):
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
        makelink:
            If true, we make a softlink from <makelink> to <path>.
    '''
    #pipcl.log(f'{path=} {recreate=} {clean=}')
    if clean:
        pipcl.log(f'Removing any existing venv {path}.')
        assert path.startswith('venv-')
        shutil.rmtree(path, ignore_errors=1)
    if recreate or not os.path.isdir(path):
        if platform.system() == 'Windows':
            pipcl.run(f'"{sys.executable}" -m venv {path}')
        else:
            pipcl.run(f'{shlex.quote(sys.executable)} -m venv {path}')
    if platform.system() == 'Windows':
        command = f'{path}\\Scripts\\activate && python'
        # shlex not reliable on Windows.
        # Use crude quoting with "...". Seems to work.
        for arg in args:
            if arg.startswith('"') and arg.endswith('"'):
                command += f'{arg}'
            else:
                assert '"' not in arg, f'{arg=}'
                command += f' "{arg}"'
    else:
        command = f'. {path}/bin/activate && python {shlex.join(args)}'
    if makelink:
        pipcl.fs_remove(makelink)
        try:
            os.symlink(path, makelink)
        except Exception as e:
            pipcl.log(f'Warning: failed to create link from {makelink=} to {path=}: {e}')
    e = pipcl.run(command, check=0, prefix=f'{path}: ')
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


if __name__ == '__main__':
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
            sys.exit(main(sys.argv))
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            # Terminate relatively quietly, failed commands will usually have
            # generated diagnostics.
            pipcl.log(f'{e}')
            raise
            #sys.exit(1)
        # Other exceptions should not happen, and will generate a full Python
        # backtrace etc here.
