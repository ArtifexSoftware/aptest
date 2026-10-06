import os

import pipcl


def  test_yaml_lint():
    pipcl.run(f'pip install yamllint')
    top = os.path.normpath(f'{__file__}/../../')
    pipcl.run(f'yamllint -f parsable -d "{{extends: default, rules: {{trailing-spaces: disable, indentation: disable, line-length: disable}}}}" {top}/.github/workflows')
