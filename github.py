#! /usr/bin/env python3

'''
Abstractions for Github ReST API.
'''

import pipcl

import fnmatch
import getpass
import glob
import hashlib
import io
import json
import os
import platform
#import requests    # Import lazily because often not present.
import shutil
import sys
import tarfile
import time
import traceback
import zipfile


def _gh_headers(token):
    '''
    Returns dict containing basic headers for gihub rest calls.
    
    Token must be string containing value Github token, typically starting with
    'ghp_'.
    '''
    headers = dict()
    headers['Accept'] = 'application/vnd.github.v3+json'
    if token:
        headers['Authorization'] = f'token {token}'
    return headers


def _gh_download(token, url, path, *, gh=True):
    '''
    Downloads from github URL to local file.
    
    Args:
        token:
            Github token.
        url:
            URL from which to download.
        path:
            Local path for downloaded data.
        gh:
            If false we do not assume github, instead using requests.get()
            directly with no special headers.
    
    * We ask user for username/token and retry if we get an error.
    * We do not leave partial downloads in place - we write to `path+'_'` then
      rename to `path`.
    * Does nothing if `path` already exists.
    '''
    if os.path.exists(path):
        pipcl.log(f'Not downloading because local path already exists: {os.path.relpath(path)}')
        return
    path_ = f'{path}_'
    pipcl.fs_remove(path_)
    pipcl.fs_ensure_parent_dir(path)
    pipcl.log('Downloading:')
    pipcl.log(f'    from: {url=}')
    pipcl.log(f'    to: {path}')
    if gh:
        r = _gh_get(token, url, stream=True, raise_for_status=False)
        if r.status_code == 403:
            username = input('username ? ')
            password = getpass.getpass('password ? ')
            _gh_get(token=None, url=url, stream=True, raise_for_status=False, auth=(username, password))
        try:
            r.raise_for_status()
        except Exception as e:
            # r.json() can have useful info about the error.
            raise Exception(str(r.json())) from e
    else:
        import requests # pylint: disable=import-outside-toplevel,import-error
        r = requests.get(url, stream=True)  # pylint: disable=missing-timeout
    t0 = t1 = time.time()
    bytes_ = 0
    with open(path_, 'wb') as f:
        # 2025-11-05: Using chunk_size=None seems to sometimes hang?
        for chunk in r.iter_content(chunk_size=2**20):
            bytes_ += len(chunk)
            f.write(chunk)
            t2 = time.time()
            if t2 - t1 >= 5:
                t1 = t2
                bytes_per_sec = int(bytes_/(t2-t0))
                pipcl.log(f'{bytes_:>12,}B {bytes_per_sec:,}B/s')
    os.rename(path_, path)


def _unzip(path_zip, path_out_directory):
    '''
    Extracts zip file into a directory.
    
    Args:
        path_zip:
            The zip file.
        path_out_directory:
            Directory into which we extract.
    
    * We do not leave partial extract in place - we write to
    `path_out_directory+'_'` then rename to `path_out_directory`.
    * We do nothing if `path_out_directory` already exists.
    '''
    if os.path.exists(path_out_directory):
        pipcl.log(f'Not extracting from {os.path.relpath(path_zip)} because already exists: {os.path.relpath(path_out_directory)}')
        return
    pipcl.log('Extracting:')
    pipcl.log(f'    from: {path_zip}')
    pipcl.log(f'    to: {path_out_directory}')
    path_out_directory_ = f'{path_out_directory}_'
    pipcl.fs_ensure_empty_dir(path_out_directory_)
    with zipfile.ZipFile(path_zip) as z:
        z.extractall(path_out_directory_)
    os.rename(path_out_directory_, path_out_directory)


def ghlogs_links(root, logs):
    '''
    Look for log files within <logs> and make softlinks in <root>/. Writes
    log lines highlighting these links.
    '''
    pipcl.log(f'### Logfile links in {logs}:')
    pipcl.log(f'{root=} {logs=}')
    assert root, f'{root=}'
    for p in glob.glob(f'{logs}/*.txt'):
        st = os.stat(p)
        dst = f'{root}/{os.path.basename(p)}'
        src = p
        pipcl.fs_remove(dst)
        sr2 = os.path.relpath(src, os.path.dirname(dst))
        try:
            os.symlink(sr2, dst)
        except Exception as e:
            pipcl.log(f'Warning: failed to create symlink: {e}')
            pipcl.log(f'    {src=}')
            pipcl.log(f'    {sr2=}')
            pipcl.log(f'    {dst=}')
        pipcl.log(f'### {st.st_size: 12,} {dst}')


def _url_expand(url):
    '''
    Returns <url> prefixed with 'https://api.github.com/repos/' if it doesn't
    alreadu start with 'https://'.
    '''
    if url.startswith(f'https://'):
        return url
    else:
        ret = f'https://api.github.com/repos/{url}'
        pipcl.log(f'Expanded {url=} to: {ret!r}.')
        return ret

def _raise(r):
    '''
    Verbose wrapper for `r.raise_for_status()`.
    '''
    try:
        r.raise_for_status()
    except Exception as e:
        pipcl.log(f'{e=}')
        pipcl.log(f'str(e)={str(e)}')
        pipcl.log(f'{r.text=}')
        pipcl.log(f'{r.json()=}')
        pipcl.log(f'r.json:\n{json.dumps(r.json(), indent="    ")}')
        #pipcl.log(f'r:\n{json.dumps(r, indent="    ")}')
        raise Exception(str(r.json())) from e


def _gh_get(
        token,
        url,
        *,
        raise_for_status=True,
        stream=False,
        params=None,
        auth=None,
        ):
    '''
    Calls requests.get() for github URL `url`.
    
    Args:
        token:
            Github token for _gh_headers().
        url:
            If starts with `https://` is a Rest URL. Otherwise should
            starts with <organisation>/<repository> and we prefix with
            `https://api.github.com/repos/`.
        raise_for_status:
            If true we call .raise_for_status() on requests result.
        stream:
            Passed as <stream> argument to to requests.get().
        params:
            Passed as <params> argument to to requests.get().
        auth:
            None or (username, password).
    '''
    import requests # pylint: disable=import-outside-toplevel,import-error
    url = _url_expand(url)
    assert url.startswith(f'https://')
    r = requests.get(   # pylint: disable=missing-timeout
            url,
            headers=_gh_headers(token),
            params=params,
            stream=stream,
            auth=auth,
            )
    if raise_for_status:
        _raise(r)
    return r


def _gh_post(token, url, json, raise_for_status=True): # pylint: disable=redefined-outer-name
    '''
    Calls requests.post() for github URL `url`.
    Args:
        url:
            If starts with https:// is a Rest URL. Otherwise should
            be <organisation>/<repository> and we prefix with
            `https://api.github.com/repos/`.
        token:
            Github token.
        json:
            Dict to pass as requests.post()'s `json` arg.
    '''
    import requests # pylint: disable=import-outside-toplevel,import-error
    pipcl.log(f'{url=}')
    url = _url_expand(url)
    pipcl.log(f'{url=}')
    headers = _gh_headers(token)
    pipcl.log(f'{headers=}')
    r = requests.post(url, headers=headers, json=json)    # pylint: disable=missing-timeout
    if raise_for_status:
        _raise(r)
    return r


def _gh_workflow(token, url_base, id_):
    '''
    Returns dict for specified workflow run.
    '''
    url = f'{url_base}/actions/runs/{id_}'
    r = _gh_get(token, url)
    return r.json()


def _timestring_to_time(time_string):
    return time.strptime(time_string, '%Y-%m-%dT%H:%M:%SZ')


def _gh_runs_newest(token, url_base, verbose=0):
    '''
    Returns id of newest workflow run.
    '''
    url = f'{url_base}/actions/runs'
    r = _gh_get(token, url)
    response = r.json()
    workflows = response[ 'workflow_runs']
    workflows.sort(key=lambda workflow: _timestring_to_time(workflow["created_at"]))
    if verbose >= 2:
        pipcl.log(json.dumps(workflows[-1], indent=4, sort_keys=True))
    if verbose >= 1:
        pipcl.log('Workflows are (oldest first):')
        for i, workflow in enumerate(workflows):
            pipcl.log(f'{i}:')
            pipcl.log(f'    head_branch={workflow["head_branch"]}')
            pipcl.log(f'    id={workflow["id"]}')
            pipcl.log(f'    date={workflow["created_at"]}')
            pipcl.log(f'    name={workflow["name"]}')
            pipcl.log(f'    artifacts_url={workflow["artifacts_url"]}')
            pipcl.log(f'    logs_url={workflow["logs_url"]}')
    if verbose:
        pipcl.log('Selecting newest workflow')
    if workflows:
        workflow = workflows[-1]
        id_ = workflow[ 'id']
        id_ = str(id_)
        #pipcl.log(f'Returning {id_=}')
        return id_
    else:
        # No workflows have ever run.
        return None


def gh_run_workflow(
        token,
        url_base,
        yml,
        data,
        *,
        doit=True,
        ):
    '''
    Starts new workflow run and returns its id.
    
    Args:
        token:
            Github token.
        url_base:
            E.g. `https://api.github.com/repos/ArtifexSoftware/PyMuPDF-julian`.
        yml:
            E.g. `test2.yml`.
        data:
            A dict.
    
    Returns workflow id.
    '''
    data['return_run_details'] = True
    pipcl.log(f'{url_base=}')
    pipcl.log(f'data:')
    pipcl.log(json.dumps(data, indent='    '))
    
    if not doit:
        pipcl.log(f'Not starting workflow because {doit=}.')
        return
    
    # https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event
    #
    run0_id = _gh_runs_newest(token, url_base)
    pipcl.log(f'{data=}')
    url = f'{url_base}/actions/workflows/{yml}/dispatches'
    r = _gh_post(token, url, json=data)
    pipcl.log(f'Have started new workflow run: {url=}')
    #pipcl.log(f'{r=}')
    r_json = r.json()
    pipcl.log(f'{r_json=}')
    pipcl.log(f'{json.dumps(r_json, indent="    ")}')

    # As of 2026-03-13 we use Github's new return_run_details flag when
    # creating the workflow, so new workflow id is in r.json(). Our code
    # relies on the id being a string, so we convert here.
    run_id = r_json['workflow_run_id']
    run_id = str(run_id)
    
    if 0:
        # Unfortunately `r` does not contain any information about the id of
        # the run we have just created. E.g. see:
        #
        #   https://stackoverflow.com/questions/69479400/get-run-id-after-triggering-a-github-workflow-dispatch-event
        #
        # That link has a way to embed a uid in the new run and detect it. But
        # for now we'll do things more crudely - repeatedly look for a new run
        # - it will be most recent run with different id from workflow0.
        #
        pipcl.log('Polling for first mention of the new workflow run we have just created...')
        while 1:
            run_id = _gh_runs_newest(token, url_base)
            pipcl.log(f'{run0_id=} {run_id=}')
            if run_id != run0_id:
                break
            time.sleep(10)
    pipcl.log(f'New workflow run is: {run_id=}')
    
    return run_id

        
def gh_workflow_download(
        token,
        url_base,
        *,
        id_='newest',
        block=True,
        local_dir=None,
        ):
    '''
    Waits for workflow to finish if it is in progress, then downloads the
    workflow's logs and artifacts.
    
    Args:
        token:
            Github token.
        url:
            .
        id_:
            If `newest` we use the newest workflow. Otherwise the id of the
            workflow to use.
        verbose:
            .
        block:
            If false we don't block, and return immediately if workflow still
            running.
        local_dir:
            .
        loglinks:
            If true, we construct softlinks in top if <local_dir> pointing to
            log files within the extracted data.
    
    Returns (workflow, directory):
        <workflow> is json dict.
        <directory>:
            Empty string: workflow was skipped.
            None: `block` is false and workflow not finished.
            Otherwise: local download directory,
    '''
    if id_ == 'newest':
        id_ = _gh_runs_newest(token, url_base)
        pipcl.log(f'{id_=}')
    
    workflow, e = gh_workflow_wait(token, url_base, id_=id_, block=block)
    if e is None:
        # Workflow still running.
        assert not block
        return workflow, None
    if 1:
        pipcl.log(f'workflow is:\n{json.dumps(workflow, indent="    ")}')
    name = workflow["name"].replace(' ', '-')
    created_at = workflow["created_at"]
    created_at = created_at.replace(':', '-')   # colons are a pain in unix shell.
    created_at = created_at.replace('T', '-')
    local_dir_infix = f'{local_dir}/' if local_dir else ''
    
    g_root = os.path.abspath(f'{__file__}/../..')
    root = f'{g_root}/{local_dir_infix}github_workflow_{name}_{created_at}_{id_}'
    os.makedirs(f'{g_root}/{local_dir_infix}', exist_ok=1)
    pipcl.log(f'{g_root=}')
    pipcl.log(f'{local_dir=}')
    pipcl.log(f'{local_dir_infix=}')
    pipcl.log(f'{root=}')
    
    # Get logs.
    #
    pipcl.log(f'{workflow.get("html_url")}: Downloading logs from workflow run.')
    path_logs = f'{root}_logs'
    path_logs_zip = f'{path_logs}.zip'
    pipcl.log('Downloading logs to:')
    pipcl.log(f'    {path_logs_zip}')
    pipcl.log(f'    {path_logs}')
    logs_url = workflow['logs_url']
    pipcl.log(f'    {logs_url=}')
    _gh_download(token, logs_url, path_logs_zip)
    _unzip(path_logs_zip, path_logs)

    # Get artifacts.
    #
    # First get intermedate json from workflow['artifacts_url']; this will
    # contain the url from which we download the artifact.
    #
    if workflow['conclusion'] == 'skipped':
        pipcl.log(f'{workflow.get("html_url")}: Not downloading artifact because workflow run skipped')
        return workflow, ''
    
    # We carry on downloading even if workflow failed, because sometimes
    # failures can be spurious and not effect the artifacts we are interested
    # in.
        
    path_artifact = f'{root}_artifact'
    path_artifact_zip = f'{path_artifact}.zip'
    r = _gh_get(token, workflow['artifacts_url'])
    pipcl.log(f'{workflow.get("html_url")}: {json.dumps(r.json(), indent=4)=}')
    artifacts = r.json()['artifacts']
    if artifacts:
        for artifact in artifacts:
            path_artifact = f'{root}_artifact_{artifact["name"]}'
            path_artifact_zip = f'{path_artifact}.zip'
            archive_download_url = artifact['archive_download_url']
            pipcl.log(f'{workflow.get("html_url")}: {archive_download_url=}')
            pipcl.log(f'{workflow.get("html_url")}: Downloading artifact to {path_artifact_zip=}')
            _gh_download(token, archive_download_url, path_artifact_zip)
            pipcl.log(f'{workflow.get("html_url")}: Extracting {path_artifact_zip=} to {path_artifact=}.')
            _unzip(path_artifact_zip, path_artifact)
    else:
        pipcl.log(f'{workflow.get("html_url")}: No artifacts available.')

    if workflow['conclusion'] != 'success':
        pipcl.log(
                f'{workflow.get("html_url")}: Workflow run failed, {root=} {workflow["conclusion"]=}:\n'
                '{json.dumps(workflow, indent=4)}',
                )
    
    pipcl.log(f'{local_dir=} {path_logs=}')
    ghlogs_links(local_dir, path_logs)
    
    if workflow['conclusion'] != 'success':
        raise Exception(f'{workflow.get("html_url")}: Workflow run failed')
    
    pipcl.log(f'{workflow.get("html_url")}: returning {root=}.')
    return workflow, root
    

def gh_workflows(token, url):
    '''
    Shows and returns available workflows.
    '''
    # Get list of available workflows.
    url = f'{url}/actions/workflows'
    r = _gh_get(token, url)
    response = r.json()
    pipcl.log(f'Available workflows are:\n{json.dumps(response, indent="    ")}')
    return response


def gh_workflow_wait(token, url, id_, block=True):
    '''
    Waits for specified workflow run to finish. Returns (workflow, e); e is:
        None:
            Not completed (only if <block> is false).
        0:
            success.
        Otherwise failure.
    '''
    if block:
        pipcl.log(f'Waiting for workflow to finish: {id_=}')
    t0 = time.time()
    dt = 0
    while 1:
        time.sleep(dt)
        t = time.time() - t0 + 1
        dt = t / 50
        dt = max(dt, 10)
        dt = min(dt, 5*60)
        try:
            run = _gh_workflow(token, url, id_)
        except Exception as e:
            pipcl.log(f'Ignoring failure to get Github workflow information: {e}')
            continue
        #print(json.dumps(run, indent=4))
        status = run[ 'status']
        if block:
            pipcl.log(f'{run.get("html_url")}: {t:.1f=} {dt:.1f=} {status=}')
        else:
            pipcl.log(f'{run.get("html_url")}: {status=}')
        if status == 'completed':
            pipcl.log(f'{run.get("html_url")}: Workflow has finished.')
            e = run['conclusion']
            if e == 'success':
                e = 0
            return run, e
        if not block:
            return run, None


def gh_branch_info(token, url, branch, verbose=True):
    '''
    Show detailed info about a github branch.
    '''
    r = _gh_get(token, f'{url}/branches/{branch}')
    ret = r.json()
    if verbose:
        pipcl.log(json.dumps(ret, indent='    '))
    return ret


def gh_assert_remote_branch_identical(token, url, branch, local_dir, check_clean_tree=True):
    '''
    Args:
        url:
            Git URL.
        check_clean_tree:
            If true we require that current tree is identical to remote tree
            after push. Otherwise we require that current committed tree is
            identical to remote tree after push, i.e. we allow uncommitted
            changes.
    '''
    assert url.startswith('https://api.github.com/repos/')
    pipcl.log(f'{url=}')
    remote_sha = _gh_get(token, f'{url}/branches/{branch}').json()['commit']['sha']
    pipcl.log(f'{url=} => {remote_sha=}.')
    e, text = pipcl.run(
            f'cd {local_dir} && git diff {"" if check_clean_tree else "--cached"} {remote_sha}',
            check=0,
            #out=[('log', 'git diff: '), (str, '')],
            )
    pipcl.log(f'{e=} {text=}')
    # Seems that, unlike `diff`, `git diff` always returns 0, even if diff is
    # non-empty? So we need to look at output `text`, not `e`.
    if text:
        raise Exception(f'Local checkout {local_dir} differs from {url} HEAD {remote_sha=}.')


def gh_community(token, url, verbose=True):
    '''
    Gets github community/profile info.
    '''
    r = _gh_get(token, f'{url}/community/profile')
    ret = r.json()
    if verbose:
        pipcl.log(json.dumps(ret, indent='    '))
    return ret


def gh_workflow_download_multiple(
        token,
        url_base,
        ids,
        *,
        download=True,
        extra_wheels=None,
        upload='',
        token_pypi=None,
        local_dir_union=None,
        ):
    '''
    Wait for workflows to finish, downloads to local machine, uploads to
    pypi.
    
    Returns local directory containing downloaded sdists and wheels.
    
    Can be safely run multiple times with the same `ids` - we don't re-download
    the same workflow results.
    
    ids:
        List, or comma/dash-separated string, of ids.
    extra_wheels:
        Extra pre-built wheels to upload. Can be comma-separated string.
    upload:
        Upload, e.g. 'pypi.org'. If contain a colon, we rsync.
    '''
    if isinstance(extra_wheels, str):
        extra_wheels = extra_wheels.split(',')
    pipcl.log(f'{ids=}')
    if isinstance(ids, str):
        if ',' in ids:
            ids = ids.split(',')
        elif '-' in ids:
            ids = ids.split('-')
        else:
            ids = [ids]
    else:
        ids = ids.copy()
    pipcl.log(f'{ids=}')
    pipcl.log(f'{",".join(ids)=}')
    ids0 = ids.copy()
    local_dir = f'gh_workflow-{time.strftime("%Y-%m-%d")}-{"-".join(ids)}'
    if not local_dir_union:
        local_dir_union = f'{local_dir}-union'
    pipcl.log(f'{ids=} {local_dir=}')
    directories = [None] * len(ids)
    pipcl.log(f'Waiting for workflows to finish: {ids=}')
    pipcl.log(f'Repeat with: {sys.argv[0]} gh_release_wait_upload --upload={upload} --download={download} {",".join(ids)}')
    t0 = time.time()
    dt = 0
    num_workflows_finished = 0
    errors = list()
    while 1:
        time.sleep(dt)
        t = time.time() - t0 + 1
        dt = t / 50
        dt = max(dt, 10)
        dt = min(dt, 5*60)
        for i, id_ in enumerate(ids):
            if not id_:
                continue
            e = None
            directory = None
            if download:
                try:
                    workflow, directory = gh_workflow_download(token, url_base, id_=id_, block=False, local_dir=local_dir)
                except Exception as ee:
                    e = ee
                    text = io.StringIO()
                    traceback.print_exc(file=text)
                    ee_detailed = text.getvalue()
                    #ee_detailed = jlib.exception_info(file=str)
                    pipcl.log(f'Workflow failed: {id_=} {ee}:\n{ee_detailed}')
                    errors.append(e)
                    workflow = None
                if directory or directory == '':    # Finished or skipped.
                    pipcl.log(f'{workflow.get("html_url")}: Workflow run has finished: {id_=} {directory=}')
                    directories[i] = directory + '_artifact' if directory else ''
                if e or directory or directory == '':
                    # Finished/skipped or (network) error getting workflow info.
                    ids[i] = None
                    num_workflows_finished += 1
                    if workflow:
                        pipcl.log(f'{workflow.get("html_url")}: {len(ids)=} {num_workflows_finished=}')
                    else:
                        pipcl.log(f'{len(ids)=} {num_workflows_finished=}')
                    if num_workflows_finished == len(ids):
                        break
            else:
                run, e = gh_workflow_wait(token, url_base, id_=id_, block=False)
                if e:
                    errors.append(e)
                ids[i] = None
                num_workflows_finished += 1
                pipcl.log(f'{run.get("html_url")}: {len(ids)=} {num_workflows_finished=}')
                if num_workflows_finished == len(ids):
                    break
        if num_workflows_finished == len(ids):
            break

    if not download:
        pipcl.log('All workflow(s) have finished. Not downloading.')
        for id_ in ids0:
            run = _gh_workflow(token, url_base, id_=id_)
            #pipcl.log(f'Info for {id_=}:\n{json.dumps(run, indent=4)}')
            pipcl.log(f'URL for {id_=}: {run.get("html_url")}')
        
        if errors:
            raise Exception(f'One or more workflows failed: {errors}')
        return
        
    pipcl.log('Have downloaded wheels for each python version:')

    # Show contents of download directory.
    #
    leaf_to_paths = dict()
    pipcl.log(f'{directories=}')
    for directory in directories:
        if not directory:
            continue
        pipcl.log(f'    {directory}*')
        for path in glob.glob(f'{directory}*/*'):
            pipcl.log(f'        {path}')
            leaf = os.path.basename(path)
            leaf_to_paths.setdefault(leaf, []).append(path)

    _check_identical_wheels(leaf_to_paths)
    
    pyodide_wheels = _create_download_union(leaf_to_paths, extra_wheels, local_dir_union)
    #pipcl.log(f'Have copied {len(pyodide_wheels)} Pyodide wheels into {local_dir_union}.')
    
    leafs = os.listdir(local_dir_union)
    pipcl.log(f'{local_dir_union}/ ({len(leafs)}):')
    for leaf in sorted(leafs):
        pipcl.log(f'    {local_dir_union}/{leaf}')
    
    if errors:
        raise Exception(f'One or more workflows failed: {errors}')

    if 0:
        # Create pypi-style 'simple' directory within local_dir_union.
        make_piprepo(local_dir_union)
        pipcl.log(f'Have created pypi {local_dir_union}/simple.')

    if upload:
        _upload(token_pypi, local_dir_union, pyodide_wheels, upload)


def make_piprepo(wheel_dir):
    pipcl.run(f'pip install --upgrade piprepo "setuptools<81"', prefix=f'pip install piprepo setuptools: ')
    pipcl.run(f'piprepo build {wheel_dir}')


def _check_identical_wheels(leaf_to_paths):
    # Some files such as sdist and PyMuPDFb-*.whl are generated by
    # each python-version-specific build.
    #
    # To be sure things are working, we check that these duplicate
    # files contain identical file trees. (The zip/tar files
    # themselves can be different due to being created with
    # different datestamps, so we extract each one and compare with
    # command-line diff -r.)
    #
    
    pipcl.log('Checking duplicate sdist/wheels')
    num_diffs = 0
    for leaf in sorted(leaf_to_paths.keys()):   # pylint: disable=too-many-nested-blocks
        paths = leaf_to_paths[ leaf]
        pipcl.log(f'{leaf}:')
        try:
            #def i_path(i):
            #    return f'pymupdf-temp-{i}'
            extracted_paths = []
            for i, path in enumerate(paths):
                st = os.stat(path)
                with open(path, 'rb') as f:
                    data = f.read()
                md5 = hashlib.md5(data)
                pipcl.log(f'    size={st.st_size:>12,} {md5.hexdigest()=} {path}')
                if leaf.startswith(('pymupdf4llm-', 'pdf4llm-')) and 'windows' in os.path.dirname(path):
                    pipcl.log(f'    [Ignoring pymupdf4llm wheel from windows because contains \\r characters so differs from non-windows builds')
                    continue
                extracted_path = f'pymupdf-temp-{i}-{os.path.basename(path)}'
                pipcl.fs_ensure_empty_dir(extracted_path)
                #pipcl.log(f'Extracting to temporary: {path} -> {path_extracted}')
                if path.endswith('.whl'):
                    with zipfile.ZipFile(path) as z:
                        z.extractall(extracted_path)
                elif path.endswith('.tar.gz'):
                    with tarfile.open(path) as z:
                        z.extractall(extracted_path)
                elif path.endswith('.xml'):
                    continue
                else:
                    assert 0, f'Unrecognised suffix: {path=}'
                extracted_paths.append(extracted_path)
            # Looks like cibuildwheel or auditwheel on Linux might be
            # reordering the items in RECORD files, so we sort them here.
            for path in extracted_paths:
                for dirpath, _dirnames, filenames in os.walk(path):
                    for filename in filenames:
                        if filename == 'RECORD':
                            p = os.path.join(dirpath, filename)
                            pipcl.log(f'Sorting: {p}')
                            t = pipcl.fs_read(p)
                            t2 = t.split('\n')
                            t2.sort()
                            t3 = '\n'.join(t2)
                            assert len(t3) == len(t)
                            pipcl.fs_write(p, t3)
            numdiffs0 = 0
            for i in range(len(extracted_paths)-1):
                excludes = list()
                excludes_text = ''
                if 'win32' in leaf or 'win_amd64' in leaf:
                    # Windows .dll's seem to contain timestamps so are
                    # not identical between builds.
                    excludes += ['*.dll', 'RECORD']
                if 'macosx_11_0_arm64' in leaf:
                    # 2024-03-21: libmupdf.dylib sometimes differ.
                    excludes += [
                            'libmupdf.dylib',
                            'RECORD',
                            'libmupdfcpp.so',   # Added 2024-05-08.
                            ]
                for ex in excludes:
                    excludes_text += f' -x "{ex}"'
                e = pipcl.run(
                        f'diff -qr {excludes_text} {extracted_paths[i]} {extracted_paths[i+1]}',
                        check=0,
                        #out='log',
                        )
                if e:
                    numdiffs0 += 1
                    pipcl.log(f'### Files/dirs differ:')
                    pipcl.log(f'###     { extracted_paths[i]}')
                    pipcl.log(f'###     { extracted_paths[i+1]}')
                if excludes:
                    e = 0
                    for dirpath, _dirnames, filenames in os.walk(extracted_paths[i]):
                        for filename in filenames:
                            match = 0
                            for exclude in excludes:
                                if fnmatch.fnmatch(filename, exclude):
                                    match = 1
                                    break
                            if match:
                                p1 = os.path.join(dirpath, filename)
                                assert p1.startswith(extracted_paths[i])
                                p2 = extracted_paths[i+1] + p1[len(extracted_paths[i]):]
                                pipcl.log(f'Comparing just the sizes of {p1} and {p2}.')
                                assert p1 != p2
                                p1_size = pipcl.fs_filesize(p1, -1)
                                p2_size = pipcl.fs_filesize(p2, -1)
                                assert p1_size != -1 and p2_size != -1
                                if p1_size != p2_size:
                                    pipcl.log(f'Files differ in size:')
                                    pipcl.log(f'    {p1_size: 10}: {p1}')
                                    pipcl.log(f'    {p2_size: 10}: {p2}')
                                    e = 1
                    if e:
                        numdiffs0 += 1
            if numdiffs0:
                num_diffs += numdiffs0
            else:
                for extracted_path in extracted_paths:
                    assert extracted_path.startswith('pymupdf-temp-')
                    pipcl.fs_remove(extracted_path)
        finally:
            for extracted_path in extracted_paths:
                if num_diffs:
                    pipcl.log(f'Not removing extracted files in: {extracted_path}')
                else:
                    pipcl.log(f'Would remove: {extracted_path=}')
                    #pipcl.fs_remove(extracted_path)

    pipcl.log(f'{num_diffs=}')
    assert num_diffs == 0


def _create_download_union(leaf_to_paths, extra_wheels, local_dir_union):
    '''
    Copies wheels from leaf_to_paths[...] and <extra_wheels> into
    <local_dir_union>.
    '''
    pyodide_wheels = list()
    
    # Copy sdist and wheels into new 'union' directory.
    #
    pipcl.log(f'Copying sdist and wheels into: {local_dir_union}/')
    os.makedirs(local_dir_union, exist_ok=1)
    
    pipcl.log(f'{leaf_to_paths=}')
    pipcl.log(f'{extra_wheels=}')
    if extra_wheels:
        for extra_wheel in extra_wheels:
            pipcl.log(f'Copying {extra_wheel=} into {local_dir_union}/:')
            pipcl.run(f'rsync -ai {extra_wheel} {local_dir_union}/')
    
    for leaf, paths in leaf_to_paths.items():
        if not leaf.endswith(('.whl', '.tar.gz')):
            pipcl.log(f'Ignoring {leaf=}.')
            continue
        if 'emscripten' in leaf:
            pipcl.log(f'Pyodide wheel: {leaf=} {paths=}')
            pyodide_wheels.append((leaf, paths))
            continue
        path = paths[0]
        path_leaf = os.path.basename(path)
        path_existing = f'{local_dir_union}/{path_leaf}'
        if os.path.exists(f'{local_dir_union}/{path_leaf}'):
            if path_leaf.endswith('.whl'):
                _check_identical_wheels(dict(path_leaf=[path_existing, path]))
            else:
                a = pipcl.fs_read(path_existing, binary=1)
                b = pipcl.fs_read(path, binary=1)
                assert a == b, (
                        f'Differing file already exists in {local_dir_union=}:\n'
                        f'    {path_existing=}\n'
                        f'    {path=}'
                        )
                pipcl.log(f'Identical file already exists: {local_dir_union}/{leaf}')
            continue
        #assert not os.path.exists(f'{local_dir_union}/{path_leaf}'), \
        #        f'File already exists in {local_dir_union=}: {path_leaf}'
        if platform.system() == 'Windows':
            # rsync seems flakey on Windows, possibly because on my Windows
            # it's provided by cygwin.
            shutil.copy2(path, local_dir_union)
        else:
            pipcl.run(f'rsync -ai {path} {local_dir_union}/')
    pipcl.log(f'Have populated {local_dir_union=}.')
    return pyodide_wheels


def _upload(token_pypi, local_dir_union, pyodide_wheels, upload):
    # Upload.
    if isinstance(upload, str) and ':' in upload:
        command = f'rsync -ai {local_dir_union}/ {upload}/'
        pipcl.log(f'Will upload to {upload}/:')
        pipcl.run(f'ls -ld {local_dir_union}/*')
        while 1:
            pipcl.log(f'{command=}')
            #yes = input(jlib.log_text('Upload with this command? Enter "yes" if you are sure... ? ', nl=0))
            yes = input('Upload with this command? Enter "yes" if you are sure... ? ')
            if yes == 'yes':
                pipcl.run(command)
                break

    else:
        assert upload in ('pypi', 'test.pypi'), f'{upload=}'
        paths = list()
        for path in glob.glob(f'{local_dir_union}/*.whl') + glob.glob(f'{local_dir_union}/*.tar.gz'):
            if 'pyodide' in path:
                pipcl.log(f'Ignoring pyodide wheel: {path}')
            else:
                paths.append(path)
        paths.sort()
        pipcl.log(f'{len(paths)=}:')
        for path in paths:
            assert path.endswith('.whl') or path.endswith('.tar.gz')
            s = pipcl.fs_filesize(path)
            pipcl.log(f'    {s:>12,} {path}')
        while 1:
            #yes = input(jlib.log_text(f'Will upload to {upload}. Enter "yes" if you are sure... ? ', nl=0))
            yes = input(f'Will upload to {upload}. Enter "yes" if you are sure... ? ')
            if yes == 'yes':
                break
        upload_pypi(token_pypi, paths, pypi_test=(upload=='test.pypi'))
    
    if pyodide_wheels:
        pipcl.log(f'Pyodide wheel(s):')
        for _leaf, paths in pyodide_wheels:
            for path in paths:
                pipcl.log(f'    {os.path.relpath(path)}')
    return local_dir_union

def cpu_bits():
    return int.bit_length(sys.maxsize+1)


def upload_pypi(token_pypi, paths, pypi_test: bool=False):
    num_tgz = 0
    num_whl = 0
    num_other = 0
    files = []
    
    if isinstance(paths, str):
        paths = paths.split(',')
    
    paths.sort()
    for path in paths:
        if path.endswith('.tar.gz'):
            num_tgz += 1
        elif path.endswith('.whl'):
            num_whl += 1
        else:
            num_other +=1
        files.append(path)
    pipcl.log(f'{num_tgz=} {num_whl=} {num_other=}')
    #if not pypi_test:
    #    assert num_tgz == 1
    assert num_other == 0
    #pipcl.log(f'Calling pypackage.upload0().')
    #pypackage.upload0(files, pypi_test, token=g_pypi_token, prompt=True)
    #pipcl.log(f'Called pypackage.upload0().')
    
    venv = f'venv-github-{platform.python_version()}-{cpu_bits()}'
    command = ''
    command = f'{sys.executable} -m venv {venv}'
    command += f' && . {venv}/bin/activate'
    command += f' && python -m pip install twine'
    pipcl.run(command)
    
    destination = 'test.pypi.org' if pypi_test else 'pypi.org'
    command = ''
    command += f'. {venv}/bin/activate'
    command += f' && python -m twine upload'
    command += f' --disable-progress-bar'
    if pypi_test:
        command += f' --repository testpypi'
    assert token_pypi
    command += f' -u __token__ -p {token_pypi}'
    #else:
    #    token_path = os.path.expanduser('~/artifex/token-pypi.org')
    #    with open(token_path) as f:
    #        token = f.read().strip()
    #    command += f' -u __token__ -p {token}'
    command += ' ' + ' '.join(files)
    while 1:
        pipcl.log(f'Uploading {len(files)} files to {destination}:')
        for file_ in files:
            pipcl.log(f'    {file_}')
        pipcl.log(f'command is: {command}')
        input(f'Press <enter> to run command and upload to {destination} ... ? ')
        try:
            pipcl.run(command)
        except Exception  as e:
            pipcl.log(f'Failed to upload: {e=}')
            #jlib.exception_info()
            traceback.print_exc()
            input('Press <enter> to retry... ? ')
        else:
            break


def main():
    args = iter(sys.argv[1:])
    while 1:
        try:
            arg = next(args)
        except StopIteration:
            break
        if arg == 'make-pypi':
            wheel_dir = next(args)
            make_piprepo(wheel_dir)
        else:
            assert 0, f'Unrecognised {arg=}.'


if __name__ == '__main__':
    sys.exit(main())
