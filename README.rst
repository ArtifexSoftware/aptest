.. section-numbering::
    :depth: 2

Artifex Packages build/test
===========================

.. contents::
    :backlinks: entry
    :depth: 2

Overview
--------

The ``aptest.py`` script can build, test and release (to https://pypi.org) multiple
Python packages together.

Aptest is not a Python package - there is no support for building an aptest
wheel for example.

Instead it is intended to be used directly from a Git checkout, for example::

    git clone git@github.com:ArtifexSoftware/aptest.git
    
    ./aptest/aptest.py ...


Packages
--------

Supported packages are:

* mupdf
* pymupdf
* pymupdf4llm
* pymupdfpro
* pymupdf_layout
* langchain_pymupdf_layout
* pdf_feature_inspector

Packages can be in different locations:

* Local checkout.
* Specific branch, tag or sha on remote git repository.
* https://pypi.org.

See the `-i`_ option.


Use of Python venv virtual environments
---------------------------------------

If we are not already running inside a Python venv, we automatically create a
venv and re-run ourselves inside it.

* The `build`_ command builds and installs into the current venv.
* The `test`_ command tests packages that are installed in the current venv.

See the `-v`_ option.


Run remotely
------------

Aptest can transparently rerun itself in remote locations:

* Remote machine (with ssh/rsync).
* Github runner (push to unique(ish) branches and run a workflow).

See the `-r`_ option.


Build/install
-------------

For each package:

* The package is built as a wheel using ``pip wheel``. This will typically
  take place in an internal pip venv.
* The wheel is installed into the current venv.
* The wheel is added to a local pypi-style PEP-503 package repository.
* We use pip's ``--extra-index-url`` option to refer to our internal package
  repository.
* Thus pip will use previously built package wheels as prerequisites, as required.

See the `build`_ command.


Cleaning packages
-----------------

Packages can be cleaned before building or when populating.

See the `--clean-git`_, `--clean-setup`_ and `--clean-setup-all`_ options.


Test
----

* We run tests in the current venv for each package, using pytest.
* Packages on https://pypi.org do not contain test suites, but one can specify a second
  package location to be used for testing, for example a local checkout or
  remote git repository.

* One can generate traces of MuPDF calls by setting environment variables in debug
  builds. For details see:
  https://mupdf.readthedocs.io/en/latest/language-bindings.html#environmental-variables

See the `test`_ command.


Build/test with cibuildwheel
----------------------------

* The `cibw`_ command runs ``cibuildwheel`` on each package.
* This builds a wheel, and runs tests using pytest.
* We add each wheel to our internal package repository.
* We set ``PIP_EXTRA_INDEX_URL`` to point to our internal package repository.
* cibuildwheel uses pip internally so this ensures that previously-built
  prerequisite wheels will be installed as required.

See the `cibw`_ command.

Cibuildwheel Python version
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Cibuildwheel needs system install of required python version(s).

On Macos:

* Installing python versions with brew does not seem to work - cibuildwheel
  cannot find it.
* To install python-3.14t:
  
  * Run::
  
      wget https://www.python.org/ftp/python/3.14.0/python-3.14.0-macos11.pkg
  
  * Create a file called ``choicechanges.plist`` containing::
  
      <?xml version="1.0" encoding="UTF-8"?>
      <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
      <plist version="1.0">
      <array>
              <dict>
                      <key>attributeSetting</key>
                      <integer>1</integer>
                      <key>choiceAttribute</key>
                      <string>selected</string>
                      <key>choiceIdentifier</key>
                      <string>org.python.Python.PythonTFramework-3.14</string>
              </dict>
      </array>
      </plist>
  
  * Run::
  
      sudo installer -pkg python-3.14.0-macos11.pkg -applyChoiceChangesXML choicechanges.plist -target /
  
  * Also see: https://docs.python.org/3/using/mac.html.


Examples
--------

Build, install and test pymupdf, pymupdfpro and pymupdf_layout using
local checkouts::

    ./aptest/aptest.py -p PyMuPDF --pro PyMuPDFPro -m mupdf --layout sce build test

Build, install and test pymupdf, pymupdfpro and pymupdf_layout using
central git repositories::

    ./aptest/aptest.py -p git: --pro git: --layout git: build test

Make release, building/testing on Github, downloading to local machine,
and uploading to https://pypi.org (also see `Release procedure`_)::

    ./aptest/aptest.py --release-1
    ./aptest/aptest.py --release-2
    ./aptest/aptest.py --release-3
    ./aptest/aptest.py --release-4
    ./aptest/aptest.py --release-5

Build/test pymupdf, pymupdfpro and pymupdf-layout using cibuildwheel,
getting packages from different locations::

    ./aptest/aptest.py -r @github -p pip: --pro PyMuPDFPlus --layout git: cibw

Test current pymupdf release with latest test suite in central git::

    ./aptest/aptest.py -r macmini -p pip: -p git: build test

Test current pymupdf release with test suite in local checkout::

    ./aptest/aptest.py -r macmini -p pip: -p PyMuPDF build test

Runs specific Github workflow PyMuPDFPlus/.github/workflows/test_multiple.yml, on windows only::

    ./aptest/aptest.py -r @github --remote-github-yml test_multiple.yml --pro PyMuPDFPlus --remote-github-yml-inputs 'args=-o windows'

Tests https://pypi.org's pymupdf, pymupdfpro and pymupdf_layout with the test
suites on central git::

    ./aptest/aptest.py -r @github -p pip: --pro pip: --layout pip: -p git: --pro git: --layout git: build test

Download wheels from a previous Aptest Github workflow run::

    ./aptest/aptest.py -r @github --aptest aptest --remote-github-workflow-id 21760695687

Test aptest itself::

    ./aptest/aptest.py --aptest aptest test

Release procedure
-----------------

Instructions for releasing wheels for:

* pymupdf
* pymupdfpro
* pymupdf_layout


* Get local checkout of each package.

* Ensure that pymupdf's ``setup.py`` specifies the correct mupdf version.

  If this is not the case, update, commit, push, and wait for the next
  overnight tests to pass before making the release.

* Ensure the version number is correct in all packages.

  * All packages should use the same version number.
  * Version numbers are always defined in ``setup.py``.
  * Version numbers may also be defined in other files such as ``README``.
  * Pymupdf has a test that checks version numbers in ``changes.txt`` etc are
    consistent with ``setup.py``.

* Ensure that PyMuPDF's Github issues and ``changes.txt`` are synchronised.

  * Go to https://github.com/pymupdf/PyMuPDF/issues.
  * For all issues that are labeled as ``Fixed in next release``, ensure that
    they are labelled as fixed in ``changes.txt``.
  * For all issues mentioned as fixed in ``changes.txt``, ensure that
    the corresponding Github issue is labelled as ``Fixed in next release``.

* Test local checkouts of all packages on Github machines::

    aptest/aptest.py -r @github -p PyMuPDF --pro PyMuPDFPro --layout sce cibw

* Push each package to Github.
* Optionally lock github branches for each project.

  On each Github repository go to: ``Settings/Branches/main/Edit/Lock branch``.

* Build and release the main wheels::

      aptest/aptest.py --release-1

  * On success this will download wheels/sdist to local machine and ask
    (twice) whether you want to upload to https://pypi.org.
  * At this point one can optionally test the downloaded wheels locally.
  * Agree to upload to https://pypi.org.

* Tag the release.

  * We use the version number as the tag, e.g. ``1.26.7``.
  * For each repository::

      git tag <version>
      git push origin <version>

* Start building Linux-aarch64 wheels::

    aptest/aptest.py --release-2

  [This will take a few hours, don't wait for it to finish here.]

* Extra updates to Github's pymupdf repository.

  * Go to: https://github.com/pymupdf/PyMuPDF/releases
  * Click ``Draft a new release``.
  * In ``Choose a tag``, select the tag ``<version>``.
  * In ``Release title`` enter ``PyMuPDF-<version> released``.
  * Add header text explaining pip install, similar to previous releases.
    For example::

      Wheels for Windows, Linux and MacOS, and the sdist, are available on
      https://pypi.org and can be installed in the usual way, for example:

      ```
      python -m pip install --upgrade pymupdf

      [Linux-aarch64 wheels will be built and uploaded later.]
      ```

  * Paste the release's changelog into the text field.
  * Modify any ReST-style links to work as markdown, e.g.
    rely on Github interpreting ``#1234`` as a link to issue
    1234.
  * Ensure that ``Set as the latest release`` is checked.
  * Ensure that ``Create a discussion for this release`` is checked,
    with ``Category: Announcements``.
  * Click on ``Publish release``.
    
    This will also create ``.zip`` and ``.tar.gz`` archives for download from
    github.
  * Go to the ``Discussions`` page and pin the announcement discussion so that
    it appears at the top of the page.
  * Unpin any previous release's announcement discussion.
  * For all Github issues that are labeled as ``fixed in next release``,
    close the issue with text ``Fixed in PyMuPDF-<version>``.
  * Check in the release announcement that all fixed issues are now shown as closed.
  * If the new release uses a new version of MuPDF, optionally
    remove all code that is specific to the previous major release
    of MuPDF. E.g. grep for ``FZ_VERSION`` or ``mupdf_version_tuple``.

  * Update https://pymupdf.readthedocs.io:

    * Go to: https://readthedocs.io
    * Click ``Log in``.
    * Click on ``Read the Docs Community``.
    * Select login using email.
    * Enter email address and shared password.
    * Go to PyMuPDF.
    * Click on Builds.
    * Click on top item's refresh button ``Rebuild version``.

  * Post to Discord ``#pymupdf_tech``.
  * Send email to ``pymupdf-marketing@artifex.com``.
    
    * Subject: ``PyMuPDF-<version> released``

    * Body::
      
        PyMuPDF-<version> has just been released.
      
        See: https://github.com/pymupdf/PyMuPDF/discussions/<announcement>

* Wait for Linux aarch64 wheels build to finish.

* Agree to upload linux-aarch64 wheels to https://pypi.org.

* Update Github release discussion to say that Linux aarch64 wheels are now
  available, e.g. with a post saying::

    Linux-aarch64 wheels are now available; install in the usual way with pip.

* Build and release Windows-x32 wheel.

  Run::
  
    aptest/aptest.py --release-3

  Wait for build to finish, agree to upload.

* Build and release Linux musllinux-x64 wheel.

  Run::
  
    aptest/aptest.py --release-4

  Wait for build to finish, agree to upload.

* Build and release pyodide wheel.

  Run::
  
    ./aptest/aptest.py --release-5

  Upload the resulting pyodide wheel to julian@ghostscript.com:public_html/pyodide/.
  
  Tell @jamie about the Pyodide wheel.
  
  [2026-01-30: hopefully we'll have a more official location soon.]

* Unlock projects' branches if they were locked above:

  Github settings/Branches/main/Edit/Lock branch - uncheck.

* Post-release changes for all projects.
  
  * Increment version in ``setup.py``.

* Extra post-release changes for pymupdf.

  In ``changes.txt``:

  * Add date of release that was just made.
  * Add title for next release ``**Changes in version <next-version>**``.

  In ``.github/ISSUE_TEMPLATE/bug_report.yml``:

  * Add version of next release to drop-down list of versions.

    (This is required for tests to pass.)


Workarounds
-----------

With `cibw`_ we do not test with python-3.14 on Windows.
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
**2026-02-06**

When cibuildwheel internally attempts to install packages with ``pip
install`` (with ``PIP_EXTRA_INDEX_URL`` pointing to our piprepo wrapping of
aptest-wheelhouse), pip complains::

    WARNING: Location 'file://D:/a/aptest/aptest/aptest-wheelhouse/simple/pymupdf/' is ignored: it is neither a file nor a directory.
    INFO: pip is looking at multiple versions of pymupdfpro to determine which version is compatible with other requirements. This could take a while.
    ERROR: Could not find a version that satisfies the requirement PyMuPDF==1.27.1 (from pymupdfpro) (from versions: ...)
    ERROR: No matching distribution found for PyMuPDF==1.27.1

I.e. preprequsite packages are not found, despite being in
``aptest-wheelhouse``.

This failure does not happen with python-3.10-3.13.

Use of setuptools<81 for piprepo
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
**2026-02-08**

Package piprepo requires pkg_resources, which is part of setuptools, but
only setuptools<81.

Keys/tokens
-----------

Github/ArtifexSoftware ssh key
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

We allow specification of a custom ssh private key to push to and/or
access git@github.com:PyMuPDF/PyMuPDF and repositories within
git@github.com/ArtifexSoftware/.

This key can be provided in two ways:

* In file ``artifex-software-ssh-key`` in the current directory.
* In environment variable ``ARTIFEX_SOFTWARE_SSH_KEY``.

We run ssh with ``StrictHostKeyChecking=no``, which may end up writing to
``~/.ssh/known_hosts``.

Smartoffice ssh key
^^^^^^^^^^^^^^^^^^^

We allow specification of a custom ssh private key that allows access to the
SmartOffice repository; this is required when PyMuPDFPro builds SmartOffice
because of how the SmartOffice build system works.

* If required, this key should be provided in file ``thirdparty-so-key`` in the
  current directory.

Huggingface token
^^^^^^^^^^^^^^^^^

If required, this token should be provided in file ``huggingface-key`` in the
current directory.

Use of keys with remote runs
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* If the `-r`_ option is used to defer to a remote machine, the key files are
  copied to the remote machine. This obviously has security implications.

* If the `-r`_ option is used to defer to a Github runner, we rely on the
  https://ArtifexSoftware/aptest repository having secrets that allow the required
  access.


Using DocLayNet dataset
-----------------------

The `gnn-download`_ command downloads/extracts the DocLayNet dataset as described in
https://github.com/ArtifexSoftware/sce/wiki/How-to-train-GNN.

* Downloading and extracting is tracked using marker files, to avoid running
  unnecessarily more than once.

The ``test-gnn*`` commands run pymupdf_layout's test scripts on the DocLayNet
dataset:

* 'test-gnn' command runs ``sce:eval/eval_gnn.py``.
* 'test-gnn-pymupdf_layout' command runs ``sce:eval/eval_pymupdf_layout.py``.
* 'test-gnn-pymupdf4llm' command runs ``sce:eval/eval_pymupdf4llm.py``.


Argument completion with Bash
-----------------------------

``aptest/aptest.py completion`` writes a bash completion script for aptest to
stdout.

* Add argument completion for aptest.py to the current Bash session with::

    source <(aptest/aptest.py completion)

  Subsequently when entering an aptest.py command, bash will respond to ``<tab>``
  by completing and/or showing valid args.

* Or write into relevant files with one of::

  ./aptest/aptest.py completion > /etc/bash_completion.d/aptest.py.bash_completion
  ./aptest/aptest.py completion >> ~/.bash_completion

  See Bash's ``help complete`` for more information.

* Also see special command  `completion`_.


Command-line arguments
----------------------

.. contents::
    :local:

Overview
^^^^^^^^

* Command line arguments are called options if they start with ``-``,
  otherwise they are called commands.
* Options are evaluated first in the order that they were specified.
* Then commands are run in the order in which they were specified.
* Usually command `test`_ would be specified after commands such as `build`_.
* Options and commands can be interleaved but it may be clearer to separate
  them on the command line.

* Command line arguments are prepended with ``<.aptest> <APTEST_options>``, where:
  
  * ``<.aptest>`` is the contents of file ``~/.aptest`` if it exists.
    
    Lines starting with ``#`` are ignored.
  * ``<APTEST_options>`` is the contents of environment variable ``APTEST_options`` if set.
  
  In both cases, arguments are extracted using
  `shlex.split() <https://docs.python.org/3/library/shlex.html#shlex.split>`__,
  so are separated by whitespace (e.g. space and newlines characters) unless
  escaped or inside quotes etc.
  
  In ``~/.aptest``, lines starting with ``#`` are ignored.

Commands
^^^^^^^^

.. _build:

build
.....
    Builds and installs packages specified by `-i`_ into venv. Wheels
    are placed in ``aptest-wheelhouse``.

    Also see:

    * `-b`_
    * `--build-type`_
    * `--clean-git`_
    * `--clean-setup`_
    * `--clean-setup-all`_

.. _cibw:

cibw
....
    Build and test packages using cibuildwheel. Wheels are placed
    in directory ``aptest-wheelhouse``, which is initially cleared.
    * We do not install wheels and it is generally not useful to do
    ``cibw test``.

    If CIBW_BUILD is unset, we set it as follows:
    * On Github we build and test all supported Python versions.
    * Otherwise we build and test the current Python version only.

    If CIBW_ARCHS is unset we set $CIBW_ARCHS_WINDOWS, $CIBW_ARCHS_MACOS
    and $CIBW_ARCHS_LINUX to auto64 if they are unset.

    Also see:

    * `--cibw-ignore-test-failures`_
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
    Generate graph showing results from previous runs of ``test-gnn*``.

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
    For packages specified with ``git:...``, populate local checkouts like
    the `build`_ command, but do not actually build/install anything.
    
    Packages are also cleaned if specified.

    Also see:
    
    * `--clean-git`_
    * `--clean-setup`_
    * `--clean-setup-all`_

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
    * Writes results to test-gnn-pymupdf4llm-YYYY-mm-dd-HH-MM-SS.json.

    Results are a dict with this structure:

        ``results['python']``
            Values from python's `platform <https://docs.python.org/3/library/platform>`__
            and `sys <https://docs.python.org/3/library/sys>`__ modules.
        
        ``results['environ']``
            Selected items from Python's `os.environ <https://docs.python.org/3/library/os#os.environ>`__.
        
        ``results['state']``
            Description of what values we passed to ``pymupdf_layout:eval/eval_util.py:evaluate_detection()``.
        
        ``results['packages']``
            Information about each package that we built/installed - version, git branch, sha etc.
            
        ``results['pip-list']``
            Information from ``pip list`` showing information about all packages.
        
        ``results['results']``
            The results from the test.
            
        ``results['t_duration']``
            Duration of test in seconds.
        
        ``results['t_start']``
            Unix start time.

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
    ``<env_name>``.
    
    * Does nothing if ``<env_name>`` is unset.
    * Useful when running via Github action.

.. _-b:

-b <build-packages-modify>
..........................
    Comma-separated ordered list of modifications to the list of
    packages built and installed by the `build`_ command.

    This list defaults to all packages specified by `-i`_. Then for each
    comma-separated item in ``<build-packages-modify>``:

    * ``-<name>``: removes package ``<name>`` from the list.
    * ``+<name>`` and ``<name>``: adds package ``<name>`` to the list.
    * ``-`` removes all packages from the list.

    In addition if the first item does not start with ``+`` or ``-`` we
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
    set ``PYMUPDF_SETUP_MUPDF_REBUILD=0`` so pymupdf will not rebuild its
    mupdf.

.. _--build-type:

-e <name>=<value>
.................
    Set specified environment variable.

.. _--gnn-doit:

.. _-h:

-h
..
    Show this help.
    
    Also see:
    
    * `--help`_.

.. _-i:

-i <package-name> <package-location>
....................................
    Add an input package.

    ``package-name``:

        One of::
        
            aptest
            langchain_pymupdf_layout
            mupdf
            pymupdf
            pymupdf4llm
            pymupdf_layout
            pymupdfpro
            smartoffice
            pdf_feature_inspector
        
        (or their aliases.)

    ``package-location``:
    
        ``pip:``
            Install from https://pypi.org using pip.

        ``pip:<suffix>``
            Install ``<package-name><suffix>`` from https://pypi.org using pip.
            For example ``pip:==1.26.3`` will install version 1.26.3 of
            the package.
        ``pip:*.whl``
            Install from local wheel using pip.
        ``pip:*.tar.gz``
            Install from local sdist using pip.
        ``"git:[-b|--branch <branch>] [--depth <depth>] [-s|--sha <40-char-sha>] [-t|--tag <tag>] [<remote>]"``
            Clone/update from git remote into local checkout
            ``aptest-git-<package-name>``.
            
            * Any local changes in an existing local checkout are deleted.
            
            Defaults:
            
            * branch: hard-coded for each package (typically "master" or "main").
            * remote: hard-coded for each package (typically a Github repository).
            * depth: 1.

        <local-dir>
            Local directory, typically a git checkout.

    If a package is specified twice, the first location will be used
    for building, and the second location used for testing. This allows
    packages on https://pypi.org to be tested, for example:

        ``aptest.py -i pymupdf pip: -i pymupdf PyMuPDF build test``
            Test current pymupdf release with testsuite in ``PyMuPDF/tests``.

        ``aptest.py -i pymupdf pip: -i pymupdf git: build test``
            Test current pymupdf release with testsuite in current git.

    Also see:
    
    * `--langchain-pymupdf-layout`_ and alias `--langchain`_.
    * `--mupdf`_ and alias `-m`_.
    * `--pdf_feature_inspector`_ and alias `--pfi`_.
    * `--pymupdf`_ and alias `-p`_ .
    * `--pymupdfpro`_ and aliases `--pro`_, `-P <-PP_>`_.
    * `--pymupdf4llm`_ and alias `--4llm`_.
    * `--pymupdf_layout`_ and aliases `--layout`_, `-l`_.
    * `--smartoffice`_.

.. _-l:

-l <pymupdf_layout-location>
............................
    Specify location of pymupdf_layout.
    
    Alias for ``-i pymupdf_layout <pymupdf_layout-location>``.
    
    Also see:
    
    * `-i`_.
    * `--layout`_.
    * `--pymupdf_layout`_.

.. _-m:

-m <mupdf-location>
...................
    Specify location of mupdf.
    
    Alias for ``-i mupdf <location>``.
    
    Also see:
    
    * `-i`_.
    * `--mupdf`_.

.. _-o:

-o <os_names>
.............
    Control which OS's we run on. If current OS is not in
    (comma-separated) list ``<os_names>``, we do nothing. ``<os_names>`` is case
    insensitive, and items should match ``linux``, ``windows`` or ``darwin``.

.. _-p:

-p <pymupdf-location>
.....................
    Specify location of pymupdf.
    
    Alias for ``-i pymupdf <location>``.
    
    Also see:
    
    * `-i`_.
    * `--pymupdf`_.

.. _-r:

-r <remote>
...........
    Re-run ourselves on remote machine(s) and on success copy wheels
    back to local machine.

    If ``<remote>`` is ``@github``, we run on Github:

    * We push specified local checkouts directories (specified
      by ``-i``, ``-m``, ``-p`` etc) to branches called ``aptest-$USER`` in the
      central repositories on https://github.com.

    * **Warning**: this will make git forget about any new files in local
      checkouts that have been added but not yet committed.

      This is because we currently push any uncommitted changes as a
      temporary commit, then use ``git reset HEAD~1`` to restore git
      state.

    * We re-run the ``aptest.py`` command on Github machines, changing
      ``-i``, ``-m`` etc args to use ``git:...`` to refer to the above
      repositories.

    * On success we copy Github logs and artifacts
      and extracted wheels etc to local directory:
      
          ``gh_workflow_YYYY-MM-DD-<workflowid>``
          
      Wheels are also copied in flat format into:
      
          ``gh_workflow_YYYY-MM-DD-<workflowid>-union/``.
    
    * Also see:
    
      * `--remote-github-workflow-id`_
      * `--remote-github-yml`_
      * `--remote-github-yml-inputs`_

    Otherwise ``<remote>`` should specify a remote machine on which to run
    aptest:

    * If ``<remote>`` contains one or more spaces it is interpreted as the ssh
      command to use, optionally ending with a colon followed by
      the remote directory to use.

      For example::

          -r 'ssh -p 2222 -J barfoo@mygateway foobar@mymachine.com:testdir'

    * Otherwise ``<remote>`` should be an rsync-style specification such
      as ``macmini`` or ``username@macmini:testdir``.

      Specify a ssh jump host using ``::``, for example::

          -r <gateway>::<remote-host>

    * Local checkouts specified by ``-i`` are copied to the remote
      using rsync, then ``git clean -f`` is run on the remote.
    
    * The ``aptest/`` directory is copied to the remote, using rsync.
    
    * The ``aptest.py`` command (without the ``-r ...`` arguments) is run on the
      remote machine.

    * On success:

      * Wheels are copied back into local directory
        ``aptest-wheelhouse/``.

      * Files matching ``test-gnn-*.json`` are copied back into the
        current directory.
    
    * Also see:
    
      * `--remote-do`_
      * `--remote-prefix`_
      * `--remote-prefix-default`_
      * `--remote-rsync-path`_
      * `--remote-rsync-wsl`_

.. _-t:

-t <test-packages-modify>
.........................
    Comma-separated ordered list of modifications to the list of
    packages tested by the `test`_ command.

    This list defaults to all packages specified by `-i`_ or its aliases.
    
    For each comma-separated item in ``<packages>``:

    * ``-<name>`` removes package ``<name>`` from the list.
    * ``+<name>`` and ``<name>`` adds package ``<name>`` to the list.
    * ``-`` removes all packages from the list.

    In addition if the first item does not start with `+`` or ``-`` we
    first remove all packages from the list.

    We allow aliases for package names.

    For example these test only pymupdfpro::
    
        -t -,pro
        -t -,pymudfpro
        -t pro

    And these remove ``mupdf`` and ``layout`` from the list of packages to test::
    
        -t -m,--layout
        -t -mupdf,-pymupdf_layout

.. _-u:

-u 0|1
......
    If 1 and ``-r @github`` is used, then on success we ask the user to
    confirm and then upload wheels to https://pypi.org.

.. _-v:

-v <venv>
.........
    Changes how we run ourselves in a venv when required.

    0 - Never use a venv.

    1 - Use a venv but without recreating it if the directory already exists.
        We assume any existing directory was created
        by us earlier and is a valid venv containing all necessary packages;
        this saves a little time.

        Otherwise we create it with ``python -m venv ...``.

    2 - Use a venv.
        Always (re)create it with ``python -m venv ...``.

    3 - Use a clean venv.
        Delete it if it already exists, then run ``python -m venv ...``.

    The default is 2.

    The venv will be called ``venv-aptest-<pthonversion>-<wordsize>``, for
    example ``venv-aptest-3.13.5-64``.
    
    We also create a convenience link called ``venv-aptest``.
    
    Also see:
    
    * `--venv-name`_

.. _-PP:

-P <pymupdfpro-location>
........................
    Specify location of pymupdfpro.
    
    Alias for ``-i pymupdfpro <pymupdfpro-location>``.
    
    Also see:
    
    * `--pro`_.
    * `--pymupdfpro`_.

.. _-VV:

-V 0 | 1
........
    Set verbose level.

.. _--atexit:

--atexit <command>
..................
    Run ``<command>`` when aptest terminates.
    
    For example:
    
    * `--atexit 'printf "\\a"'`
    * `--atexit beep`


--build-type debug | memento | release
......................................
    Set build type. Default is ``release``.

.. _--cibw-name:

--cibw-name <cibw_name>
.......................

    Name to use when installing ``cibuildwheel`` for the `cibw`_ command, e.g.::
    
        --cibw-name cibuildwheel==3.0.0b1
        --cibw-name git+https://github.com/pypa/cibuildwheel

    Default is ``cibuildwheel``, i.e. the current release.

.. _--cibw-pyodide:

--cibw-pyodide 0|1
..................
     Make the `cibw`_ command build a pyodide wheel; runs
     ``cibuildwheel --platform pyodide ...`` etc.

.. _--cibw-pyodide-version:

--cibw-pyodide-version <cibw_pyodide_version>
.............................................
    Override default Pyodide version to use with `cibw`_ command
    by setting ``CIBW_PYODIDE_VERSION``.

.. _--cibw-skip-add-defaults:

--cibw-skip-add-defaults 0|1
............................
    If 1 (the default) we add defaults to ``CIBW_SKIP`` such as ``pp*`` (to exclude
    pypy) and ``cp3??t-*`` (to exclude free-threading), which effects the `cibw`_
    command.

.. _--clean-git:

--clean-git <packages>
......................
    Add comma-separated packages/aliases to list of packages for which we run
    ``git clean -fdx`` in the `build`_ and `populate`_ commands.

.. _--clean-setup:

--clean-setup <packages>
........................
    Add comma-separated packages/aliases to list of packages for which we run
    ``setup.py clean`` in the `build`_ and `populate`_ commands.
    
    * As of 2026-02-10, only pymupdf does anything in response to this.
    
    * pymupdf's ``setup.py clean`` deletes files for pymupdf's extension and
      mupdf's C++/Python APIs.
      
    ``--clean-setup pymupdf`` can be useful if pymupdf fails to import mupdf;
    this can be caused by the build system not rebuilding correctly.

.. _--clean-setup-all:

--clean-setup-all <packages>
............................
    Add comma-separated packages/aliases to list of packages for which we run
    ``setup.py clean --all`` in the `build`_ and `populate`_ commands.
    
    * As of 2026-02-10, only pymupdf does anything in response to this.
    
    * pymupdf's ``setup.py clean --all`` deletes files for pymupdf's extension and
      mupdf's C++/Python APIs and the mupdf C API.

.. _--devel:

--devel 0|1
...........
    If 1, output extra information, including:
    
    * File/line information in log messages.
    * Backtraces in error messages.

.. _-e:

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
    Specify expression to use to select which ``test-gnn-*.json`` files to
    include in output created by command `gnn-show`_.

    ``<expression>`` should be a Python expression that looks at Python dict ``results``.

    ``<results>`` will actually be a ``doct.Doct()`` so dotted notation can
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
      * We set ``CIBW_ENABLE=graalpy``.
      * We set ``CIBW_BUILD = 'gp*'``.

    * Otherwise we:

      * Don't create a conventional venv.
      * Clone the latest pyenv and build it.
      * Use pyenv to install graalpy.
      * Use graalpy to create venv.

    [After the first time, suggest ``-v 1`` to avoid delay from
    updating/building pyenv and recreating the graal venv.]

.. _--gnn-show-text:

.. _--help:

--help
......
    Show this help.
    
    Also see:
    
    * `-h`_.

.. _--langchain:

--langchain <langchain-pymupdf-layout-location>
...............................................
    Specify location of langchain-pymupdf-layout.
    
    Alias for ``-i langchain_pymupdf_layout <langchain-pymupdf-layout-location>``.
    
    Also see:

    * `-i`_.
    * `--langchain-pymupdf-layout`_.

.. _--langchain-pymupdf-layout:

--langchain-pymupdf-layout <langchain-pymupdf-layout-location>
..............................................................

    Specify location of langchain-pymupdf-layout.
    
    Alias for ``-i langchain_pymupdf_layout <langchain-pymupdf-layout-location>``.
    
    Also see:

    * `-i`_.
    * `--langchain`_.


.. _--layout:

--layout <pymupdf_layout-location>
..................................
    Specify location of pymupdf_layout.
    
    Alias for ``-i pymupdf_layout <pymupdf_layout-location>``.
    
    Also see:
    
    * `-i`_.
    * `-l`_.
    * `--pymupdf_layout`_.

.. _--mupdf:

--mupdf <mupdf-location>
........................
    Specify location of mupdf.
    
    Alias for ``-i mupdf <mupdf-location>``.
    
    Also see:
    
    * `-i`_.
    * `-m`_.

.. _--pdf_feature_inspector:

--pdf_feature_inspector
.......................
    Specify location of pdf_feature_inspector.
    
    Alias for ``-i pdf_feature_inspector <pdf_feature_inspector-location>``
    
    Also see:
    
    * `-i`_.
    * `--pfi`_.

.. _--pfi:

--pfi <pdf_feature_inspector-location>
......................................
    Specify location of pdf_feature_inspector.
    
    Alias for ``-i pdf_feature_inspector <pdf_feature_inspector-location>``
    
    Also see:
    
    * `-i`_.
    * `--pdf_feature_inspector`_.

.. _--pro:

--pro <pymupdfpro-location>
...........................
    Specify location of pymupdfpro.
    
    Alias for ``-i pymupdfpro <pymupdfpro-location>``.
    
    Also see:
    
    * `-P <-PP_>`_.
    * `--pymupdfpro`_.

.. _--pymupdf:

--pymupdf <pymupdf-location>
............................
    Specify location of pymupdf.
    
    Alias for ``-i pymupdf <pymupdf-location>``.
    
    Also see:
    
    * `-i`_.
    * `-p`_.

.. _--pymupdfpro:

--pymupdfpro <pymupdfpro-location>
..................................
    Specify location of pymupdfpro.
    
    Alias for ``-i pymupdfpro <pymupdfpro-location>``.
    
    Also see:
    
    * `--pro`_.
    * `-P <-PP_>`_.

.. _--pymupdf4llm:

--pymupdf4llm <pymupdf4llm-location>
....................................
    Specify location of pymupdf4llm.
    
    Alias for ``-i pymupdf4llm <pymupdf4llm-location>``.
    
    Also see:
    
    * `-i`_.
    * `--4llm`_.

.. _--pymupdf_layout:

--pymupdf_layout <pymupdf_layout-location>
..........................................
    Specify location of pymupdf_layout.
    
    Alias for ``-i pymupdf_layout <pymupdf_layout-location>``.
    
    Also see:
    
    * `-i`_.
    * `-l`_.
    * `--layout`_.

.. _--pytest:

--pytest <pytest-flags>
.......................
    Specify pytest flags used by `test`_ command; for example
    ``--pytest '-k test_123'``.

.. _--pytest-path:

--pytest-path <pytest_path>
...........................
    Specify a directory/file/test-function to use with the `test`_ command, relative
    to each project root directory. Can be specified multiple times. Default is
    ``<package_root>/tests/``.

.. _--pytest-wrap:

--pytest-wrap gdb | valgrind | helgrind
.......................................
    Makes `test`_ command run tests under specified tool.

.. _--python:

--python <python>
.................
    Set Python to use. If set we re-run ourselves using specified
    python command.

.. _--release-1:

.. _--release-2:

.. _--release-3:

.. _--release-4:

.. _--release-5:

--release-1
...........
--release-2
...........
--release-3
...........
--release-4
...........
--release-5
...........
    Preset args for making releases. Only one may be specified, and it
    must be the only arg.

    ``aptest/aptest.py --release-1``
        Build wheels for pymupdf, pymupdfpro and pymupdf_layout, for all
        platforms except linux-aarch64, linux-x64-musl and win32.
    ``aptest/aptest.py --release-2``
        Build wheels for pymupdf, pymupdfpro and pymupdf_layout, for
        linux-aarch64.
    ``aptest/aptest.py --release-3``
        Build pymupdf wheel for win32.
    ``aptest/aptest.py --release-4``
        Build pymupdf wheel for linux-x64-musl.
    ``aptest/aptest.py --release-5``
        Build pyodide wheel.

.. _--remote-do:

--remote-do 0|1
...............
    [For debugging.]

    If 0 we don't sync to remote and we don't run any commands on
    remote. But we do sync remote wheels to local.

.. _--remote-github-workflow-id:

--remote-github-workflow-id <workflow_id>
.........................................
    Changes behaviour of ``-r @github``. Don't run anything Github,
    instead continue from previous ``-r @github`` invocation by waiting
    for ``<workflow_id>`` to finish and then downloading logs and wheels
    etc to the local machine. Note that one still needs to include
    ``-r @github``.

.. _--remote-github-yml:

--remote-github-yml <yml>
.........................
    With ``-r @github``, run the specified ``.yml`` file (leafname only) instead
    of running ``aptest.py``.
    If no packages are specified, runs on Github's
    ``ArtifexSoftware/aptest`` repository; otherwise exactly one package
    must be specified.

.. _--remote-github-yml-inputs:

--remote-github-yml-inputs <inputs>
...................................
    Specify inputs used with `--remote-github-yml`_. ``<inputs>`` should be a
    comma-separated list of ``<name>=<value>`` pairs.
    
    For example if the .yml file has::
    
        on:
          workflow_dispatch:
            inputs:
              args:
                type: string
                default: ''
                description: 'Arguments to pass to aptest.py'
    
    Then::
    
        --remote-github-yml-inputs 'args=-o windows'

.. _--remote-prefix:

--remote-prefix <remote_prefix>
...............................
    Run remote using specified Python command. Ignored by ``-r @github``.

.. _--remote-prefix-default:

--remote-prefix-default <remote> <prefix>
.........................................
    Sets default remote prefix for a specific remote when specified with
    ``-r <remote>``. For example to always use python-3.12 on remote machine
    ``jules-asus``, use::

        --remote-prefix-default jules-asus python312
    
    (It can be useful to put this in ``~/.aptest``.)

.. _--remote-rsync-path:

--remote-rsync-path <remote_rsync_path>
.......................................
    Specify ``--rsync-path`` when running rsync, to identify location of
    rsync on remote. E.g. ``--remote-rsync-path 'wsl rsync'`` if remote is
    a Windows machine with rsync installed in the default WSL system.

.. _--remote-rsync-wsl:

--remote-rsync-wsl 0|1
......................
    [Experimental.]

    Tweak various things to cope with remote using wsl rsync.

.. _--run:

--run <package> <command>
.........................
    Make `run`_ command run the specified command within checkout of
    ``<package>``.

.. _--sdists:

--sdists 0|1
............
    If 1, the `build`_ and `cibw`_ commands will also build sdists.

.. _--smartoffice:

--smartoffice
.............
    Specify location of smartoffice.
    
    Alias for ``-i smartoffice <smartoffice-location>``.
    
    Also see:
    
    * `-i`_.

.. _--swig:

--swig <swig>
.............
    Use ``<swig>`` instead of the ``swig`` command.

    Unix only:
        Clone/update/build swig from a git repository using 'git:' prefix.

        We default to https://github.com/swig/swig.git branch master, so these
        are all equivalent::

            --swig 'git:--branch master https://github.com/swig/swig.git'
            --swig 'git:--branch master'
            --swig git:

        2025-08-18: This fixes building with ``py_limited_api`` on python-3.13.

.. _--swig-quick:

--swig-quick 0|1
................
    If 1 and `--swig`_'s ``<swig>`` value starts with ``git:``, we do not
    update/build swig if it is already present.

.. _--system-packages:

--system-packages 0|1
.....................
    If 1, automatically install required system packages such as
    Valgrind, using ``apt`` on Linux and ``brew`` on MacOS. Default is 1 if
    running as Github action, otherwise 0.

.. _--system-site-packages:

--system-site-packages 0|1
..........................
    If 1, use ``--system-site-packages`` when creating venv. Defaults is 0.

.. _--test-extra-packages:

.. _--tee-auto:

--tee-auto 0|1
..............
    If 1, we copy log output to file ``aptest-out-YYYY-mm-dd-HH-MM-SS``, and on
    exit create convenience softlink ``aptest-out``.
    
    Default is 0.

.. _--tee-path:

--tee-path <path>
.................
    Copy log output to file ``<path>``.
    
    Default is 0.

--test-extra-packages <names>
.............................
    Installs specified comma-separated packages from https://pypi.org before
    running tests in `test`_ command.

.. _--test-gnn-cache:

--test-gnn-cache 0|1
....................
    If 1, ``test-gnn*`` commands look for a matching ``test-gnn-*.json``
    file. If one is found, we do not run, instead creating softlinks to
    the matching ``.json`` file.

    To match, we require all fields in a ``.json`` file match the file
    that we would create for the current run, except for:

    * ``['results']`` - not available for the current run, obviously.
    * ``['t_start']``
    * ``['t_duration']``
    * ``['pip-list']`` - we allow changes to misc other packages, e.g. version numbers may vary.

    We require the other settings to be identical, such as:

    * OS, machine name, username etc.
    * Python version, implementation etc.
    * How Artifex pckages were specified, e.g. ``-p git:`` or ``-p pip:``.
    * git sha's and diffs for Artifex packages specified with ``git:`` or local checkout.
    * https://pypi.org version numbers for Artifex packages specified with ``pip:...``.
    * Any `--test-gnn-limit`_ value.

.. _--test-gnn-extra:

--test-gnn-extra <key>=<value>
..............................
    Adds specified ``key=value`` pair to the root of the results dict
    created by ``test-gnn*`` commands.

.. _--test-gnn-limit:

--test-gnn-limit <limit>
........................
    Set number of gnn files to test. Default is all.

.. _--test-gnn-out:

--test-gnn-out <path>
.....................
    Where to write json data containing test details. Default is a filename
    containing the current date and time.

.. _--test-gnn-push:

--test-gnn-push 0|1
...................
    If 1, we push gnn results to
    https://github.com/ArtifexSoftware/PyMuPDF-pymupdf-results. Default is 0.

.. _--cibw-ignore-test-failures:

--cibw-ignore-test-failures 0|1
...............................
    If 1, the `cibw`_ command ignores test failures. Default is 0.

.. _--ticker:

--ticker <delay>
................
    Use ticker with specified delay. Disabled if ``delay==0``. Default is
    0.5.

.. _--venv-name:

--venv-name <venv_name>
.......................
    Sets the venv name used by `-v`_.
    
    Default is ``venv-aptest-<python-version>-<word-size>``,
    for example ``venv-aptest-3.14.2-64``.

.. _--4llm:

--4llm <location>
.................
    Specify location of pymupdf4llm.
    
    Alias for ``-i pymupdf4llm <location>``.
    
    Also see:
    
    * `-i`_.
    * `--pymupdf4llm`_.

.. _--4llm-unified:

--4llm-unified 0|1
..................

    If 1 we assume any pymupdf4llm package has been created by merging
    pymupdf4llm into the layout git repository (ArtifexSoftware/sce on Github).

Special arguments
^^^^^^^^^^^^^^^^^

.. _completion:

completion
..........
    Must be the only arg. Prints a bash completion script for
    aptest.py, to stdout.

    The script works by using aptest.py itself to write valid
    completions to stdout (which it does if environment variable
    ``COMP_LINE`` is defined).

    If ``APTEST_COMPLETION_DEBUG`` is defined, it is a path to which
    diagnostics are appended.


Changelog
---------

**2026-02-10**

* Improved output after downloading from Github.
* Added `--cibw-ignore-test-failures`_.
* Renamed ``--log-tee`` to `--tee-auto`_.
* Added `--tee-path`_.
* Added `--atexit`_.

**2026-02-09**

* Changed `-V <-VV_>`_ to take the verbose level (0 or 1) instead of incrementing it.
* Changed default verbose level to 1.
* Show git sha and diff of aptest itself on startup if verbose.
* `cibw`_: don't attempt to build/test layout on macos-intel-python3.14
  because onnxruntime not available.
* Fixed .github/workflows/test_multiple.yml failures.
* Improved error diagnostics.
* Improved clean options.


**2026-02-05**

* Added `--atexit`_
* Fix `--smartoffice`_ to use ``thirdparty-so-key``.
* Optionally copy output to date-stamped file. See ``--log-tee``.
* Improved sorting of options in ``README.rst``.
* Improved handling of ``-p pip:`` - we now set ``PYMUPDF_SETUP_VERSION`` so other
  packages will match correctly.
* Fix ``--smartoffice git:`` on Github - use ``PYMUPDFPRO_SETUP_SOT_KEY`` if set.
* Added test of pymupdfpro with latest smartoffice to Github tests.
* Fix `-b`_ and `-t`_ to do nothing if given empty string value.
* In ``~/.aptest``, ignore lines starting with ``#``.

**2026-01-31**

* Update tests to use mupdf 1.27.x branch.
* Added experimental support for unified 4llm+layout package; see `--4llm-unified`_.

**2026-01-30**

* Allow testing of aptest itself.
* Added `--release-5`_ for building pyodide pymupdf wheel.
* Avoid remaining potential for ``build`` command to end up installing incorrect package versions.


**2026-01-15**

* Fix potentially incorrect package versions if ``pip:`` is used.
* Fix flake8 errors.
* Fix codespell errors.
* All docs are now in ``README.rst``.
