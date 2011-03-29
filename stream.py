from StringIO import StringIO
import sys

from eventlet.corolocal import local


_installed = False
_save_out = None
_save_err = None


class _StreamLocal(local):
    def __init__(self):
        # Initialize the output and error streams
        self.out = StringIO()
        self.err = StringIO()


_stlocal = _StreamLocal()


def pop():
    # Get the out stream contents, then close and replace the stream
    out = _stlocal.out.getvalue()
    _stlocal.out.close()
    _stlocal.out = StringIO()

    # Ditto with the error stream contents
    err = _stlocal.err.getvalue()
    _stlocal.err.close()
    _stlocal.err = StringIO()


class StreamProxy(object):
    def __init__(self, stname):
        # Save the stream name of interest
        self._stname = stname

    def __getattr__(self, attr):
        # Proxy out to the appropriate stream
        return getattr(getattr(_stlocal, self._stname), attr)

    def __setattr__(self, attr, value):
        # Proxy out to the appropriate stream
        return setattr(getattr(_stlocal, self._stname), attr, value)

    def __delattr__(self, attr):
        # Proxy out to the appropriate stream
        return delattr(getattr(_stlocal, self._stname), attr)


def install():
    global _installed
    global _save_out
    global _save_err

    # Do nothing if we're already installed
    if _installed:
        return

    # Remember that we've been installed
    _installed = True

    # Save original stdout and stderr
    _save_out = sys.stdout
    _save_err = sys.stderr

    # Replace them with StreamProxy instances
    sys.stdout = StreamProxy('out')
    sys.stderr = StreamProxy('err')


def uninstall():
    global _save_out
    global _save_err

    # Do nothing if we haven't been installed
    if not _installed:
        return

    # Restore original stdout and stderr
    sys.stdout = _save_out
    sys.stderr = _save_err

    # Reset our state
    _save_out = None
    _save_err = None
    _installed = False
