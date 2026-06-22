.. section-numbering::
    :depth: 2

Aptest - artifex python packages build/test system
==================================================

.. contents::
    :backlinks: entry
    :depth: 2


Overview of Aptest
------------------

Aptest is a command-line programme that can build, test and release (to
https://pypi.org) multiple Artifex Python packages together.

Aptest is hosted at https://github.com/ArtifexSoftware/aptest.


License
-------

GNU Affero General Public License v3.0 only.

* See file `<COPYING>`__.


How to run Aptest
-----------------

Aptest can be run in various ways:


* Run directly from local Aptest Git checkout, using command ``aptest/aptest.py``::

    git clone git@github.com:ArtifexSoftware/aptest.git
    aptest/aptest.py ...

* Install into current venv from local Aptest Git checkout, and use command ``aptest``::

    git clone git@github.com:ArtifexSoftware/aptest.git
    pip install ./aptest
    aptest ...

* Install into current venv from remote Aptest Git repository, and use command ``aptest``::

    pip install git+ssh://git@github.com/ArtifexSoftware/aptest.git
    aptest ...

* Use `pipx <https://pypi.org/project/pipx/>`_ with local Aptest Git checkout::

    git clone git@github.com:ArtifexSoftware/aptest.git
    pipx run ./aptest ...

* Use `pipx <https://pypi.org/project/pipx/>`_ with remote Aptest Git repository::

    pipx run artifex_aptest@git+ssh://git@github.com/ArtifexSoftware/aptest.git ...


Python virtual environments
---------------------------
If one is already in a venv:

* Aptest will use the venv directly,
  for example the `build`_ command will install packages into this venv.

Otherwise:

* Aptest will create, enter and use its own venv,
  called ``venv-aptest-<pthonversion>-<wordsize>``.
* For convenience,
  a symbolic link ``venv-aptest`` will be created that points to this venv.


Supported packages
------------------

* ``langchain_pymupdf_layout``
* ``mupdf``
* ``pdf2docx``
* ``pdf_feature_inspector``
* ``pymupdf``
* ``pymupdf4llm``
* ``pymupdf_layout``
* ``pymupdfpro``
* ``smartoffice``
* ``smartoffice-marina``
* ``smartoffice-neo``

Notes:

* Only one of ``smartoffice``, ``smartoffice-marina`` and ``smartoffice-neo`` can be specified.
* ``mupdf``, ``smartoffice``, ``smartoffice-marina`` and ``smartoffice-neo`` are pseudo packages.

  They are not built into python wheels, instead:

  * ``mupdf`` is built into ``pymupdf``.
  * ``smartoffice``, ``smartoffice-marina`` and ``smartoffice-neo`` are built into ``pymupdfpro``.

See the `-i`_ option.


Package locations
-----------------

* A local checkout.
* Specific branch, tag or sha on remote git repository.
* https://pypi.org.

See the `-i`_ option.


Building packages
-----------------

For each package:

* If package was specified with ``pip:...``
  
  * A wheel will be downloaded and installed from https://pypi.org.

* Otherwise:

  * If package was specified with ``git:...`` we clone/update a local checkout.

  * The package is built locally into a wheel with ``pip wheel``.
  * This will typically take place in an internal pip venv.
  * The wheel is installed into the current venv.
  
  * Note that the wheel will be specific to the current system
    and might not work on other systems with the same OS.
    
    For example on Linux it will require at least the current system's glibc.
    
    If you need a more portable wheel, use the `cibw`_ command.
  
* The wheel is added to a local pypi-style PEP 503 package repository.
* We use pip's ``--extra-index-url`` option to refer to our internal package
  repository.
* Thus pip will use previously built package wheels as prerequisites, as required.

See the `build`_ command.


Testing packages
----------------

* We run tests for each package, using `pytest <https://docs.pytest.org>`_.
* Packages on https://pypi.org do not contain test suites, but one can specify a second
  package location to be used for testing, for example a local checkout or
  remote git repository.

* One can generate traces of MuPDF calls by setting environment variables in debug
  builds. For details see:
  https://mupdf.readthedocs.io/en/latest/language-bindings.html#environmental-variables

See the `test`_ command.


Build/test with cibuildwheel
----------------------------

* Instead of separately building and testing packages, Aptest can use `cibuildwheel <https://cibuildwheel.pypa.io/en/stable/>`__.
* This builds a wheel, and runs tests using `pytest <https://docs.pytest.org>`_.
* We add each wheel to our internal package repository.
* We set ``PIP_EXTRA_INDEX_URL`` to point to our internal package repository.
* cibuildwheel uses pip internally so this ensures that previously-built
  prerequisite wheels will be installed as required.
*
  Note that, unlike testing with the `test`_ command,
  prerequisite packages can
  override packages specified to Aptest.
  We try to avoid this by setting PYMUPDF_SETUP_VERSION
  but generally one should use `build`_ and `test`_ when testing non-standard versions.

See the `cibw`_ command.


Things to be careful of
-----------------------

Rebuild all packages each time Aptest is used
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Aptest tries to be cautious when building/rebuilding and,
by default,
it will remove the contents of the wheelhouse before building anything,
so don't assume previous builds will be available.
  
* So for example when building pymupdf4llm,
  if one intends to use the new build of pymupdf4llm with a similar new build of pymupdf
  (instead of pymupdf from pypi.org),
  then one should also build pymupdf, for example with:
  
  ``aptest/aptest.py -m=git: -p=git: --4llm pymupdf4llm build``
  
  Usually rebuilding pypmupdf like this will be faily quick.


Examples
--------

[Also see `Python virtual environments`_ for information about where wheels are
generated/installed.]

Using local checkouts, build packages ``pymupdf``, ``pymupdfpro`` and ``pymupdf_layout``
(putting wheels into directory ``aptest-wheelhouse/``),
install (into current venv or ``venv-aptest-<pthonversion>-<wordsize>``)
and test:

    ``aptest/aptest.py -p PyMuPDF --pro PyMuPDFPro -m mupdf --layout sce build test``

Similarly build, install and test ``pymupdf``, ``pymupdfpro`` and ``pymupdf_layout`` using
central git repositories:

    ``aptest/aptest.py -p git: --pro git: --layout git: build test``

Make release, building/testing on Github, downloading to local machine,
and uploading to https://pypi.org (also see `Release procedure`_)::

    aptest/aptest.py --release-1
    aptest/aptest.py --release-2
    aptest/aptest.py --release-3
    aptest/aptest.py --release-4
    aptest/aptest.py --release-5
    aptest/aptest.py --release-6

Build/test ``pymupdf``, ``pymupdfpro`` and ``pymupdf-layout`` using cibuildwheel,
getting packages from different locations:

    ``aptest/aptest.py -r @github -p pip: --pro PyMuPDFPlus --layout git: cibw``

Test current ``pymupdf`` release with latest test suite in central git:

    ``aptest/aptest.py -p pip: -p git: build test``

Test current ``pymupdf`` release with test suite in local checkout:

    ``aptest/aptest.py -p pip: -p PyMuPDF build test``

Runs specific Github workflow ``PyMuPDFPlus/.github/workflows/test_multiple.yml``, on windows only:

    ``aptest/aptest.py -r @github --remote-github-yml test_multiple.yml --pro PyMuPDFPlus --remote-github-yml-inputs --remote-github-runners windows``

Test `<https://pypi.org>`_'s ``pymupdf``, ``pymupdfpro`` and ``pymupdf_layout`` with the test
suites on central git:

    ``aptest/aptest.py -r @github -p pip: --pro pip: --layout pip: -p git: --pro git: --layout git: build test``

Download wheels from a previous Aptest Github workflow run:

    ``aptest/aptest.py -r @github --aptest aptest --remote-github-workflow-id 21760695687``

Test Aptest itself:

    ``aptest/aptest.py --aptest aptest test``

Build/test ``pymupdfpro`` with alternative ``smartoffice-neo``:

    ``aptest/aptest.py --smartoffice-neo git: --pro git: build test``

Build/test ``pymupdfpro`` with alternative ``smartoffice-marina``:

    ``aptest/aptest.py --smartoffice-marina git: --pro git: build test``

Run ``pymupdf_layout`` gnn tests with ``mupdf`` version 1.27.2, current ``pymupdf`` in git, and local checkout ``sce/`` of ``pymupdf_layout`` (this assumes that the DocLayNet dataset has been downloaded, see `Using DocLayNet dataset`_):

    ``aptest/aptest.py --test-gnn-det eval/eval_pymupdf_layout.py -m=git:'-t 1.27.2' -p=git: --layout=sce test-gnn``


Making internal development releases
------------------------------------

It can be useful to build wheels for commonly-used systems from the latest code in central git,
and make them generally available for testing.

Building development wheels
^^^^^^^^^^^^^^^^^^^^^^^^^^^
First create a separate wheelhouse directory,
with a special file that prevents Aptest from deleting it.
This allows one to have multiple wheel versions in the same place:

* ``mkdir -p wheels-test``
* ``touch wheels-test/_aptest_wheelhouse_preserve``

Build wheels on Github,
forcing version ``1.28.0a1`` for packages starting with ``pymupdf`` by setting ``PIPCL_CHANGE_VERSIONS``.
This will default to creating wheels for ``windows-x64``, ``linux-x64`` and ``macos-arm64``:

* ``aptest/aptest.py --wheelhouse wheels-test -m=git: -p=git: --layout=git: --4llm=git: -r @github cibw -e 'PIPCL_CHANGE_VERSIONS=^pymupdf.* 1.28.0a1'``

Upload wheels and pypi database to web server:

* ``aptest/aptest.py --wheelhouse wheels-test draft --draft-location julian@ghostscript.com:public_html/wheels-test/``

Using development wheels
^^^^^^^^^^^^^^^^^^^^^^^^

View wheels on web server at:

* ``https://ghostscript.com/~julian/wheels-test``

Install wheels from the web server with one of:

* ``pip install --pre --upgrade --extra-index-url https://ghostscript.com/~julian/wheels-test/simple pymupdf4llm``
* ``pip install --extra-index-url https://ghostscript.com/~julian/wheels-test/simple pymupdf4llm==1.28.0a1``

Release procedure
-----------------

Instructions for releasing wheels for:

    * ``pdf4llm``
    * ``pymupdf``
    * ``pymupdf4llm``
    * ``pymupdf_layout``
    * ``pymupdfpro``


* Get local checkout of latest version of each package, corresponding to what will be released.

* Ensure that pymupdf's ``setup.py`` specifies the correct mupdf version.

  If this is not the case, update, commit, push, and wait for the next
  overnight tests to pass before making the release.

* Ensure the version number is correct in all packages.

  * All packages should have the same version number.
  * Version numbers are always defined in ``setup.py``.
  * Version numbers may also be defined in other files such as ``README`` and ``CHANGES``.
  * ``pymupdf`` has a test that checks version numbers in ``changes.txt`` etc are
    consistent with ``setup.py``.

* Ensure that ``pymupdf``'s Github issues and ``changes.txt`` are synchronised.

  * Go to https://github.com/pymupdf/PyMuPDF/issues.
  * For all issues that are labeled as ``Fixed in next release``, ensure that
    they are labelled as fixed in ``changes.txt``.
  * For all issues mentioned as fixed in ``changes.txt``, ensure that
    the corresponding Github issue is labelled as ``Fixed in next release``.

* Test local checkouts of all packages on Github machines:

    ``aptest/aptest.py -r @github -p PyMuPDF --pro PyMuPDFPro --layout sce --4llm pymupdf4llm --pdf4llm pymupdf4llm cibw``

* In `~/.aptest`_, specify package sources for releases.

  This is done with upper-case versions of the usual package-specifier options,
  so that different `--release-*`_ options can select different subsets
  (see `-i`_'s `upper-case-package names`_ section).
  
  To use local checkouts:

      ``-P PyMuPDF --PRO PyMuPDFPlus --LAYOUT sce --4LLM pymupdf4llm --PDF4LLM pymupdf4llm``
  
  Or to use specific sha's for each package:

      ``-P 'git:--sha ...' --PRO 'git:--sha ...' --LAYOUT 'git:--sha ...' --4LLM 'git:--sha ...' --PDF4LLM 'git:--sha ...'``

  Or to use the latest remote versions in git:
  
      ``-P git: --PRO git: --LAYOUT git: --4LLM git: --PDF4LLM git:``
  
* In `~/.aptest`_, specify an empty release wheelhouse directory, for example:
  
    ``--wheelhouse-release release-1.27.2``

  This will eventually hold all release wheels and sdists prior to them being
  uploaded to https://pypi.org.

* Build wheels for all packages:

    ``aptest/aptest.py --release-1``
  
    ``aptest/aptest.py --release-2``
  
    ``aptest/aptest.py --release-3``
  
    ``aptest/aptest.py --release-4``
  
    ``aptest/aptest.py --release-5``
  
    ``aptest/aptest.py --release-6``

  These commands can be manually run in parallel using individual terminals.
    
  On success this will populate the release wheelhouse with all wheels and sdists
  
  Also see:
  
  * `--release-*`_.
  
* Make manual tests of the generated wheels before uploading.

  Install from local wheels:
  
  * Use the location specified by `--wheelhouse-release`_ in `~/.aptest`_,
    with ``pip install``'s ``--extra-index-url``, for example:

      ``pip install --extra-index-url release-1.27.2 pdf4llm pymupdfpro``

  Or upload to, and install from, a web server:
  
  * ``aptest/aptest.py draft --draft-location julian@ghostscript.com:public_html/wheels-1.27.2/`` --wheelhouse release-1.27.2.
  
  * ``pip install --extra-index-url https://ghostscript.com/~julian/wheels-1.27.2/simple pdf4llm pymupdfpro``
  
  Test the wheels:
  
  * Enter a venv.
  
  * ``pip install pytest``
  
  * ``pytest PyMuPDF/tests`` etc.


* Make the release by uploading all wheels and sdists to https://pypi.org/:

  ``aptest/aptest.py upload``

* Release pyodide wheel.

  **2026-06-15**: pypi.org now accepts pyodide wheels.
  
  * See: https://github.com/pymupdf/PyMuPDF/issues/5025
  * Need to update aptest.py to include pyodide wheels in upload.

  Old:
  
      Copy/rsync the pyodide wheel in the release directory to
      ``julian@ghostscript.com:public_html/pyodide/``, for example:

        ``rsync -ai release-1.27.2/pymupdf-1.27.2-cp313-abi3-pyodide_2025_0_wasm32.whl julian@ghostscript.com:public_html/pyodide/``

      This will be available in: https://ghostscript.com/~julian/pyodide/.

      Tell ``@jamie`` about the Pyodide wheel.

      [2026-01-30: hopefully we'll have a more official location soon.]

* Update central repositories:

  * Repositories are:
  
    * ``PyMuPDF``
    * ``PyMuPDFPro``
    * ``pymupdf4llm``
    * ``sce``
  
  * If building with local checkouts, push each to github.

  * Tag each repository:

    * We use the version number as the tag, e.g. ``1.26.7``.
    * For each repository::

        git tag <version>
        git push origin <version>

* Extra updates to Github's ``pymupdf`` repository.

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
      
        See: https://github.com/pymupdf/PyMuPDF/discussions/<announcement-id>

* Possible post-release changes:

  For all projects.
  
  * Increment version in all package ``setup.py`` files.

  Extra post-release changes for ``pymupdf``.

  * In ``pymupdf``'s ``changes.txt``:

    * Add date of release that was just made.
    * Add title for next release ``**Changes in version <next-version>**``.

  * In ``pymupdf``'s ``.github/ISSUE_TEMPLATE/bug_report.yml``:

    * Add version of next release to drop-down list of versions.

      (This is required for tests to pass.)


Details
-------


Run remotely
^^^^^^^^^^^^

Aptest can transparently re-run itself in remote locations:

* Remote machine (with ssh/rsync).
* Github runner (push to unique(ish) branches and run a workflow).

See the `-r`_ option.


Use of Python venv virtual environments
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If Aptest is not already running inside a Python venv, it automatically creates a
venv and re-runs itself inside it.

* The `build`_ command builds and installs into the current venv.
* The `test`_ command tests packages that are installed in the current venv.

See the `-v`_ option.


Pytest junit .xml output
^^^^^^^^^^^^^^^^^^^^^^^^

If `--pytest-junit-xml`_ is specified,
then when running `pytest <https://docs.pytest.org>`_ with the `test`_ and `cibw`_ commands,
Aptest specifies ``--junit-xml=aptest-wheelhouse/<package-name>-pytest-junit.xml``,
which generates an .xml file containing the test results.

The .xml file is also copied back to local machine along with .whl files if `-r`_ is used.

Also see https://docs.pytest.org/en/stable/how-to/output.html#creating-junitxml-format-files.


Cleaning packages
^^^^^^^^^^^^^^^^^

Packages can be cleaned before building or when populating.

See the `--clean-git`_, `--clean-setup`_ and `--clean-setup-all`_ options.


Cibuildwheel Python versions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Cibuildwheel needs a system install of required python version(s).

On Macos:

* Installing python versions with brew does not seem to work - cibuildwheel
  cannot find them.

* What does work is to use the official installers at https://python.org.

  These commands install the latest builds of Python, as of 2026-02-25::

    wget https://www.python.org/ftp/python/3.10.11/python-3.10.11-macos11.pkg && sudo installer -pkg python-3.10.11-macos11.pkg -target /
    wget https://www.python.org/ftp/python/3.11.9/python-3.11.9-macos11.pkg && sudo installer -pkg python-3.11.9-macos11.pkg -target /
    wget https://www.python.org/ftp/python/3.12.10/python-3.12.10-macos11.pkg && sudo installer -pkg python-3.12.10-macos11.pkg -target /
    wget https://www.python.org/ftp/python/3.13.12/python-3.13.12-macos11.pkg && sudo installer -pkg python-3.13.12-macos11.pkg -target /
    wget https://www.python.org/ftp/python/3.14.3/python-3.14.3-macos11.pkg && sudo installer -pkg python-3.14.3-macos11.pkg -target /

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


Workarounds and problems
^^^^^^^^^^^^^^^^^^^^^^^^

(2026-02-06) With `cibw`_ we do not test with python-3.14 on Windows
....................................................................

    When cibuildwheel internally attempts to install packages with ``pip
    install`` (with ``PIP_EXTRA_INDEX_URL`` pointing to our piprepo wrapping of
    aptest-wheelhouse), pip complains::

        WARNING: Location 'file://D:/a/aptest/aptest/aptest-wheelhouse/simple/pymupdf/' is ignored: it is neither a file nor a directory.
        INFO: pip is looking at multiple versions of pymupdfpro to determine which version is compatible with other requirements. This could take a while.
        ERROR: Could not find a version that satisfies the requirement PyMuPDF==1.27.1 (from pymupdfpro) (from versions: ...)
        ERROR: No matching distribution found for PyMuPDF==1.27.1

    I.e. prerequisite packages are not found, despite being in
    ``aptest-wheelhouse``.

    This failure does not happen with python-3.10-3.13.

(2026-02-08) Use of setuptools<81 for piprepo
.............................................

    Package piprepo requires package ``pkg_resources``,
    which is part of setuptools,
    but only setuptools<81.

(2026-06-18) Use under Visual Studio on Windows
...............................................

Running Aptest within a Visual Studio session has been known to give confusing results,
possibly due to using a different working directory.

So it's recommended to run Aptest within a standard Windows terminal instead.


Keys/tokens
^^^^^^^^^^^

Aptest allows different keys to be used when it runs operations such as git
commands, pypi uploads and Github ReST operations.

* Keys can be in files or environment variables.

* Keys are selected by matching a prefix against git remotes, urls etc.

Use of keys with remote runs
............................

* If the `-r`_ option is used to defer to a remote machine,
  all specific key files are copied to the remote machine.
  
  * This is probably only usable if key files are in the current directory.
  
  * This obviously has security implications.

* If the `-r`_ option is used to defer to a Github runner with `-r @github`_,
  we rely on the Github Aptest repository https://ArtifexSoftware/aptest
  having secrets that allow the required access,
  and one should specify the corresponding environment variables using the `--key`_ option.

To create a github ReST token:

* Follow instructions for creating a "classic" token at
      https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#creating-a-personal-access-token-classic.
* In ``scopes``, select just ``repo``.

Default keys when running on Github
...................................
If running as a Github action (``GITHUB_ACTIONS==true``), we add the
Aptest github repository secrets ``ARTIFEX_SOFTWARE_SSH_KEY`` and
``PYMUPDFPRO_SETUP_SOT_KEY`` as keys for use with git operations on Github and
Gitlab.

Also see:

* `--key`_.


Using DocLayNet dataset
.......................

The `gnn-download`_ command downloads/extracts the DocLayNet dataset as described in
https://github.com/ArtifexSoftware/sce/wiki/How-to-train-GNN.

* Downloading and extracting is tracked using marker files, to avoid running
  unnecessarily more than once.

* The `test-gnn`_ command runs ``pymupdf_layout`` tests on the DocLayNet dataset,
  depending on the `--test-gnn-det`_ value.

* The ``pymupdf_layout`` package must have been built/installed.


Argument completion with Bash
.............................

Aptest has support for customised bash argument completion using ``<tab>``.

Activate in the current bash session with::

    source <(aptest/aptest.py completion)

Alternatively activate in all new bash sessions with one of::

    aptest/aptest.py completion > /etc/bash_completion.d/aptest.py.bash_completion
    aptest/aptest.py completion >> ~/.bash_completion

* Also see special command  `completion`_.


Command-line arguments
----------------------

.. contents::
    :local:


Overview
^^^^^^^^

Commands and options
....................
* Command line arguments are called options if they start with ``-``,
  otherwise they are called commands.
* Options are evaluated first in the order that they were specified.
* Then commands are run in the order in which they were specified.
* Usually command `test`_ would be specified after commands such as `build`_.
* Options and commands can be interleaved but it may be clearer to separate
  them on the command line.


Option values
.............
Option values can be specified with ``--foo <value>`` or ``--foo=<value>``.


Bool options
............

Bool options are handled specially, they set to true by default, and can be
set explicitly using ``--foo=<value>``:
  
Set to true:

* ``--foo``
* ``--foo=1``
* ``--foo=true``
* ``--foo=True``

Set to false:

* ``--foo=0``
* ``--foo=false``
* ``--foo=False``

.. _~/.aptest:


Default arguments in file ~/.aptest
...................................
If this file exists, its contents are inserted before the command-line arguments.

* The tilde is expanded with ``os.path.expanduser()``,
  so on Windows this could be ``C:/Users/<username>/.aptest``.
* The file is ignored if the environment has ``APTEST_DOT_APTEST=0``.

The contents are extracted as follows:

* Lines starting with ``#`` are ignored.
* Arguments are extracted using `shlex.split()
  <https://docs.python.org/3/library/shlex.html#shlex.split>`__,
  so are separated by whitespace
  (e.g. space and newlines characters)
  unless escaped or inside quotes etc.


.. _$APTEST_options:
  
Default arguments in $APTEST_options
....................................

If environmental variable ``$APTEST_options`` is set, it is added to the
command line after any `~/.aptest`_ and before the command-line arguments.

*
  Arguments are extracted using `shlex.split()
  <https://docs.python.org/3/library/shlex.html#shlex.split>`__.


Commands
^^^^^^^^

build
.....
    Builds and installs packages specified by `-i`_ into venv. Wheels
    are placed in ``aptest-wheelhouse``.

    Also see:

    * `-b`_
    * `--build-pip-no-clean`_
    * `--build-type`_
    * `--clean-git`_
    * `--clean-setup`_
    * `--clean-setup-all`_

cibw
....
    Build and test packages using `cibuildwheel <https://cibuildwheel.pypa.io>`_.
    Wheels are placed in directory ``aptest-wheelhouse``.
    
    * We do not install wheels and it is generally not useful to do
      ``cibw test``.

    If ``CIBW_BUILD`` is unset:
    
    * On Github we set ``CIBW_BUILD`` to build and test with all supported Python versions.
    * Otherwise we set ``CIBW_BUILD`` to build and test with the current Python version only.
    
    If ``CIBW_BUILD`` is ``all``:
    
    * We set CIBW_BUILD to build and test with all supported Python versions.

    If ``CIBW_ARCHS`` is unset:
    
    * We set ``CIBW_ARCHS_WINDOWS``, ``CIBW_ARCHS_MACOS`` and ``CIBW_ARCHS_LINUX``
      to ``auto64`` if they are unset.
    
    `cibuildwheel <https://cibuildwheel.pypa.io>`_ cannot handle pure python packages,
    so we manually build+test such packages.
    
    * This will use the current python version only,
      and not (for example) a manylinux docker on Linux.
      
    * For example with the pure-python package ``pymupdf4llm``,
      we only test ``pymupdf4llm`` + ``pymupdf_layout`` + ``pymupdf`` together on native Python.
    
    * Unlike the `build`_ and `test`_ commands,
      `cibw`_ requires that packages have compatible version numbers,
      otherwise it will fail.
    
      * It's non-trivial to support incompatible version numbers with
        `cibuildwheel <https://cibuildwheel.pypa.io>`_.
      * `cibw`_ is generally used to build releases,
        for which version numbers should match anyway.

    Also see:

    * `--cibw-ignore-test-failures`_
    * `--cibw-name`_
    * `--cibw-pyodide`_
    * `--cibw-pyodide-version`_
    * `--cibw-skip-add-defaults`_


docs
....
    Convert `<README.rst>`__ into `<README.rst.html>`__.
    
    Currently uses `docutils <https://pypi.org/project/docutils/>`__.


draft
.....
    Rsync the wheelhouse directory to the location specified by `--draft-location`_.
    
    * The wheelhouse will contain a ``simple/`` directory created by ``piprepo``,
      so one can pip install with:
      
      ``pip install --extra-index-url ``<url>/simple``.
      
      where ``<url>`` is the URL of the draft location.
      
    * We will also sync a piprepo subdirectory ``simple/`` that will

    Also see:

    * `--wheelhouse-release`_.


gnn-download
............
    Download and extract dataset for the ``pymupdf_layout`` GNN model. Does not
    do unnecessary downloads or extracts.


gnn-show
........
    Generate graph showing results from previous runs of `test-gnn`_.

    For example::

        aptest/aptest.py gnn-show --gnn-show-select \
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


gnn-train
.........
    Trains ``pymupdf_layout``. Not tested.


populate
........
    For packages specified with ``git:...``, populate local checkouts like
    the `build`_ command, but do not actually build/install anything.
    
    Packages are also cleaned if specified.

    Also see:
    
    * `--clean-git`_
    * `--clean-setup`_
    * `--clean-setup-all`_

run
...
    Runs commands specified by `--run`_ within checkouts.


test
....
    Runs `pytest <https://docs.pytest.org>`_ tests.

    Also see:

    * `--pytest`_
    * `--pytest-path`_
    * `--pytest-wrap`_
    * `-t`_
    * `--test-extra-packages`_


test-gnn
.........

    * Test GNN model
    * Writes results to ``test-gnn-results/test-gnn-YYYY-mm-dd-HH-MM-SS.json``.
    * Requires `--test-gnn-det`_.

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
    * `--test-gnn-det`_
    * `--test-gnn-extra`_
    * `--test-gnn-limit`_
    * `--test-gnn-out`_
    * `--test-gnn-push`_


upload
......
    Upload all wheels and sdists in directory specified by `--wheelhouse-release`_, to https://pypi.org.


windows-show-vs-instances
.........................
    Show available Visual Studio installs.


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


.. _-e:

-e <name>=<value>
.................
    Set specified environment variable.


.. _--git-remote-modify:

--git-remote-modify <prefix> <replacement>
..........................................

    When cloning/fetching from git remotes, replace <prefix> with <replacement>.

    For example: ``--git-remote-modify git@github.com: https://github.com/``
    
    Also see:
    
    * `-i`_.


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
            pdf2docx
            pdf_feature_inspector
            pymupdf
            pymupdf4llm
            pymupdf_layout
            pymupdfpro
            smartoffice
            smartoffice-marina
            smartoffice-neo
        
        (or their aliases.)

    ``package-location`` should be one of:
        
        ``"git:[-b|--branch <branch>] [--depth <depth>] [-s|--sha <40-char-sha>] [-t|--tag <tag>] [<remote>]"``
            Clone/update from git remote into local checkout
            ``aptest-git-<package-name>``, from which we build/install from source.
            
            * If the local checkout already exists, any local changes are deleted.
            * ``<remote>`` can also be a local checkout,
              from which Aptest will clone/fetch in the usual way.
            * A suffix can be appended to the local checkout name if `--git-local-detailed`_ is specified.
            
            Defaults:
            
            * ``<branch>``: hard-coded for each package (typically "master" or "main").
            * ``<remote>``: hard-coded for each package (typically a Github repository).
            * ``<depth>``: 1.
    
        ``pip:``
            Install from https://pypi.org using pip.
        
        ``pip:*.tar.gz``
            Install from local sdist using pip.
        
        ``pip:*.whl``
            Install from local wheel using pip.

        ``pip:<suffix>``
            Install ``<package-name><suffix>`` from https://pypi.org using pip.
            For example ``pip:==1.26.3`` will install version 1.26.3 of
            the package.

        ``<directory>``
            A local directory, typically a git checkout, from which we build/install from source.

    **Separate locations for building and testing**
    
    If a package is specified twice, the first location will be used
    for building, and the second location used for testing. This allows
    packages on https://pypi.org to be tested, for example:

        ``aptest.py -i pymupdf pip: -i pymupdf PyMuPDF build test``
            Test current pymupdf release with testsuite in ``PyMuPDF/tests``.

        ``aptest.py -i pymupdf pip: -i pymupdf git: build test``
            Test current pymupdf release with testsuite in current git.

.. _upper-case-package names:

    **Using upper-case package names**
    
    If a package is specified using an upper-case name, the package location
    is stored in a separate list that is only used if `--use-release-args`_
    is specified. This is typically used in `~/.aptest`_ to simplify making
    releases.
    
    **Aliases**
    
    Various convenience options and shortened aliases are provided:
    
    * `--langchain-pymupdf-layout`_ and alias `--langchain`_.
    * `--mupdf`_ and alias `-m`_.
    * `--pdf2docx`_.
    * `--pdf_feature_inspector`_ and alias `--pfi`_.
    * `--pymupdf4llm`_ and alias `--4llm`_.
    * `--pymupdf`_ and alias `-p`_ .
    * `--pymupdf_layout`_ and alias `--layout`_.
    * `--pymupdfpro`_ and alias `--pro`_.
    * `--smartoffice`_ and alias `--sot`_.
    * `--smartoffice-neo`_ and aliases `--sot-neo`_, `--neoso`_.
    
    Also see:
    
    * `--git-depth`_.
    * `--git-local-detailed`_.


.. _--log-prefix:

--log-prefix <log_prefix>
.........................
    Add prefix to all logging.


.. _-m:

-m <mupdf-location>
...................
    Specify location of package ``mupdf``.
    
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
    
    Also see:
    
    * `--remote-github-runners`_ - this will be more efficient when running
      on Github with `-r @github`_.


.. _-p:

-p <pymupdf-location>
.....................
    Specify location of package ``pymupdf``.
    
    Alias for ``-i pymupdf <location>``.
    
    Also see:
    
    * `-i`_.
    * `--pymupdf`_.


.. _-r:

.. _-r @github:

-r <remote>
...........
    Run ourselves on remote machine(s) and on success copy wheels
    back to local machine.

    If ``<remote>`` is ``@github``, we run on Github:

    * We push specified local checkouts directories (specified
      by ``-i``, ``-m``, ``-p`` etc) to branches called ``aptest-$USER`` in the
      hard-coded per-packagae central repositories, typically on https://github.com.

    * If there are uncommitted changes they are temporarily committed
      and we use the git stash to save/restore things.
      As of 2026-03-30 this fixes a problem where newly-added files were removed.

    * We re-run the ``aptest.py`` command on Github machines, changing
      ``-i``, ``-m`` etc args to use ``git:...`` to refer to the above
      repositories.

    * On success we copy Github logs and artifacts
      and extracted wheels etc to local directory:
      
          ``gh_workflow_YYYY-mm-dd-<workflowid>``
          
      Wheels are also copied in flat format into:
      
          ``gh_workflow_YYYY-mm-dd-<workflowid>-union/``.
    
    * ``-r@github`` is ignored if we are already running on Github
      (``GITHUB_ACTIONS=='true'``).
    
    * Also see:
    
      * `--remote-github-runners`_
      * `--remote-github-workflow-id`_
      * `--remote-github-yml`_
      * `--remote-github-yml-inputs`_
      * `--wheelhouse-release`_
    
    Otherwise ``<remote>`` should specify a remote machine on which to run
    Aptest:

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

      * `test-gnn`_ results directory ``test-gnn-results/`` is synced to local machine.
    
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

-u (bool)
.........
    [Obsolete]
    
    If true and `-r @github`_ is used, then on success we ask the user to
    confirm and then upload wheels to https://pypi.org.


.. _-v:

-v <venv>
.........
    
    **This option is unsupported at present due to switching to the external ``pipcl`` package.
    However the information below about the name of the venv and convenience link still applies.**
    
    Changes how we re-run ourselves in a venv when required.

    0 - Never re-run inside a venv.
    
        For example one could use this if already in a venv.

    1 - Use a venv but without recreating it if the directory already exists.
        We assume any existing directory was created
        by us earlier and is a valid venv containing all necessary packages;
        this saves a little time.

        Otherwise we create it with ``python -m venv ...``.

    2 - (This is the default) Use a venv.
        Always (re)create it with ``python -m venv ...``.

    3 - Use a clean venv.
        Delete it if it already exists, then run ``python -m venv ...``.

    The venv will be called ``venv-aptest-<pthonversion>-<wordsize>``, for
    example ``venv-aptest-3.13.5-64``.
    
    We also create a convenience link called ``venv-aptest``.
    
    Also see:
    
    * `--venv-name`_


.. _-VV:

-V <verbose>
............
    Set verbose level. Supported values are 0 and 1.


.. _--atexit:

--atexit <command>
..................
    Run ``<command>`` when Aptest terminates.
    
    For example:
    
    * ``--atexit 'printf "\\a"'``
    * ``--atexit beep``


.. _--build-pip-no-clean:

--build-pip-no-clean (bool)
...........................
    With command `build`_, run ``pip wheel`` with ``--no-clean``.
    
    According to ``man pip wheel``, this can also be done by setting environment variable ``PIP_NO_CLEAN``.


.. _--build-type:

--build-type debug | memento | release
......................................
    Set build type. Default is ``release``.


.. _--check-pushed:

--check-pushed (bool)
........................
    If true, fail if local checkout is not pushed to remote.


.. _--check-unchanged:

--check-unchanged (bool)
........................
    If true, fail if git diff is not empty in local checkout.


.. _--cibw-ignore-test-failures:

--cibw-ignore-test-failures (bool)
..................................
    If true, the `cibw`_ command ignores test failures. Default is false.


.. _--cibw-name:

--cibw-name <cibw_name>
.......................

    Name to use when installing ``cibuildwheel`` for the `cibw`_ command, e.g.::
    
        --cibw-name cibuildwheel==3.0.0b1
        --cibw-name git+https://github.com/pypa/cibuildwheel

    Default is ``cibuildwheel``, i.e. the current release.


.. _--cibw-pyodide:

--cibw-pyodide (bool)
.....................
     Make the `cibw`_ command build a pyodide wheel; runs
     ``cibuildwheel --platform pyodide ...`` etc.


.. _--cibw-pyodide-version:

--cibw-pyodide-version <cibw_pyodide_version>
.............................................
    Override default Pyodide version to use with `cibw`_ command
    by setting ``CIBW_PYODIDE_VERSION``.


.. _--cibw-skip-add-defaults:

--cibw-skip-add-defaults (bool)
...............................
    If true (the default) we add defaults to ``CIBW_SKIP`` such as ``pp*`` (to exclude
    pypy) and ``cp3??t-*`` (to exclude free-threading), which effects the `cibw`_
    command.
    
    Set to false with ``--cibw-skip-add-defaults=0`` or
    ``--cibw-skip-add-defaults=false`` or ``--cibw-skip-add-defaults=False``.


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
    
    * ``pymupdf``'s ``setup.py clean`` deletes files for pymupdf's extension and
      mupdf's C++/Python APIs.
      
    ``--clean-setup pymupdf`` can be useful if pymupdf fails to import mupdf;
    this can be caused by the build system not rebuilding correctly.


.. _--clean-setup-all:

--clean-setup-all <packages>
............................
    Add comma-separated packages/aliases to list of packages for which we run
    ``setup.py clean --all`` in the `build`_ and `populate`_ commands.
    
    * As of 2026-02-10, only pymupdf does anything in response to this.
    
    * ``pymupdf``'s ``setup.py clean --all`` deletes files for pymupdf's extension and
      mupdf's C++/Python APIs and the mupdf C API.


.. _--clean-wheelhouse:

--clean-wheelhouse (bool)
.........................
    If not specified (the default),
    then we first delete ``aptest-wheelhouse/`` if we are doing a build of all specified packages.
    
    I.e. we delete ``aptest-wheelhouse/`` if:
    
    * Commands `build`_ or `cibw`_ are specified.
    * And we are not skipping the build of one or more packages (with `-b`_).

    This is a useful default because it allows one to test while skipping slow
    rebuilds using `-b`_, but still start with a clean wheelhouse in the usual
    case where everything is being built.
    
    Otherwise:
    
    * If true, we delete ``aptest-wheelhouse/``.
    * If false, we do not delete ``aptest-wheelhouse/``.


.. _--devel:

--devel (bool)
..............
    If true, output extra information, including:
    
    * File/line information in log messages.
    * Backtraces in error messages.


.. _--draft-location:

--draft-location <remote>
.........................
    Location to which the `draft`_ command rsync's from the local wheelhouse.
    
    If ``<remote>`` can be accessed via https,
    it can be used as a pypi-style package repository with:
    
        ``pip install --extra-index-url <url>/simple ...``
    
    For example after:
    
        ``draft --draft-location julian@ghostscript.com:public_html/wheels-1.27.2``
    
    One can install packages with:
    
        ``pip install --extra-index-url https://ghostscript.com/~julian/wheels-1.27.2/simple pymupdf ...``
    
    [Note the trailing ``/simple``.]


.. _--git-depth:

--git-depth <depth>
...................
    Set git depth when cloning/updating package specified with ``git:...``.
    
    Also see:
    
    * `-i`_.


.. _--git-local-detailed:

--git-local-detailed (bool)
...........................
    Default is false.
    
    If true, we include any branch/tag/remote specification in local git clone
    path with ``git:...``.
    
    For example with ``--git-local-detailed -m=git:-b 1.27.x``,
    the local directory will be ``aptest-git-mupdf--b_1.27.x``.
    
    Also see:
    
    * `-i`_.
    

.. _--gnn-doit:

--gnn-doit (bool)
.................
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


.. _--gnn-show-text:

--gnn-show-text <path>
......................
    Override default filename of `gnn-show`_ text output.


.. _--graal:

--graal (bool)
..............
    If true we use Graal environment.

    As of 2025-08-04, if true:
    
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


--help
......
    Show this help.
    
    Also see:
    
    * `-h`_.

.. _--langchain:


.. _--key:

--key <prefix> <path>[,<env>]
.............................

    Specify a key file and/or environment variable,
    to be used for matching URLs or git remotes etc.

    * The longest matching prefix is used.
    * A match is only made if ``<prefix>`` or ``<env>`` exist.
    * ``<path>`` is the path of a file containing the key.
    * ``<env>`` is the name of an environment variable containing the key.

    For example:

    * Use file ``thirdparty-so-key`` for accessing git remotes starting with ``git@gitlab.artifex.com:``:

      ``--key git@gitlab.artifex.com: thirdparty-so-key``.

    * Also specify an environment variable for a Github repository secret,
      that allows access to gitlab when running in a Github action.

      ``--key git@gitlab.artifex.com: thirdparty-so-key,PYMUPDFPRO_SETUP_SOT_KEY``

    * Specify a file containing the pypi.org token to be used by the `upload`_ command:

      ``--key https://upload.pypi.org/ token-pypi.org``

    It can be convenient to put `--key`_ options in `~/.aptest`_, for example::

        # Key for pypi.org for use by `upload` command.
        --key https://upload.pypi.org/ token-pypi.org

        # Key for Github ReST operations used by `-r @github`.
        --key https://api.github.com/ token-github.com

        # Key for accessing repositories on Github.
        --key git@github.com: artifex-software-ssh-key,ARTIFEX_SOFTWARE_SSH_KEY

        # Key for accessing repositories on Artifex Gitlab.
        --key git@gitlab.artifex.com: thirdparty-so-key,PYMUPDFPRO_SETUP_SOT_KEY

    * When keys are used for ssh operations, Aptest runs ssh with
      ``StrictHostKeyChecking=no``,
      which may end up writing to ``~/.ssh/known_hosts``.

    Also see:

    * `Keys/tokens`_.


--langchain <langchain-pymupdf-layout-location>
...............................................
    Specify location of package ``langchain-pymupdf-layout``.
    
    Alias for ``-i langchain_pymupdf_layout <langchain-pymupdf-layout-location>``.
    
    Also see:

    * `-i`_.
    * `--langchain-pymupdf-layout`_.


.. _--langchain-pymupdf-layout:

--langchain-pymupdf-layout <langchain-pymupdf-layout-location>
..............................................................

    Specify location of package ``langchain-pymupdf-layout``.
    
    Alias for ``-i langchain_pymupdf_layout <langchain-pymupdf-layout-location>``.
    
    Also see:

    * `-i`_.
    * `--langchain`_.


.. _--layout:

--layout <pymupdf_layout-location>
..................................
    Specify location of package ``pymupdf_layout``.
    
    Alias for ``-i pymupdf_layout <pymupdf_layout-location>``.
    
    Also see:
    
    * `-i`_.
    * `--pymupdf_layout`_.


.. _--mupdf:

--mupdf <mupdf-location>
........................
    Specify location of package ``mupdf``.
    
    Alias for ``-i mupdf <mupdf-location>``.
    
    Also see:
    
    * `-i`_.
    * `-m`_.


.. _--marina:

--marina <smartoffice-marina-location>
......................................

    Specify location of package ``smartoffice-marina``.
    
    Alias for ``-i smartoffice-marina <smartoffice-marina-location>``.
    
    Also see:
    
    * `--smartoffice-marina`_.


.. _--neoso:

--neoso <smartoffice-neo-location>
....................................

    Specify location of package ``smartoffice-neo``.
    
    Alias for ``-i smartoffice-neo <smartoffice-neo-location>``.
    
    Also see:
    
    * `--smartoffice-neo`_.
    * `--sot-neo`_.


.. _--pdf2docx:

--pdf2docx <pdf2docx-location>
..............................
    Specify location of package ``pdf2docx``.
    
    Alias for ``-i pdf2docx <pdf2docx-location>``.
    
    Also see:
    
    * `-i`_.


.. _--pdf_feature_inspector:

--pdf_feature_inspector <pdf_feature_inspector-location>
........................................................
    Specify location of package ``pdf_feature_inspector``.
    
    Alias for ``-i pdf_feature_inspector <pdf_feature_inspector-location>``.
    
    Also see:
    
    * `-i`_.
    * `--pfi`_.


.. _--pfi:

--pfi <pdf_feature_inspector-location>
......................................
    Specify location of package ``pdf_feature_inspector``.
    
    Alias for ``-i pdf_feature_inspector <pdf_feature_inspector-location>``.
    
    Also see:
    
    * `-i`_.
    * `--pdf_feature_inspector`_.


.. _--pro:

--pro <pymupdfpro-location>
...........................
    Specify location of package ``pymupdfpro``.
    
    Alias for ``-i pymupdfpro <pymupdfpro-location>``.
    
    Also see:
    
    * `--pymupdfpro`_.


.. _--pymupdf:

--pymupdf <pymupdf-location>
............................
    Specify location of package ``pymupdf``.
    
    Alias for ``-i pymupdf <pymupdf-location>``.
    
    Also see:
    
    * `-i`_.
    * `-p`_.


.. _--pymupdfpro:

--pymupdfpro <pymupdfpro-location>
..................................
    Specify location of package ``pymupdfpro``.
    
    Alias for ``-i pymupdfpro <pymupdfpro-location>``.
    
    Also see:
    
    * `--pro`_.


.. _--pymupdf4llm:

--pymupdf4llm <pymupdf4llm-location>
....................................
    Specify location of package ``pymupdf4llm``.
    
    Alias for ``-i pymupdf4llm <pymupdf4llm-location>``.
    
    Also see:
    
    * `-i`_.
    * `--4llm`_.


.. _--pymupdf_layout:

--pymupdf_layout <pymupdf_layout-location>
..........................................
    Specify location of package ``pymupdf_layout``.
    
    Alias for ``-i pymupdf_layout <pymupdf_layout-location>``.
    
    Also see:
    
    * `-i`_.
    * `--layout`_.


.. _--pytest:

--pytest <pytest-flags>
.......................
    Specify extra `pytest <https://docs.pytest.org>`_ flags when Aptest runs ``pytest``.
    
    Used by the `test`_ and `cibw`_ commands.
    
    For example:
    
    * ``--pytest '-k test_123'``
    * ``--pytest '-v -k "test_123 or test_246"'``


.. _--pytest-junit-xml:

--pytest-junit-xml: (bool)
..........................
    Run ``pytest`` with ``--junit-xml`` and write info into ``aptest-wheelhouse``.


.. _--pytest-path:

--pytest-path <pytest_path>
...........................
    Specify a directory/file/test-function to be used by
    `pytest <https://docs.pytest.org>`_
    with the `test`_ and `cibw`_ commands,
    relative to each project root directory.
    
    Can be specified multiple times.
    Default is ``<package_root>/tests/``.


.. _--pytest-timeout:

--pytest-timeout <timeout-secs>
...............................
    Install `pytest-timeout <https://pypi.org/project/pytest-timeout/>`_ and run
    pytest with ``--timeout <timeout-secs>``.
    
    * Note that this does not interrupt extension code.


.. _--pytest-timeout-method:

--pytest-timeout-method <method>
................................
    Run pytest with ``--method <method>`` (requires `--pytest-timeout`_).


.. _--pytest-wrap:

--pytest-wrap gdb | valgrind | helgrind
.......................................
    Makes `test`_ command run `pytest <https://docs.pytest.org>`_ under specified tool.


.. _--python:

--python <python>
.................
    Set Python to use. If set we re-run ourselves using specified
    python command.


.. _--release-*:

--release-1
...........
    Build release wheels for ``pymupdf``, ``pymupdfpro``, ``pymupdf4llm`` and
    ``pymupdf_layout``, for core platforms ``linux-x64``, ``windows-x64`` and ``macos-arm64``.
        
    Also builds sdists.
    
    Also see `Release procedure`_.


--release-2
...........
    Build release wheels for ``pymupdf``, ``pymupdfpro``, ``pymupdf4llm`` and ``pymupdf_layout``, for
    platforms ``linux-aarch64`` and ``macos-x64``.
    
    Also see `Release procedure`_.


--release-3
...........
    Build release ``pymupdf`` wheel for platform ``windows-x32``.
    
    Also see `Release procedure`_.


--release-4
...........
    Build release ``pymupdf`` wheel for platform ``linux-x64-musl``.
    
    Also see `Release procedure`_.


--release-5
...........
    Build release ``pymupdf`` wheel for platform ``pyodide``.
    
    Also see `Release procedure`_.


--release-6
...........
    Build release ``pymupdf`` wheel for platform ``linux-x64`` and free threading python-3.14.
    
    Also see `Release procedure`_.


.. _--remote-do:

--remote-do (bool)
..................
    [For debugging.]

    Default is true.
    
    If false (``--remote-do=0``) we don't sync to remote and we don't run any
    commands on remote. But we do sync remote wheels to local.


.. _--remote-github-runners:

--remote-github-runners <github-runners-modify>
...............................................
    Comma-separated ordered list of modifications to the list of
    Github runners on which `-r @github`_ runs.

    This list defaults to runners for Linux-x64, Windows-x64
    and MacOS-arm64. Then for each comma-separated item in
    ``<github-runners-modify>``:

    * ``-<name>``: removes runner ``<name>`` from the list.
    * ``+<name>`` and ``<name>``: adds runner ``<name>`` to the list.
    * ``-`` removes all runners from the list.

    In addition if the first item does not start with ``+`` or ``-`` we
    first remove all runners from the list.

    We allow aliases for Github runners names:
    
    * ``linux``, ``linux-intel``.
    * ``macos-intel``.
    * ``macos``, ``macos-arm``.
    * ``windows-arm``.
    * ``windows``, ``windows-intel``.

    For example:

    * Run only on windows-arm::
      
        --remote-github-os windows-arm
        --remote-github-os -,+windows-arm


.. _--remote-github-workflow-id:

--remote-github-workflow-id <workflow_id>
.........................................
    Changes the behaviour of `-r @github`_. Don't start a new run on Github,
    instead continue from a previous `-r @github`_ invocation by waiting for
    ``<workflow_id>`` to finish and downloading logs and wheels etc to the
    local machine.
    
    * One still needs to specify `-r @github`_.
    
    Previous downloads are not repeated unnecessarily:
    
    * Downloads are made to a temporary file that is then atomically renamed.
    * Files that already exist locally are not downloaded again.


.. _--remote-github-yml:

--remote-github-yml <yml>
.........................
    With `-r @github`_, run the specified ``.yml`` file (leafname only) instead
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
    Run remote using specified (Python) command. Ignored by `-r @github`_.


.. _--remote-prefix-default:

--remote-prefix-default <remote> <prefix>
.........................................
    Sets default remote prefix for a specific remote when specified with
    ``-r <remote>``. For example to always use python-3.12 on remote machine
    ``jules-asus``, use::

        --remote-prefix-default jules-asus python312
    
    Also see `~/.aptest`_.


.. _--remote-rsync-path:

--remote-rsync-path <remote_rsync_path>
.......................................
    Specify ``--rsync-path`` when running rsync, to identify location of
    rsync on remote. E.g. ``--remote-rsync-path 'wsl rsync'`` if remote is
    a Windows machine with rsync installed in the default WSL system.


.. _--remote-rsync-wsl:

--remote-rsync-wsl (bool)
.........................
    [Experimental.]

    If true we tweak various things to cope with remote using wsl rsync.


.. _--run:

--run <package> <command>
.........................
    Make `run`_ command run the specified command within checkout of
    ``<package>``.


.. _--sdists:

--sdists (bool)
...............
    If true, the `build`_ and `cibw`_ commands will also build sdists.
    
    We only build sdists for these packages:
    
    * ``pymupdf``
    * ``pymupdf4llm``
    * ``pdf2docx``
    
    With `cibw`_, we only build sdists if on Linux.


.. _--set-swig:

--set-swig <swig>
.................
    Specify what swig to use.
    
    * If ``pip:...`` we install using pip.

    * (Unix only) If ``git:...`` we clone/update/build swig from a git repository.

      We default to https://github.com/swig/swig.git branch master, so these
      are all equivalent::

          --set-swig 'git:--branch master https://github.com/swig/swig.git'
          --set-swig 'git:--branch master'
          --set-swig git:
    
    * Otherwise should be the swig binary to use.


.. _--set-swig-quick:

--set-swig-quick (bool)
.......................
    If true and `--set-swig`_'s ``<swig>`` value starts with ``git:``, we do not
    update/build swig if it is already present.


.. _--smartoffice:

--smartoffice <smartoffice-location>
....................................
    Specify location of package ``smartoffice``.
    
    Alias for ``-i smartoffice <smartoffice-location>``.
    
    Also see:
    
    * `-i`_.
    * `--sot`_.


.. _--smartoffice-marina:

--smartoffice-marina <smartoffice-marina-location>
..................................................
    Specify location of package ``smartoffice-marina``, an alternative to ``--smartoffice``.
    
    Alias for ``-i smartoffice-marina <smartoffice-marina-location>``.
    
    Also see:
    
    * `-i`_.
    * `--marina`_.


.. _--smartoffice-neo:

--smartoffice-neo <smartoffice-neo-location>
............................................
    Specify location of package ``smartoffice-neo``, an alternative to ``--smartoffice``.
    
    Alias for ``-i smartoffice-neo <smartoffice-neo-location>``.
    
    Also see:
    
    * `-i`_.
    * `--neoso`_.
    * `--sot-neo`_.


.. _--sot:

--sot <smartoffice-location>
............................

    Specify location of package ``smartoffice``.
    
    Alias for ``-i smartoffice <smartoffice-location>``.
    
    Also see:
    
    * `--smartoffice`_.


.. _--sot-neo:

--sot-neo <smartoffice-neo-location>
....................................

    Specify location of package ``smartoffice-neo``.
    
    Alias for ``-i smartoffice-neo <smartoffice-neo-location>``.
    
    Also see:
    
    * `--smartoffice-neo`_.
    * `--neoso`_.


.. _--system-packages:

--system-packages (bool)
........................
    If true, automatically install required system packages such as
    Valgrind, using ``apt`` on Linux and ``brew`` on MacOS. Default is true if
    running as Github action, otherwise false.


.. _--system-site-packages:

--system-site-packages (bool)
.............................
    If true, use ``--system-site-packages`` when creating venv. Defaults is false.


.. _--tee-auto:

--tee-auto (bool)
.................
    If true, we copy log output to file ``aptest-out-YYYY-mm-dd-HH-MM-SS``, and on
    exit create convenience softlink ``aptest-out``.
    
    Otherwise we cancel any existing tee.
    
    If `-r`_ is used to run on a remote machine (not ``@github`),
    we create a second convenience softlink called ``aptest-out-<remote>``.
    
    Default is false.
    
    Can be useful to put this in `~/.aptest`_.


.. _--tee-path:

--tee-path <path>
.................
    Copy log output to file ``<path>``.
    
    Can be useful to put this in `~/.aptest`_.


.. _--test-extra-packages:

--test-extra-packages <names>
.............................
    Installs specified comma-separated packages from https://pypi.org before
    running tests in `test`_ command.


.. _--test-gnn-cache:

--test-gnn-cache (bool)
.......................
    If true, ``test-gnn*`` commands look for a matching ``test-gnn-*.json``
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
    * How Artifex packages were specified, e.g. ``-p git:`` or ``-p pip:``.
    * git sha's and diffs for Artifex packages specified with ``git:`` or local checkout.
    * https://pypi.org version numbers for Artifex packages specified with ``pip:...``.
    * Any `--test-gnn-limit`_ value.


.. _--test-gnn-det:

--test-gnn-det <gnn_det>
........................
    This is required by `test-gnn`_.
    
    Sets the Python script to be run,
    relative to the root of the ``pymupdf_layout`` checkout.
    
    Valid values for ``<gnn_det>`` are:
    
    * ``eval/eval_docling.py``
    * ``eval/eval_gnn.py``
    * ``eval/eval_oracle_gnn.py``
    * ``eval/eval_pymupdf4llm.py``
    * ``eval/eval_pymupdf_layout.py``


.. _--test-gnn-extra:

--test-gnn-extra <key>=<value>
..............................
    Adds specified ``key=value`` pair to the root of the results dict
    created by `test-gnn`_.


.. _--test-gnn-limit:

--test-gnn-limit <limit>
........................
    Set number of gnn files to tested by `test-gnn`_. Default is all.


.. _--test-gnn-out:

--test-gnn-out <path>
.....................
    Where to write json data containing test details from `test-gnn`_. Default
    is a filename containing the current date and time.


.. _--test-gnn-push:

--test-gnn-push (bool)
......................
    If true, we push gnn results from `test-gnn`_ to
    https://github.com/ArtifexSoftware/PyMuPDF-pymupdf-results. Default is false.


.. _--ticker:

--ticker <delay>
................
    Use ticker with specified delay. Disabled if ``delay==0``. Default is
    0.5.


.. _--use-release-args:

--use-release-args (bool)
.........................
    * Use upper-case package locations
      (see `-i`_'s `upper-case-package names`_ section),
      typically specified in `~/.aptest`_.

    * Require that `--wheelhouse-release`_ has been specified,
      and use its value for the wheelhouse.
      
      * The new value must be different from the default wheelhouse,
        so that we can protect against non-release builds deleting a partially complete
        release procedure.
      * We never remove the contents of this wheelhouse,
        because multiple invocations of Aptest are required to build the release wheels. So
        `--clean-wheelhouse`_ is ignored.
    
    Also see:
    
    * `-i`_.
    * `--wheelhouse`_.
    * `--wheelhouse-release`_.

.. _--venv-name:

--venv-name <venv_name>
.......................
    Sets the venv name used by `-v`_.
    
    Default is ``venv-aptest-<python-version>-<word-size>``,
    for example ``venv-aptest-3.14.2-64``.


.. _--wheelhouse:

--wheelhouse <wheelhouse_dir>
.............................
    Directory in which to place wheels, instead of
    default ``aptest-wheelhouse``.
    
    Also see:
    
    * `--clean-wheelhouse`_.
    * `--wheelhouse-release`_.


.. _--wheelhouse-release:

--wheelhouse-release <wheelhouse_release>
.........................................
    Directory in which to place wheels when building releases.
    
    Also see:
    
    * `--wheelhouse`_.
    * `--release-*`_.


.. _--4llm:

--4llm <location>
.................
    Specify location of package ``pymupdf4llm``.
    
    Alias for ``-i pymupdf4llm <location>``.
    
    Also see:
    
    * `-i`_.
    * `--pymupdf4llm`_.


Special arguments
^^^^^^^^^^^^^^^^^

completion
..........
    Must be the only arg. Writes an Aptest bash completion script to stdout.

    The completion script works by internally running ``aptest.py`` in
    completion mode (where ``COMP_LINE`` is defined), where it writes valid
    completions to stdout.

    When in completion mode, Aptest will append diagnostics to file
    ``APTEST_COMPLETION_DEBUG`` if defined.
    
    Also see `Argument completion with Bash`_.


Changelog
---------

**2026-06-22**

* Fixed ``.github/workflows/test_release.yml``.


**2026-06-19**

* Added AGPL-3.0-only license - see `License`_.
* Updated Github workflow to test mupdf-1.28.x branch.


**2026-06-18**

* Added section on creating/using development wheels, `Making internal development releases`_.
* Don't delete wheelhouse if it contains a file called ``_aptest_wheelhouse_preserve``.
* Improved use of ``piprepo`` to create pypi-style database in wheelhouse:

  * Remove all wheels that are unknown to Aptest.
  * Recreate pypi-style database before uploading with `draft`_.
  * Recreate pypi-style database before exiting.
* Minor improvements to output from autoenv on startup.
* Modify .github/workflows/test_multiple.yml to match pymupdfpro now defaulting to marina.
* Show current directory on startup.
* With `upload`_, also upload pyodide wheels to pypi, which now accepts them.


**2026-06-15**

* Simplified where we put wheels:

  * Removed ``--wheelhouse-union``.
  * Removed ``--wheelhouse-union-release``.
  * Added `--wheelhouse-release`_.
  * When building on Github, download wheels into our wheelhouse.

* Various fixes to `--release-*`_.
* Improved display of args - show ``~.aptest``, ``APTEST_options`` and command line separately.


**2026-06-14**

* Further fix of ``.github/workflows/test_multiple.yml`` artifact names.


**2026-06-12**

* Write command line to log output on startup.
* In ``.github/workflows/test_multiple.yml``, fix creation of artifacts containing wheels.


**2026-06-10**

* Fix Windows builds with `cibw`_ by disabling wheel repair with
  ``CIBW_REPAIR_WHEEL_COMMAND_WINDOWS=''``.
  
  (This is because ``cibuildwheel`` has started to use ``delvewheel``,
  which apparently cannot find our ``mupdfcpp64.dll``.)


**2026-06-01**

* Added `--build-pip-no-clean`_, to preserve ``pip wheel`` build directory.
* Fixed detection of free-thread python.
* Show Aptest git info on startup.
* Change whether we clean wheelhouse; see `--clean-wheelhouse`_.
* Don't run pytest with ``--junit-xml`` by default; see `--pytest-junit-xml`_.
* Added `--git-local-detailed`_.


**2026-05-14**

* Improved handling of EOF on command line.


**2026-05-10**

* Updated test_multiple, we currently need to patch marina.


**2026-05-07**

* Fix `--pytest-wrap`_.


**2026-05-03**

* More concise command-line diagnostics if `~/.aptest`_ or `$APTEST_options`_
  are used.
* If we fail to create softlink to venv, output warning instead of failing.


**2026-04-31**

* Fix bug if python executable path has spaces, e.g. on Windows.
* Fix incorrect warnings about directories not being a git checkout, e.g. with case changes on Windows or trailing slash.


**2026-04-30**

* Improved `How to run Aptest`_, and added pipx examples.
* Improved pro/marina builds with `cibw`_.


**2026-04-27**

* Improved `Release procedure`_.
* Improved description of how to install aptest with pip; see `How to run Aptest`_.
* Avoid unnecessary backtraces after some command line errors.


**2026-04-23**

* Improved diagnostics/backtraces on errors.
* Added `--pytest-timeout`_ and `--pytest-timeout-method`_.
* Fix git errors in manylinux docker with `cibw`_ by setting ``safe.directory``.
* Set correct ssh/git key if building ``pymupdfpro`` with ``smartoffice-marina``.
* Special-case ``CIBW_BUILD=all``; see `cibw`_.
* Default to deleting wheelhouse if `build`_ or `cibw`_ commands are specified;
  see `--clean-wheelhouse`_.
* Control of venv with `-v`_ is currently unsupported.


**2026-04-18**

* Fixed building of pipcl.
* Fixed handling of PIP_EXTRA_INDEX_URL on manylinux.
* Avoid spurious differences between line endings in wheels when building on Windows.


**2026-04-16**

* Added `--git-remote-modify`_.
* Added `--wheelhouse`_.
* Fix `--cibw-pyodide-version`_.
* Add support on Unix for building/installing as a Python package, providing console command ``aptest``.
  
  * Can still be used directly from a checkout.
* Uses `pipcl package from pypi.org <https://pypi.org/project/pipcl/>`_
  (have removed local pipcl.py and wdev.py).


**2026-04-09**

* When a package location is specified with ``git:...``,
  allow ``<remote>`` to be a local checkout. See `-i`_.


**2026-04-02**

* Fixed bug in release builds.
* Document that the `cibw`_ command requires that package versions are compatible.
* Added `--clean-wheelhouse`_.


**2026-04-02**

* Fix build of ``pymupdfpro`` on Github.


**2026-04-01**

* Fixed scheduled Github tests - use Aptest repository secrets for Github/Gitlab keys.
  See `Default keys when running on Github`_.


**2026-03-31**

* Added control of git depth; see `--git-depth`_.
* Improve internal specification of packages - use explicit git remote.
* With `cibw`_, improve handling of old versions of pymupdf.
* Improved key handling, removing hard-coded key file paths in favour of new option `--key`_.
* Added support for (pseudo) package ``smartoffice-marina`` with pymupdfpro.
* Added pymupdf4llm to scheduled Github tests in ``.github/workflows/test_multiple.yml``.
* Ignore `-r @github`_ if already running on Github.
* Fixed `-r @github`_ forgetting about newly added files.
* Removed ``--4llm-unified`` as we decided not to unify ``pymupdf4llm`` and ``pymupdf_layout``.
* Make ``--tee-auto=0`` cancel an existing tee.

**2026-03-20**

* Fix use of `--smartoffice`_ with `cibw`_.


**2026-03-19**

* Fix handling of ``pdf4llm`` wheels when making releases.

  (Like ``pymupdf4llm`` wheels, these are pure python but differ if created on
  Windows due to carriage return characters.)

* Minor improvements to diagnostics.


**2026-03-18**

* Added ``pymupdf4llm`` and ``pdf4llm`` to `Release procedure`_.
* With `cibw`_, don't build/test ``pymupdf4llm`` and ``pdf4llm`` on macos/intel/python-3.14,
  because ``onnxruntime`` not available.
* Added `--check-pushed`_.


**2026-03-17**

* Added ``pymupdf4llm`` and ``pdf4llm`` to ``.github/workflows/test_release.yml``.
* Add handling of `--check-unchanged`_ when running on Github.
* Don't install extra packages when testing ``pymupdf4llm`` - is now unnecessary.


**2026-03-16**

* Added support for pdf4llm.
* Add pdf4llm to release.


**2026-03-12**

* Use Github's native linux-arm runner instead of CIBW_ARCHS_LINUX=aarch64 and emulation.
* Run pytest in 4llm's top-level tests/ directory, not test/pymupdf4llm/llama_index/.
* Create pretty-printed version of pytest's pytest-junit.xml.


**2026-03-10**

* Don't overwrite ``--tee`` output when doing bash command completion.
* Cope with windows pure python ``pymupdf4llm`` wheels differing because of DOS line endings.
* Improved release procedure.
  
  * Build all wheels/sdists in local directory using multiple invocations of Aptest.
  * Upload everything to https://pypi.org in one operation.
  
* New option `--check-unchanged`_.
* New option `--draft-location`_.
* New option `--log-prefix`_.
* New option ``--wheelhouse-union``.
* New option ``--wheelhouse-union-release``.
* New command `draft`_.
* New command `upload`_.


**2026-03-05**

* Disabled backtraces in args diagnostics, unless `--devel`_ is specified.
* Fixed build ordering of ``pymupdf_4llm`` because it now requires ``pymupdf_layout``.


**2026-03-04**

* Avoid problems on Github caused by pytest searching for a pytest.ini file.
* With `cibw`_, avoid extra prerequisite wheels for pure-python packages in aptest-wheelhouse.

**2026-03-04**

* Removed aliases ``-l``, ``-s``, ``-P``.
* Internal fix to not use ``|head -n 1`` with ``git log -1``.
* Added `--neoso`_ alias for `--smartoffice-neo`_.

**2026-03-04**

* Avoid git delays on Windows - use ``git log -1`` instead of ``git show``.
* Added ``smartoffice-neo`` package, an alternative to ``smartoffice``.
  See `--smartoffice-neo`_.

**2026-03-04**

* Renamed ``--swig`` and ``--swig-quick`` to `--set-swig`_ and `--set-swig-quick`_.
* Added support for package ``swig``.
* Changes to `test-gnn`_.
* ``--4llm-unified`` now expects layout to be in 4llm
  (previously 4llm was moved into layout).
* Fixed handling of ``pymupdf4llm``.
* Also build sdists for ``pymupdf4llm`` and ``pdf2docx`` (as well as ``pymupdf``).
* Added pymupdf4llm to `--release-1`_.
* Allow trailing `/` in local package checkout paths.
* Run ``git`` with ``-no-pager`` to attempt to avoid long delays on Windows.


**2026-02-26**

* Fixed build of ``pymupdf-cp314t`` wheel in  `--release-6`_ command.
* Use stylesheet in `docs`_ command when producing `<README.rst.html>`__.


**2026-02-25**

* With `cibw`_ command, support `--pytest-path`_ (was previously ignored).
* Fix `--python`_.
* Generate junit .xml file when running pytest.
* Fix `--clean-setup`_ with pymupdf's mupdf.
* Avoid duplicate ``aptest-out-*`` files when re-running ourselves in venv or on remote machine.
* Add support for ``pip:...`` to ``--swig``.
* Added `--release-6`_ for python-3.14t (free threading) wheel.
* Added `docs`_ command.


**2026-02-18**

* New command line parser.

  * Accepts ``--foo=bar`` as well as ``--foo bar``.
  * Special case for Bool args:
  
    * Bools are now specified as ``--foo`` or  ``--foo=<value>``.
    * Previous ``--foo <value>`` must be changed to ``--foo`` or ``--foo=<value>``,
      for example in `~/.aptest`_ and `$APTEST_options`_.
  * See `Option values`_.
* Ignore `~/.aptest`_ if ``APTEST_DOT_APTEST=0``.
* Added new command `windows-show-vs-instances`_.
* Allow control over what Github runners are used with ``-r @github`` - see new option `--remote-github-runners`_.

**2026-02-12**

* Added ``--token-github-path``.
* Added ``--token-pypi-path``.
* Fixed ``-r @github`` on Windows.

**2026-02-11**

* Fixed `-u`_ upload.
* Fixed checking of `--release-*`_ options.
* Fixed bug in `run`_ command.

**2026-02-10**

* Improved output after downloading from Github.
* Added `--cibw-ignore-test-failures`_.
* Renamed ``--log-tee`` to `--tee-auto`_.
* Added `--tee-path`_.
* Added `--atexit`_.
* Added support for ``pdf2docx`` - see `--pdf2docx`_.


**2026-02-09**

* Changed `-V <-VV_>`__ to take the verbose level (0 or 1) instead of incrementing it.
* Changed default verbose level to 1.
* Show git sha and diff of Aptest itself on startup if verbose.
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
* Added experimental support for unified 4llm+layout package; see ``--4llm-unified``.


**2026-01-30**

* Allow testing of Aptest itself.
* Added `--release-5`_ for building pyodide pymupdf wheel.
* Avoid remaining potential for ``build`` command to end up installing incorrect package versions.


**2026-01-15**

* Fix potentially incorrect package versions if ``pip:`` is used.
* Fix flake8 errors.
* Fix codespell errors.
* All docs are now in `<README.rst>`__.
