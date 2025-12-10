## Artifex Packages build/test.

The `aptest.py` scripts can build, test and release (to pypi.org) multiple
Python packages together.


### Supported packages/projects:

* mupdf
* pymupdf
* pymupdfpro
* pymupdf-layout


### Package locations

* Build from local checkout.
* Build from specific branch, tag or sha on remote git repository.
* Install directly from pypi.org.

See `-i` option, or aliases `-m`, `-p`, `-P` and `-l`.


### Run in different places

* Local machine.
* Remote machine (with ssh/rsync).
* Github runner (push to unique(ish) branches and run a workflow).

See the `-r` option.


### Build/install

For each package:
* The package is built as a wheel using `pip wheel`. This will typically
  take place in an internal pip venv.
* The wheel is installed into the current venv.
* The wheel is added to a local pypi-style PEP-503 package repository.
* We use pip's `--extra-index-url` option to refer to our internal package
  repository.
* Thus pip will use previously built wheels as prerequisites, as required.


### Test

* We run tests in the current venv for each package, using pytest.
* Packages on pypi.org do not contain test suites, but one can specify a second
  package location to be used for testing, for example a local checkout or
  remote git repository.


### Build/test with cibuildwheel

* The `cibw` command runs `cibuildwheel` on each package.
* This builds a wheel, and runs tests using pytest.
* We add each wheel to our internal package repository.
* We set PIP_EXTRA_INDEX_URL to point to our internal package repository.
* cibuildwheel uses pip internally so this ensures that previously-built
  prerequisite wheels will be installed as required.


### Running on Github with `-r @github`.

* If a package is specified as a local checkout:
  * We push the local checkout to a branch in the equivalent Github repository.
  * We change the aptest.py command line to specify a `git:...` location.
  * For example we would change `-p PyMuPDF` to
    `-p 'git:-b <branch> git@github.com:pymupdf/PyMuPDF.git`.
* We use branch name `aptest-$USER`.
  * This allows multiple developers to run on Github simultaneously, without
    creating an unbounded number of temporary branches.


### Keys/tokens

#### Github/ArtifexSoftware ssh key

We allow specification of a custom ssh private key to push to and/or access
git@github.com:PyMuPDF/PyMuPDF and repositories within git@github.com:Artifex/.

* If required, this key should be provided in file `artifex-software-ssh-key`
  in the current directory.

* We run ssh with `StrictHostKeyChecking=no`, which may end up writing to
  .ssh/known_hosts.

#### Smartoffice ssh key

We allow specification of a custom ssh private key that allows access to the
SmartOffice repository; this is required when PyMuPDFPro builds SmartOffice
because of how the SmartOffice build system works.
  
* If required, this key should be provided in file `thirdparty-so-key` in the
  current directory.

#### Huggingface token

If required, this token should be provided in file `huggingface-key` in the
current directory.

#### Use of keys with remote runs

* If the `-r` option is used to defer to a remote machine, the key files are
  copied to the remote machine. This obviously has security implications.

* If the `-r` option is used to defer to a Github runner, we rely on the
  ArtifexSoftware/aptest repository having secrets that allow the required
  access.


### Argument completion with Bash

`aptest/aptest.py completion` writes a bash completion script for aptest to
stdout.

* Add argument completion for aptest.py to the current Bash session with:

  `source <(aptest/aptest.py completion)`
            
  Subsequently when entering an aptest.py command, bash will respond to <tab>
  by completing and/or showing valid args.

* Or write into relevant files with:

  * `./aptest/aptest.py completion > /etc/bash_completion.d/aptest.py.bash_completion`
  * `./aptest/aptest.py completion >> ~/.bash_completion`.
  
  See Bash's `help complete` for more information.


### More information

Please run `aptest.py -h` or read the same text in the doc-comment at the start
of aptest.py.
