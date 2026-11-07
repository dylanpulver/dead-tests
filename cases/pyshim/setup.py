import sys

# A pre-install guard legitimately checks the running interpreter.
if sys.version_info < (3, 10):
    raise SystemExit("needs Python 3.10 or newer")
