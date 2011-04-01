from StringIO import StringIO
import sys

from eventlet.corolocal import local

from dtest.exceptions import DTestException


_installed = False
_saves = {}


class Capturer(object):
    _capturers = {}
    _caporder = []

    def __new__(cls, name, desc, init, retrieve, install, uninstall):
        # First, make sure name isn't already in use
        if name in cls._capturers:
            return cls._capturers[name]

        # Don't allow new capturer registrations after we're installed
        if _installed:
            raise DTestException("Capturers have already been installed")

        # Verify that init and retrieve are callables
        if not callable(init):
            raise DTestException("%r must be a callable "
                                 "initialization routine" % init)
        elif not callable(retrieve):
            raise DTestException("%r must be a callable "
                                 "retrieval routine" % retrieve)
        elif not callable(install):
            raise DTestException("%r must be a callable "
                                 "installation routine" % install)
        elif not callable(uninstall):
            raise DTestException("%r must be a callable "
                                 "uninstallation routine" % uninstall)

        # OK, construct a new one
        cap = super(Capturer, cls).__new__(cls)
        cap.name = name
        cap.desc = desc
        cap.init = init
        cap.retrieve = retrieve
        cap.install = install
        cap.uninstall = uninstall

        # Save it in the cache
        cls._capturers[name] = cap
        cls._caporder.append(name)

        # And return it
        return cap


class _CaptureLocal(local):
    def __init__(self):
        # Walk through all the capturers and initialize them
        for cap in Capturer._capturers.values():
            setattr(self, cap.name, cap.init(cap))


_caplocal = _CaptureLocal()


def retrieve():
    # Walk through all the capturers and retrieve their description
    # and value
    vals = []
    for name in Capturer._caporder:
        # Get the capturer
        cap = Capturer._capturers[name]

        # Get the current value of the capturer and re-initialize it
        val = cap.retrieve(cap, getattr(_caplocal, name))
        setattr(_caplocal, name, cap.init(cap))

        # Push down the value and other important data
        if val:
            vals.append((cap.name, cap.desc, val))

    # Return the captured values
    return vals


class CaptureProxy(object):
    def __init__(self, capname):
        # Save the capturer name of interest
        super(CaptureProxy, self).__setattr__('_capname', capname)

    def __getattr__(self, attr):
        # Proxy out to the appropriate object
        return getattr(getattr(_caplocal, self._capname), attr)

    def __setattr__(self, attr, value):
        # Proxy out to the appropriate object
        return setattr(getattr(_caplocal, self._capname), attr, value)

    def __delattr__(self, attr):
        # Proxy out to the appropriate stream
        return delattr(getattr(_caplocal, self._capname), attr)


def install():
    global _installed

    # Do nothing if we're already installed
    if _installed:
        return

    # Remember that we've been installed
    _installed = True

    # Perform the install
    for cap in Capturer._capturers.values():
        _saves[cap.name] = cap.install(cap, CaptureProxy(cap.name))


def uninstall():
    global _installed
    global _saves

    # Do nothing if we haven't been installed
    if not _installed:
        return

    # Restore our saved objects
    for cap in Capturer._capturers.values():
        cap.uninstall(cap, _saves[cap.name])

    # Reset our state
    _saves = {}
    _installed = False


def _st_init(cap):
    # Create a new StringIO stream
    return StringIO()


def _st_retrieve(cap, st):
    # Retrieve the value of the StringIO stream
    return st.getvalue()


def _st_install(cap, new):
    # Retrieve and return the old stream and install the new one
    old = getattr(sys, cap.name)
    setattr(sys, cap.name, new)
    return old


def _st_uninstall(cap, old):
    # Re-install the old stream
    setattr(sys, cap.name, old)
    pass


# Add capturers for stdout and stderr
Capturer('stdout', 'Standard Output', _st_init, _st_retrieve,
         _st_install, _st_uninstall)
Capturer('stderr', 'Standard Error', _st_init, _st_retrieve,
         _st_install, _st_uninstall)
