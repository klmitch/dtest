from StringIO import StringIO
import sys

from eventlet.corolocal import local

from dtest.exceptions import DTestException


_installed = False
_saves = {}


class Capturer(object):
    _capturers = {}
    _caporder = []

    def __new__(cls, name, desc):
        # First, make sure name isn't already in use
        if name in cls._capturers:
            return cls._capturers[name]

        # Don't allow new capturer registrations after we're installed
        if _installed:
            raise DTestException("Capturers have already been installed")

        # OK, construct a new one
        cap = super(Capturer, cls).__new__(cls)
        cap.name = name
        cap.desc = desc

        # Save it in the cache
        cls._capturers[name] = cap
        cls._caporder.append(name)

        # And return it
        return cap

    def init(self):
        # Initialize a capturer; returns an object that looks like
        # whatever's being captured, but from which a value can later
        # be retrieved.
        raise DTestException("%s.%s.init() unimplemented" %
                             (self.__class__.__module__,
                              self.__class__.__name__))

    def retrieve(self, captured):
        # Retrieve the value of a capturer; takes the object returned
        # by init() and returns its string value.
        raise DTestException("%s.%s.retrieve() unimplemented" %
                             (self.__class__.__module__,
                              self.__class__.__name__))

    def install(self, new):
        # Install the capture proxy specified by new; should place
        # that object into the appropriate place so that it can
        # capture output.  Should return the old value, which will
        # later be passed to uninstall.
        raise DTestException("%s.%s.install() unimplemented" %
                             (self.__class__.__module__,
                              self.__class__.__name__))

    def uninstall(self, old):
        # Uninstall the capture proxy by replacing it with the old
        # value specified.  The old value will be the value returned
        # by install().
        raise DTestException("%s.%s.uninstall() unimplemented" %
                             (self.__class__.__module__,
                              self.__class__.__name__))


class _CaptureLocal(local):
    def __init__(self):
        # Walk through all the capturers and initialize them
        for cap in Capturer._capturers.values():
            setattr(self, cap.name, cap.init())


_caplocal = _CaptureLocal()


def retrieve():
    # Walk through all the capturers and retrieve their description
    # and value
    vals = []
    for name in Capturer._caporder:
        # Get the capturer
        cap = Capturer._capturers[name]

        # Get the current value of the capturer and re-initialize it
        val = cap.retrieve(getattr(_caplocal, name))
        setattr(_caplocal, name, cap.init())

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
        _saves[cap.name] = cap.install(CaptureProxy(cap.name))


def uninstall():
    global _installed
    global _saves

    # Do nothing if we haven't been installed
    if not _installed:
        return

    # Restore our saved objects
    for cap in Capturer._capturers.values():
        cap.uninstall(_saves[cap.name])

    # Reset our state
    _saves = {}
    _installed = False


class StdStreamCapturer(Capturer):
    def init(self):
        # Create a new StringIO stream
        return StringIO()

    def retrieve(self, st):
        # Retrieve the value of the StringIO stream
        return st.getvalue()

    def install(self, new):
        # Retrieve and return the old stream and install the new one
        old = getattr(sys, self.name)
        setattr(sys, self.name, new)
        return old

    def uninstall(self, old):
        # Re-install the old stream
        setattr(sys, self.name, old)


# Add capturers for stdout and stderr
StdStreamCapturer('stdout', 'Standard Output')
StdStreamCapturer('stderr', 'Standard Error')
