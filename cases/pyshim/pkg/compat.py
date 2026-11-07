import sys


def dead_body():
    # The condition is false on every supported version.
    if sys.version_info < (3, 10):
        return "legacy"
    return "modern"


def dead_else():
    # The condition is true on every supported version, so the else is dead.
    if sys.version_info >= (3, 10):
        return "modern"
    else:
        return "legacy"


def still_branches():
    if sys.version_info < (3, 12):
        return "older"
    return "newer"


def platform_branch():
    if sys.platform == "win32":
        return "windows"
    return "posix"


def awaits_future():
    if sys.version_info >= (3, 15):
        return "future"
    return "now"


def exact_patch_release():
    # black does this for a real memory-safety bug in 3.12.5, so it is live.
    if sys.version_info[:3] == (3, 12, 5):
        return "warn"
    return "fine"


def platform_and_version():
    # prefect gates on both; live on Windows below 3.14, so not dead.
    if sys.platform == "win32" and sys.version_info < (3, 14):
        return "windows-workaround"
    return "normal"


def refuses_old_interpreter():
    # A guard, not a shim: it exists because metadata can be bypassed.
    if sys.version_info < (3, 10):
        raise RuntimeError("needs Python 3.10 or newer")


def refuses_by_writing(stream):
    # pipenv's resolver does this: it runs under the USER's interpreter, so the
    # package's own requires-python does not constrain it. A guard can refuse by
    # writing a readable message and returning a code, without raising.
    if sys.version_info < (3, 10):
        stream.write("needs Python 3.10 or newer\n")
        return 1
    return 0


def maintainer_said_keep_it():
    # noqa: UP036 is ruff's outdated-version-block rule. Suppressing it is a
    # written decision to keep the branch.
    if sys.version_info < (3, 10):  # noqa: UP036
        return "legacy"
    return "modern"
