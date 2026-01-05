Artifex Packages build/test
===========================

.. contents::
    :backlinks: entry
    :depth: 2

Overview
--------

The `aptest.py` script can build, test and release (to pypi.org) multiple
Python packages together.


Supported packages/projects
---------------------------

* mupdf
* pymupdf
* pymupdfpro
* pymupdf-layout


Package locations
-----------------

* Local checkout.
* Specific branch, tag or sha on remote git repository.
* pypi.org.

Also see:

* `-i`_
* `--mupdf`_ `-m`_
* `--pymupdf`_ `-p <-p_>`_
* `--pymupdfpro`_ `--pro`_ `-P <-PP_>`_
* `--pymupdf_layout`_ `--layout`_ `-l`_


Run in different places
-----------------------

* Local machine.
* Remote machine (with ssh/rsync).
* Github runner (push to unique(ish) branches and run a workflow).

See the `-r`_ option.


Build/install
-------------

For each package:

* The package is built as a wheel using `pip wheel`. This will typically
  take place in an internal pip venv.
* The wheel is installed into the current venv.
* The wheel is added to a local pypi-style PEP-503 package repository.
* We use pip's `--extra-index-url` option to refer to our internal package
  repository.
* Thus pip will use previously built wheels as prerequisites, as required.


Test
----

* We run tests in the current venv for each package, using pytest.
* Packages on pypi.org do not contain test suites, but one can specify a second
  package location to be used for testing, for example a local checkout or
  remote git repository.


Build/test with cibuildwheel
----------------------------

* The `cibw`_ command runs `cibuildwheel` on each package.
* This builds a wheel, and runs tests using pytest.
* We add each wheel to our internal package repository.
* We set PIP_EXTRA_INDEX_URL to point to our internal package repository.
* cibuildwheel uses pip internally so this ensures that previously-built
  prerequisite wheels will be installed as required.


Running on Github with `-r @github`
-----------------------------------

* If a package is specified as a local checkout:

  * We push the local checkout to a branch in the equivalent Github repository.
  * We change the aptest.py command line to specify a `git:...` location.

  For example we would change `-p PyMuPDF` to::

        -p 'git:-b <branch> git@github.com:pymupdf/PyMuPDF.git

* We use branch name `aptest-$USER`.

  This allows multiple developers to run on Github simultaneously, without
  creating an unbounded number of temporary branches.


Examples
--------

Build, install and test pymupdf, pymupdfpro and pymupdf_layout using
local checkouts::

    ./aptest/aptest.py -p PyMuPDF -P PyMuPDFPro -m mupdf -l sce build test

Build, install and test pymupdf, pymupdfpro and pymupdf_layout using
central git repositories::

    ./aptest/aptest.py -p git: -P git: -l git: build test

Make release, building/testing on Github, downloading to local machine,
and uploading to pypi.org::

    ./aptest/aptest.py --release-1
    ./aptest/aptest.py --release-2
    ./aptest/aptest.py --release-3


Build/test pymupdf, pymupdfpro and pymupdf-layout using cibuildwheel,
getting packages from different locations::

    ./aptest/aptest.py -r @github -p pip: -P PyMuPDFPlus -l git: cibw

Test current pymupdf release with latest test suite in central git::

    ./aptest/aptest.py -r macmini -p pip: -p git: build test

Test current pymupdf release with test suite in local checkout::

    ./aptest/aptest.py -r macmini -p pip: -p PyMuPDF build test

Runs specific Github workflow PyMuPDFPlus/.github/workflows/test_multiple.yml::

    ./aptest/aptest.py -r @github --remote-github-yml test_multiple.yml -P PyMuPDFPlus --remote-github-yml-inputs 'args=-o windows'

Tests pypi.org's pymupdf, pymupdfpro and pymupdf_layout with the test
suites on central git::

    ./aptest/aptest.py -r @github -p pip: -P pip: -l pip: -p git: -P git: -l git: build test


Release procedure
-----------------

Packages are:

* pymupdf
* pymupdfpro
* pymupdf_layout

Things to do:

* Get local checkout of each package.

* Ensure that pymupdf's `setup.py` specifies the correct mupdf version.

  If this is not the case, update, commit, push, and wait for the next
  overnight tests to pass before making the relase.

* Ensure the version number is correct in all packages.

  * All packages should use the same version number.
  * Version numbers are always defined in setup.py.
  * Version numbers may also be defined in other files such as README.
  * Pymupdf has a test that checks version numbers in changes.txt etc are
    consistent with setup.py.

* Ensure that PyMuPDF issues and changelog are synchronised.

  * Go to https://github.com/pymupdf/PyMuPDF/issues.
  * For all issues that are labeled as `Fixed in next release`, ensure that
    they are labelled as fixed in PyMuPDF's changes.txt.
  * For all issues mentioned as fixed in PyMuPDF's changes.txt, ensure that
    the corresponding Github issue is labelled as `Fixed in next release`.

* Test local checkouts of all packages on Github machines.

  Run::

    aptest/aptest.py -r @github -p PyMuPDF --pro PyMuPDFPro --layout sce cibw

* Push each package to github.
* Optionally lock github branches for each project.

  On each Github repository go to: `Settings/Branches/main/Edit/Lock branch`.

* Build and release main wheels.

  Run::

    aptest/aptest.py --release-1

  * On success this will download wheels/sdist to local machine and ask
    (twice) whether you want to upload to pypi.org.
  * At this point one can optionally test the downloaded wheels locally.
  * Agree to upload to pypi.org.

* Tag the release

  * We use the version number as the tag, e.g. `1.26.7`.
  * For each repository::

      git tag <version>
      git push origin <version>

* Start building Linux-aarch64 wheels::

    aptest/aptest.py --release-2

  [This will take a few hours, don't wait for it to finish here.]

* Extra updates to Github's pymupdf respository.

  * Go to: https://github.com/pymupdf/PyMuPDF/releases
  * Click `Draft a new release`.
  * In `Choose a tag`, select the tag `<version>`.
  * In `Release title` enter `PyMuPDF-<version> released`.
  * Add header text explaining pip install, similar to previous releases.
    For example::

      Wheels for Windows, Linux and MacOS, and the sdist, are available on
      pypi.org and can be installed in the usual way, for example:

      ```
      python -m pip install --upgrade pymupdf

      [Linux-aarch64 wheels will be built and uploaded later.]
      ```

  * Paste the release's changelog into the text field.
  * Modify any ReST-style links to work as markdown, e.g.
    rely on Github interpreting `#1234` as a link to issue
    1234.
  * Ensure that `Set as the latest release` is checked.
  * Ensure that `Create a discussion for this release` is checked,
    with `Category: Announcements`.
    
    Alternatively create an announcement discussion separately.
  * Click on `Publish release`.
    
    This will also create `.zip` and `.tar.gz` archives for download from
    github.
  * Go to the `Discussions` page and pin the announcement discussion so that
    it appears at the top of the page.
  * Unpin previous release's announcement discussion if present.
  * For all github issues that are labeled as `fixed in next release`,
    close the issue with text `Fixed in PyMuPDF-<version>`.

  * Check in the release announcement that all fixed issues are now shown as closed.
  * If the new release uses a new version of MuPDF, optionally
    remove all code that is specific to the previous major release
    of MuPDF. E.g. grep for `FZ_VERSION` or `mupdf_version_tuple`.

  * Update pymupdf.readthedocs.io:

    * Go to: readthedocs.io
    * Click `Log in`
    * Click on `Read the Docs Community`.
    * Select login using email.
    * Enter email address and shared password.
    * Go to PyMuPDF.
    * Click on Builds.
    * Click on top item's refresh button `Rebuild version`.

  * Post to Discord #pymupdf_tech.
  * Send email to pymupdf-marketing@artifex.com
    
    * Subject: `PyMuPDF-<version> released`

    * Body::
      
        PyMuPDF-<version> has just been released.
      
        See: https://github.com/pymupdf/PyMuPDF/discussions/<announcement>

* Wait for Linux aarch64 wheels build to finish.

* Update release discussion to say that Linux aarch64 wheels are now
  available, e.g. with a post saying::

    Linux-aarch64 wheels are now available; install in the usual way with pip.

* Agree to upload linux-aarch64 wheels to pypi.org.

* Build and release Windows-x32 wheel.

  Run::
  
    aptest/aptest.py --release-3

  Wait for build to finish, agree to upload.

* Build and release Linux musllinux-x64 wheel.

  Run::
  
    aptest/aptest.py --release-4

  Wait for buildd to finish, agree to upload.

* Unlock projects' branches if they were locked above:

    Github settings/Branches/main/Edit/Lock branch - uncheck.

* Post-release changes for all projects:
  
  * Increment version in setup.py.
  * In pymupdf:
  
    In changes.txt:
    
    * Add date of release that was just made.
    * Add title for next release `**Changes in version <next-version>**`
  
    In .github/ISSUE_TEMPLATE/bug_report.yml:
  
    * Add version of next release to drop-down list of versions.
    
      (This is required for tests to pass.)


Keys/tokens
-----------

Github/ArtifexSoftware ssh key
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

We allow specification of a custom ssh private key to push to and/or
access git@github.com:PyMuPDF/PyMuPDF and repositories within
git@github.com/ArtifexSoftware/.

* If required, this key should be provided in file `artifex-software-ssh-key`
  in the current directory.

* We run ssh with `StrictHostKeyChecking=no`, which may end up writing to
  .ssh/known_hosts.

Smartoffice ssh key
^^^^^^^^^^^^^^^^^^^

We allow specification of a custom ssh private key that allows access to the
SmartOffice repository; this is required when PyMuPDFPro builds SmartOffice
because of how the SmartOffice build system works.

* If required, this key should be provided in file `thirdparty-so-key` in the
  current directory.

Huggingface token
^^^^^^^^^^^^^^^^^

If required, this token should be provided in file `huggingface-key` in the
current directory.

Use of keys with remote runs
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* If the `-r`_ option is used to defer to a remote machine, the key files are
  copied to the remote machine. This obviously has security implications.

* If the `-r`_ option is used to defer to a Github runner, we rely on the
  ArtifexSoftware/aptest repository having secrets that allow the required
  access.


Using DocLayNet dataset
-----------------------

The 'gnn' command downloads/extracts the DocLayNet dataset as described in
https://github.com/ArtifexSoftware/sce/wiki/How-to-train-GNN.
Downloads/extracts only as necessary, so is efficient if run more than once.

The `test-gnn*` commands run pymupdf_layout's test scripts on the DocLayNet
datset:

* 'test-gnn' command runs `sce:eval/eval_gnn.py`.
* 'test-gnn-pymupdf_layout' command runs `sce:eval/eval_pymupdf_layout.py`.
* 'test-gnn-pymupdf4llm' command runs `sce:eval/eval_pymupdf4llm.py`.


Argument completion with Bash
-----------------------------

`aptest/aptest.py completion` writes a bash completion script for aptest to
stdout.

* Add argument completion for aptest.py to the current Bash session with::

    source <(aptest/aptest.py completion)

  Subsequently when entering an aptest.py command, bash will respond to `<tab>`
  by completing and/or showing valid args.

* Or write into relevant files with one of::

  ./aptest/aptest.py completion > /etc/bash_completion.d/aptest.py.bash_completion
  ./aptest/aptest.py completion >> ~/.bash_completion

  See Bash's `help complete` for more information.


Command-line arguments
----------------------

.. contents::
    :local:

Overview
^^^^^^^^

* Command line arguments are called options if they start with `-`,
  otherwise they are called commands.
* Arguments are evaluated first in the order that they were specified.
* Then commands are run in the order in which they were specified.
* Usually command `test`_ would be specified after commands such as `build`_.
* Options and commands can be interleaved but it may be clearer to separate
  them on the command line.
* Command-line arguments are prefixed with contents of `~/.aptest`, if it
  exists.

  * Arguments are extracted using `shlex.split()`, so are separated by
    whitespace (e.g. space and newlines characters) unless escaped or inside
    quotes etc.


Commands
^^^^^^^^

.. _build:

build
.....
    Builds and installs packages specified by `-i`_ into venv. Wheels
    are placed in `aptest-wheelhouse`.

    Also see:

    * `-b`_
    * `--build-type`_

.. _cibw:

cibw
....
    Build and test packages using cibuildwheel. Wheels are placed
    in directory `aptest-wheelhouse`, which is initially cleared.
    * We do not install wheels and it is generally not useful to do
    `cibw test`.

    If CIBW_BUILD is unset, we set it as follows:
    * On Github we build and test all supported Python versions.
    * Otherwise we build and test the current Python version only.

    If CIBW_ARCHS is unset we set $CIBW_ARCHS_WINDOWS, $CIBW_ARCHS_MACOS
    and $CIBW_ARCHS_LINUX to auto64 if they are unset.

    Also see:

    * `--cibw-name`_
    * `--cibw-pyodide`_
    * `--cibw-pyodide-version`_
    * `--cibw-skip-add-defaults`_

.. _gnn-download:

gnn-download
............
    Download and extract dataset for pymupdf_layout GNN model. Does not
    do unnecessary downloads or extracts.

.. _gnn-show:

gnn-show
........
    Generate graph showing results from previous runs of `test-gnn*`.

    For example::

        ./aptest/aptest.py gnn-show --gnn-show-select \
                " \
                'environ' in results \
                and results['environ']['USER']=='jules' \
                and results['python']['platform.system()']=='Windows' \
                and  results['state'].get('limit')==5 \
                "

    Also see:

    * `--gnn-show-graph`_
    * `--gnn-show-text`_
    * `--gnn-show-select`_

.. _gnn-train:

gnn-train
.........
    Trains pymupdf_layout. Not tested.

.. _populate:

populate
........
    For packages specified with `git:...` populate local checkouts like
    the `build`_ command, but do not actually build/install anything.

.. _run:

run
...
    Runs commands specified by `--run`_ within checkouts.

.. _test:

test
....
    Runs pytest tests.

    Also see:

    * `--pytest`_
    * `--pytest-path`_
    * `--pytest-wrap`_
    * `-t`_
    * `--test-extra-packages`_

.. _test-gnn:

test-gnn
........

    [untested]
    Test GNN model.

.. _test-gnn-pymupdf_layout:

test-gnn-pymupdf_layout
.......................
    [untested]
    Test GNN model via pymupdf_layout.

.. _test-gnn-pymupdf4llm:

test-gnn-pymupdf4llm
....................

    * Test GNN model via pymupdf4llm.
    * Writes results to test-gnn-pymupdf4llm-YYYY-MM-DD-HH-MM-SS.json.

    Results are a dict with this structure::

        results['python']...    Values from python's `platform` and `sys` modules.
        results['environ'] - selected items from Python's os.environ.
        results['state'] - description of what values we passed to pymupdf_layout:eval/eval_util.py:evaluate_detection().
        results['packages'] - information about each package that we built/installed - version, git branch, sha etc.
        results['pip-list'] - information from `pip list` showing information about all packages.
        results['results'] - the results from the test.
        results['t_duration'] - duration of test in seconds.
        results['t_start'] - Unix start time.

    Also see:

    * `--test-gnn-cache`_
    * `--test-gnn-extra`_
    * `--test-gnn-limit`_
    * `--test-gnn-out`_
    * `--test-gnn-push`_


.. _test-gnn-devel:

test-gnn-devel
..............
    Work in progress running gnn pymupdf4llm test, storing output in
    file with full git info of all packages.


Options
^^^^^^^

.. _-a:

-a <env_name>
.............
    Read next space-separated argument(s) from environmental variable
    `<env_name>`.
    
    * Does nothing if `<env_name>` is unset.
    * Useful when running via Github action.

.. _-b:

-b <packages>
.............
    Comma-separated ordered list of modifications to the list of
    packages built and installed by the `build`_ command.

    This list defaults to all packages specified by `-i`. Then for each
    comma-separated item in `<packages>`:

    * `-<name>`: removes package `<name>` from the list.
    * `+<name>` and `<name>`: adds package `<name>` to the list.
    * `-` removes all packages from the list.

    In addition if the first item does not start with `+` or `-` we
    first remove all packages from the list.

    We allow aliases for package names.

    For example:

    * Build only pymupdfpro::
    
        -b -,P

        -b -,pymudfpro

    * Remove mupdf and layout from list of packages to build::
    
        -b -m,--layout

        -b -mupdf,-pymupdf_layout

    If 'mupdf' was specified as a package but has been removed here, we
    set `PYMUPDF_SETUP_MUPDF_REBUILD=0` so pymupdf will not rebuild its
    mupdf.

.. _--build-type:

--build-type debug|memento|release
..................................
    Set build type. Default is `release`.

.. _--cibw-name:

--cibw-name <cibw_name>
.......................

    Name to use when installing `cibuildwheel` for the `cibw`_ commad, e.g.::
    
        --cibw-name cibuildwheel==3.0.0b1
        --cibw-name git+https://github.com/pypa/cibuildwheel

    Default is `cibuildwheel`, i.e. the current release.

.. _--cibw-pyodide:

--cibw-pyodide 0|1
..................
     Make the `cibw`_ command build a pyodide wheel; runs `cibuildwheel
     --platform pyodide ...` etc.

.. _--cibw-pyodide-version:

--cibw-pyodide-version <cibw_pyodide_version>
.............................................
    Override default Pyodide version to use with `cibw`_ command
    by setting `CIBW_PYODIDE_VERSION`.

.. _--cibw-skip-add-defaults:

--cibw-skip-add-defaults 0|1
............................
    If 1 (the default) we add defaults to `CIBW_SKIP` such as `pp*` (to exclude
    pypy) and `cp3??t-*` (to exclude free-threading), which effects the `cibw`_
    command.

.. _--clean:

--clean <packages>
..................
    Add comma-separated packages to list of packages for which we run `git
    clean -fdx` in the `populate`_ and `build`_ commands.

.. _--devel:

--devel 0|1
...........
    If 1, output extra information, e.g. backtrace on error.

.. _-e:

-e <name>=<value>
.................
    Set specified environment variable.

.. _--gnn-doit:

--gnn-doit 0|1
..............
    If 0 (the default) we never download/extract DocLayNet.

.. _--gnn-show-graph:

--gnn-show-graph <path>
.......................
    Override default name of gnn-graph out file in `gnn-show`_ command.

.. _--gnn-show-path:

--gnn-show-path <path>
......................
    Add comma-separated paths of json output file for `gnn-show`_ command. Can
    be called multiple times.

.. _--gnn-show-select:

--gnn-show-select <expression>
..............................
    Specify expression to use to select which `test-gnn-*.json` files to
    include in output created by command `gnn-show`_.

    `<expression>` should be a Python expression that looks at Python dict `results`.

    `<results>` will actually be a `doct.Doct()` so dotted notation can
    also be used for keys that are legal Python identifiers.

    Example::
    
        --gnn-show-select "'environ' in results and results.environ.USER=='jules' and results.python['platform.system()']=='Windows' and  results.state.get('limit')==5

--gnn-show-text <path>
......................
    Override default filename of `gnn-show`_ text output.

.. _--graal:

--graal 0|1
...........
    If '1' we use Graal environment.

    As of 2025-08-04, if specified:
    
    * We assert-fail if both `cibw`_ and non-cibw commands are specified.
    * If the `cibw`_ command  is specified:

      * We use a conventional venv.
      * We set `CIBW_ENABLE=graalpy`.
      * We set `CIBW_BUILD = 'gp*'`.

    * Otherwise we:

      * Don't create a conventional venv.
      * Clone the latest pyenv and build it.
      * Use pyenv to install graalpy.
      * Use graalpy to create venv.

    [After the first time, suggest `-v 1` to avoid delay from
    updating/building pyenv and recreating the graal venv.]

.. _--gnn-show-text:

.. _--help:

.. _-h:


--help
......
-h
..
    Show this help.

.. _-i:

-i <package-name> <location>
............................
    Add an input package.

    `package-name`:

        One of::

            langchain_pymupdf_layout
            mupdf
            pymupdf
            pymupdf4llm
            pymupdf_layout
            pymupdfpro

    location::
        `pip:`
            Install from pypi.org using pip.

        `pip:<version>`
            Install specified version from pypi.org using pip.
            [Doesn't currently work generally because if another project needs a
            newer version, pip will install again from pypi.org.]
        `pip:*.whl`
            Install from local wheel using pip.
        `pip:*.tar.gz`
            Install from local sdist using pip.
        `'git:[-b <branch>] [-t <tag>] [<remote>]'`
            Clone/update from git remote into local checkout
            `aptest-git-<package-name>`, optionally overriding default
            branch/tag/remote.
            Note that any changes or commits in the local checkout are
            deleted.

        <local-dir>
            Local directory, typically a git checkout.

    If a package is specified twice, the first location will be used
    for building, and the second location used for testing. This allows
    packages on pypi.org to be tested, for example:

        aptest.py -i pymupdf pip: -i pymupdf PyMuPDF build test
            Test current pymupdf release with testsuite in PyMuPDF/tests.

        aptest.py -i pymupdf pip: -i pymupdf git: build test
            Test current pymupdf release with testsuite in current git.

.. _--langchain-pymupdf-layout:

--langchain-pymupdf-layout <location>
.....................................

.. _--langchain:

--langchain <location>
......................
    Aliases for `-i langchain_pymupdf_layout <location>`

.. _--mupdf:
.. _-m:

--mupdf <location>
..................
-m <location>
.............
    Aliases for `-i mupdf <location>`.

.. _-o:

-o <os_names>
.............
    Control which OS's we run on. If current OS is not in
    (comma-separated) list, we do nothing. <os_names> is case
    insensitive. Should match linux, windows or darwin.

.. _--pymupdf:

.. _-p:

--pymupdf <location>
....................
-p <location>
.............
    Aliases for `-i pymupdf <location>`.

.. _--pymupdfpro:

.. _--pro:

.. _-PP:

--pymupdfpro <location>
.......................
--pro <location>
................
-P <location>
.............
    Aliases for `-i pymupdfpro <location>`.

.. _pymupdf4llm:

--pymupdf4llm <location>
........................
--4llm <location>
.................
    Aliases for `-i pymupdf4llm <location>`.

.. _--pymupdf_layout:
.. _--layout:
.. _-l:

--pymupdf_layout <location>
...........................
--layout <location>
...................
-l <location>
.............
    Aliases for `-i pymupdf_layout <location>`.

.. _--pytest:

--pytest <pytest-flags>
.......................
    Specify pytest flags used by `test`_ command; for example `--pytest '-k
    test_123'`.

.. _--pytest-path:

--pytest-path <pytest_path>
...........................
    Specify a directory/file/function to use with the `test`_ command, relative
    to each project root directory. Can be specified multiple times. Default is
    `<package_root>/tests/`.

.. _--pytest-wrap:

--pytest-wrap gdb|valgrind|helgrind
...................................
    Makes `test`_ command run tests under specified tool.

.. _--python:

--python <python>
.................
    Set Python to use. If set we re-run ourselves using specified
    python command.

.. _-r:

-r <remote>
...........
    Re-run ourselves on remote machine(s) and on success copy wheels
    back to local machines.

    If `<remote>` is `@github`, we run on Github:

    * We push specified local checkouts directories (specified
      by `-i`, `-m`, `-p` etc) to branches called `aptest-$USER` in the
      equivalent repositories in `github.com/ArtifexSoftware/`.

    * Warning: this will make git forget about any new files that
      have been added but not yet commited.

      This is because we currently push any uncommited changes as a
      temporary commit, then use `git reset HEAD~1` to restore git
      state.

    * We re-run the `aptest.py` command on Github machines, changing
      `-i`, `-m` etc args to use `git:` to refer to the above
      repositories.

    * On success we copy Github logs and artifacts
      and extracted wheels etc to local directory
      `gh_workflow_YYYY-MM-DD-<workflowid>`. Wheels are copied in
      flat format into `gh_workflow_YYYY-MM-DD-<workflowid>-union/`.

    Otherwise `<remote>` should specify a remote machine on which to run
    aptest:

    * If `<remote>` contains a space it is interpreted as the ssh
      command to use, optionally ending with a colon followed by
      the remote directory to use.

      For example::

          -r 'ssh -p 2222 -J barfoo@mygateway foobar@mymachine.com:testdir'

    * Otherwise `<remote>` should be a rsync-style specification such
      as `macmini` or `username@macmini:testdir`.

      Specify a ssh jump host using `::`, for example::

          -r <gateway>::<remote-host>

    In both cases:

    * Local checkouts specified by `-i` are coped to the remote
      using rsync, then `git clean -f` is run on the remote.

    * On success:

      * Wheels are copied back into local directory
        `aptest-wheelhouse/`.

      * Files matching `test-gnn-*.json` are copied back into the
        current directory.

.. _--release-1:

.. _--release-2:

.. _--release-3:

--release-1
...........
--release-2
...........
--release-3
...........
    Preset args for making releases. Only one may be specified, and it
    must be the only arg.

    `aptest/aptest.py --release-1`
        Build wheels for everything except linux-aarch64,
        linux-x64-musl and win32.
    `aptest/aptest.py --release-2`
        Build wheels for linux-aarch64.
    `aptest/aptest.py --release-3`
        Build wheels for win32 (pymupdf only).
    `aptest/aptest.py --release-4`
        Build wheels for linux-x64-musl (pymupdf only).

.. _--remote-do:

--remote-do 0|1
...............
    [For debugging.]

    If 0 we don't sync to remote and we don't run any commands on
    remote. But we do sync remote wheels to local.

.. _--remote-github-workflow-id:

--remote-github-workflow-id <workflow_id>
.........................................
    Changes behaviour of `-r @github`. Don't run anything Github,
    instead continue from previous `-r @github` invocation by waiting
    for `<workflow_id>` to finish and then downloadings logs and wheels
    etc. Note that one still needs to include `-r @github cibw`.

.. _--remote-github-yml:

--remote-github-yml <yml>
.........................
    With `-r @github`, run `.yml` file (leafname) instead of running
    `aptest.py`. If no packages are specified, runs on Github's
    `ArtifexSoftware/aptest repository`; otherwise exactly one package
    must be specified.

.. _--remote-github-yml-inputs:

--remote-github-yml-inputs <inputs>
...................................
    Specify inputs used with `--github-yml`. `<inputs>` is comma-separated
    list of `<name>=<value>` pairs.

.. _--remote-prefix:

--remote-prefix <remote_prefix>
...............................
    Run remote using specified Python command. Ignored by `-r @github`.

.. _--remote-prefix-default:

--remote-prefix-default <remote> <prefix>
.........................................
    Sets default remote prefix for different remotes as specified with
    `-r <remote>`. For example::

        --remote-prefix-default jules-asus python312

.. _--remote-rsync-path:

--remote-rsync-path <remote_rsync_path>
.......................................
    Specify `--rsync-path` when running rsync, to identify location of
    rsync on remote. E.g. `--remote-rsync-path 'wsl rsync` if remote is
    a Windows machine with rsync installed in default WSL system.

.. _--remote-rsync-wsl:

--remote-rsync-wsl 0|1
......................
    [Experimental.]

    Tweak various things to cope with remote using wsl rsync.

.. _--run:

--run <package> <command>
.........................
    Make `run`_ command run specified command within checkout of
    `<package>`.

.. _--sdists:

--sdists 0|1
............
    If 1, the `build`_ and `cibw`_ commands will also build sdists.

.. _--swig:

--swig <swig>
.............
    Use <swig> instead of the `swig` command.

    Unix only:
        Clone/update/build swig from a git repository using 'git:' prefix.

        We default to https://github.com/swig/swig.git branch master, so these
        are all equivalent:

            --swig 'git:--branch master https://github.com/swig/swig.git'
            --swig 'git:--branch master'
            --swig git:

        2025-08-18: This fixes building with py_limited_api on python-3.13.

.. _--swig-quick:

--swig-quick 0|1
................
    If 1 and `--swig`_'s `<swig>` value starts with `git:`, we do not
    update/build swig if it is already present.

.. _--system-packages:

--system-packages 0|1
.....................
    If 1, automatically install required system packages such as
    Valgrind, using `apt` on Linux and `brew` on MacOS. Default is 1 if
    running as Github action, otherwise 0.

.. _--system-site-packages:

--system-site-packages 0|1
..........................
    If 1, use `--system-site-packages` when creating venv. Defaults is 0.

.. _-t:

-t <packages>
.............
    Comma-separated ordered list of modifications to the list of
    packages tested by the `test`_ command.

    This list defaults to all packages specified by `-i` or its aliases. Then
    for each comma-separated item in `<packages>`:

        * `-<name>` removes package `<name>` from the list.
        * `+<name>` and `<name>` adds package `<name>` to the list.
        * `-` removes all packages from the list.

    In addition if the first item does not start with `+` or `-` we
    first remove all packages from the list.

    We allow aliases for package names.

    For example these test only pymupdfpro::
    
        -t -,pro
        -t -,pymudfpro

    And these remove mupdf and layout from list of packages to test::
    
        -t -m,-l
        -t -mupdf,-pymupdf_layout

.. _--test-extra-packages:

--test-extra-packages <names>
.............................
    Installs specified comma-separated packages from pypi.org before
    running tests in `test`_ command.

.. _--test-gnn-cache:

--test-gnn-cache 0|1
....................
    If 1, `test-gnn*` commands look for a matching `test-gnn-*.json`
    file. If one is found, we do not run, instead creating softlinks to
    the matching `.json` file.

    To match, we require all fields in a `.json` file match the file
    that we would create for the current run, except for:

    * ['results'] - not available for the current run, obviously.
    * ['t_start']
    * ['t_duration']
    * ['pip-list'] - we allow changes to misc other packages, e.g. version numbers may vary.

    We require the other settings to be identical, such as:

    * OS, machine name, username etc.
    * Python version, implementation etc.
    * How Artifex pckages were specified, e.g. `-p git:` or `-p pypi.org`.
    * git sha's and diffs for Artifex packages specified with `git:` or local checkout.
    * pypi.org version numbers for Artifex packages specified with `pip:`.
    * Any `--test-gnn-limit` value.

.. _--test-gnn-extra:

--test-gnn-extra <key>=<value>
..............................
    Adds specified key=value pair to the root of the results dict
    created by test-gnn* commands.

.. _--test-gnn-limit:

--test-gnn-limit <limit>
........................
    Set number of gnn files to test. Default is all.

.. _--test-gnn-out:

--test-gnn-out <path>
.....................
    Where to write json data containing test details. Default is a file
    containing curre time.

.. _--test-gnn-push:

--test-gnn-push 0|1
...................
    If 1, we push gnn results to
    github.com/ArtifexSoftware/PyMuPDF-pymupdf-results. Default is 0.

.. _--ticker:

--ticker <delay>
................
    Use ticker with specified delay. Disabled if delay==0. Default is
    0.5.

.. _-u:

-u 0|1
......
    If 1, if `-r @github` is used then on success we ask the user to
    confirm and then upload wheels to pypi.org.

.. _-v:

-v <venv>
.........
    Changes how we run ourselves in a venv if required.

    `0` - Do not use a venv.

    `1` - Use venv. If it already exists, we assume the existing
        directory was created by us earlier and is a valid venv
        containing all necessary packages; this saves a little time.

    `2` - Use venv.

    `3` - Use venv but delete it first if it already exists.

    The default is `2`.

    The venv will be called `venv-aptest-<pthonversion>-<wordsize>`; we
    also create a convenience link called `venv-aptest`.

.. _-V2:

-V
..
    Verbose.
