import pipcl


def build():
    
    sha, comment, diff, branch = pipcl.git_info('.')
    gitinfo = f'{sha=}\n{comment=}\n{branch=}\n{diff=}\n'
    return [
            ('aptest.py', 'artifex_aptest/__init__.py'),
            ('autovenv.py', 'artifex_aptest/'),
            ('backtrace.py', 'artifex_aptest/'),
            ('cli.py', 'artifex_aptest/'),
            ('doct.py', 'artifex_aptest/'),
            ('graph.py', 'artifex_aptest/'),
            ('github.py', 'artifex_aptest/'),
            ('README.rst', 'artifex_aptest/'),
            (gitinfo.encode('utf8'), 'artifex_aptest/gitinfo.py'),
            ]


def sdist():
    ret = list()
    for p in pipcl.git_items('.'):
        ret.append(p)
    return ret


p = pipcl.Package(
        'artifex_aptest',
        version = str(1),
        pure = True,
        description='README.rst',
        summary='Artifex package testing',
        author='Artifex',
        author_email='julian.smith@artifex.com',
        requires_dist = ['pipcl'],
        entry_points = '''
            [console_scripts]
            aptest = artifex_aptest:main0
            ''',
        fn_build = build,
        )

build_wheel = p.build_wheel
build_sdist = p.build_sdist

if __name__ == '__main__':
    import sys
    p.handle_argv(sys.argv)
