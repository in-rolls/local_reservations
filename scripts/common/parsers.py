"""Import a state's parser under a name of its own.

Every state calls its parser `parse.py`. A plain `import parse` therefore
resolves to whichever one reached sys.path first, and the second test module to
run gets that same module back out of the cache - so it tests another state's
code while appearing to pass. That is exactly the failure this repository keeps
running into: a plausible result rather than an error.
"""

import importlib.util
import pathlib
import sys

SCRIPTS = pathlib.Path(__file__).resolve().parent.parent


def load(state):
    """Return `scripts/<state>/parse.py` as a module named `<state>_parse`."""
    name = f"{state}_parse"
    if name in sys.modules:
        return sys.modules[name]
    path = SCRIPTS / state / "parse.py"
    if not path.exists():
        raise FileNotFoundError(path)
    # the parsers add scripts/common to sys.path themselves, for emit/normalize
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
