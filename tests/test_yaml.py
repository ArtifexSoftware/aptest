import os

import pipcl


def test_yaml_lint():
    pipcl.run(f'pip install yamllint')
    top = os.path.normpath(f'{__file__}/../../')
    # Yamllint complains about carriage return line-endings on Windows.
    r = ', new-lines: disable' if pipcl.windows() else ''
    pipcl.run(f'yamllint -f parsable -d "{{extends: default, rules: {{trailing-spaces: disable, indentation: disable, line-length: disable{r}}}}}" {top}/.github/workflows')
