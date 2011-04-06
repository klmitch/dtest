"""
=======================
Generic Output Capturer
=======================

This module contains the Capturer class, which can be used to capture
arbitrary output from tests in a thread-safe fashion.  A new Capturer
is defined by subclassing the Capturer class and providing
implementations for the init(), retrieve(), install(), and uninstall()
methods; then, the subclass is instantiated.  Once instantiated,
capturing by the test framework is automatic--registration of the
instance is done by the Capturer constructor.  The module also defines
StdStreamCapturer and produces two instantiations of it, for capturing
stdout and stderr.

Usage
-----

Each Capturer instance must have a unique name, and additionally a
description, which will be output in the test report.  The init()
method of a Capturer instance is called to create a new object to
intercept and store the output; for stream-like Capturer instances,
this could simply return, say, an instantiation of StringIO.  The
retrieve() method will be passed this object and must return a string
consisting of all the output.  The install() and uninstall() methods
cooperate to install a special CaptureProxy object.  For an example of
a full Capturer subclass, check out StdStreamCapturer, contained
within this module:

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

Implementation Details
----------------------

The eventlet.corolocal.local class is used to maintain a set of
capturing objects (as initialized by the Capturer.init() method) for
each thread.  The Capturer.install() method is used by the framework
to install a special CaptureProxy object, which uses this thead-local
data to proxy all attribute accesses to the correct capturing object.
Once a test is complete, the captured data is retrieved by calling the
Capturer.retrieve() method, and once all tests have finished, the
Capturer.uninstall() method is used to restore the original values
that the Capturer.install() method discovered when it installed the
CaptureProxy object.

The capture module exports three functions used only by the framework;
these probably should not be called directly by a test author.  The
retrieve() function retrieves the captured data by calling the
Capturer.retrieve() methods in turn; the data is returned in the same
order in which it was registered.

The next two internal functions are install() and uninstall(), which
simply call the Capturer.install() and Capturer.uninstall() methods in
turn.  Note that these calls are not made in any defined order, so
test authors should not rely on any given ordering.

The capture module also pre-defines two Capturer instances, one for
capturing output to sys.stdout, and the other for capturing output to
sys.stderr; the code for this is included in the example above, and
can be referred to while building your own Capturer subclasses.
"""

from StringIO import StringIO
import sys

from eventlet.corolocal import local

from dtest.exceptions import DTestException


# Globals needed for capturing
_installed = False
_saves = {}


class Capturer(object):
    """
    Capturer
    ========

    The Capturer class is an abstract class which keeps track of all
    instances.  It is used to set up new output capturers, in a
    thread-safe way.  Subclasses must implement the init(),
    retrieve(), install(), and uninstall() methods.  The Capturer
    class should not be instantiated directly, as these necessary
    methods are unimplemented.

    Two class variables are defined; the _capturers dictionary stores
    a mapping from a Capturer ``name`` to a Capturer instance, while
    the _caporder list contains a list of Capturer ``name``s in the
    order in which they were instantiated.
    """

    _capturers = {}
    _caporder = []

    def __new__(cls, name, desc):
        """
        Allocate and initialize a Capturer.  Each instance of Capturer
        must have a unique ``name``; this name permits distinct
        Capturer instances to be looked up by CaptureProxy instances.
        The ``desc`` argument should contain a short description which
        will be used to indicate the source of the capture in the test
        output.

        If an attempt to reuse a ``name`` is made, the previous
        instance of that name will be returned, rather than a new one
        being instantiated.
        """

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
        """
        Initialize a Capturer object.  Should return an object which
        exports the appropriate interface for the output being
        intercepted.  All subclasses must implement this method.
        """

        # Initialize a capturer; returns an object that looks like
        # whatever's being captured, but from which a value can later
        # be retrieved.
        raise DTestException("%s.%s.init() unimplemented" %
                             (self.__class__.__module__,
                              self.__class__.__name__))

    def retrieve(self, captured):
        """
        Retrieve data from a Capturer object.  The ``captured``
        argument will be an object returned by the init() method.
        Should return a string consisting of the output data.  All
        subclasses must implement this method.
        """

        # Retrieve the value of a capturer; takes the object returned
        # by init() and returns its string value.
        raise DTestException("%s.%s.retrieve() unimplemented" %
                             (self.__class__.__module__,
                              self.__class__.__name__))

    def install(self, new):
        """
        Install a CaptureProxy object.  The ``new`` argument will be a
        CaptureProxy object, which will delegate all accesses to an
        appropriate object returned by the init() method.  Should
        return the old value of whatever interface is being captured.
        All subclasses must implement this method.
        """

        # Install the capture proxy specified by new; should place
        # that object into the appropriate place so that it can
        # capture output.  Should return the old value, which will
        # later be passed to uninstall.
        raise DTestException("%s.%s.install() unimplemented" %
                             (self.__class__.__module__,
                              self.__class__.__name__))

    def uninstall(self, old):
        """
        Uninstall a CaptureProxy object.  The ``old`` argument will be
        a value returned by the install() method.  The CaptureProxy
        object installed by install() should be uninstalled and
        replaced by the original object specified by ``old``.  All
        subclasses must implement this method.
        """

        # Uninstall the capture proxy by replacing it with the old
        # value specified.  The old value will be the value returned
        # by install().
        raise DTestException("%s.%s.uninstall() unimplemented" %
                             (self.__class__.__module__,
                              self.__class__.__name__))


class _CaptureLocal(local):
    """
    _CaptureLocal
    =============

    The _CaptureLocal class extends eventlet.corolocal.local to
    provide thread-local data.  Its attributes map to objects returned
    by the init() methods of the corresponding Capturer instances, and
    are unique to each thread.
    """

    def __init__(self):
        """
        Initialize a _CaptureLocal object in each thread.  For each
        defined Capturer instance, calls the init() method of that
        object and stores it in an attribute with the same name as the
        Capturer.  This is the magic that allows CaptureProxy to send
        output to the correct place.
        """

        # Walk through all the capturers and initialize them
        for cap in Capturer._capturers.values():
            setattr(self, cap.name, cap.init())


_caplocal = _CaptureLocal()


def retrieve():
    """
    Retrieve captured output for the current thread.  Returns a list
    of tuples, in the same order in which the corresponding Capturer
    instances were allocated.  Each tuple contains the Capturer name,
    its description, and the captured output.  The capture objects are
    reinitialized by this function.
    """

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
    """
    CaptureProxy
    ============

    The CaptureProxy class delegates all attribute accesses to a
    thread-specific object initialized by the Capturer.init() method.
    The only local attribute of a CaptureProxy object is the _capname
    attribute, which stores the name of the Capturer the CaptureProxy
    is acting on behalf of.  CaptureProxy objects are to be installed
    by the Capturer.install() method and uninstalled by the
    Capturer.uninstall() method.
    """

    def __init__(self, capname):
        """
        Initialize a CaptureProxy by storing the Capturer name.
        """

        # Save the capturer name of interest
        super(CaptureProxy, self).__setattr__('_capname', capname)

    def __getattr__(self, attr):
        """
        Delegate attribute accesses to the proxied, thread-specific
        capturing object.
        """

        # Proxy out to the appropriate object
        return getattr(getattr(_caplocal, self._capname), attr)

    def __setattr__(self, attr, value):
        """
        Delegate attribute updates to the proxied, thread-specific
        capturing object.
        """

        # Proxy out to the appropriate object
        return setattr(getattr(_caplocal, self._capname), attr, value)

    def __delattr__(self, attr):
        """
        Delegate attribute deletions to the proxied, thread-specific
        capturing object.
        """

        # Proxy out to the appropriate stream
        return delattr(getattr(_caplocal, self._capname), attr)


def install():
    """
    Install CaptureProxy objects for all defined Capturer instances.
    For each Capturer instance, the install() method will be called.
    """

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
    """
    Uninstall CaptureProxy objects for all defined Capturer instances.
    For each Capturer instance, the uninstall() method will be called.
    """

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
    """
    StdStreamCapturer
    =================

    The StdStreamCapturer is a subclass of Capturer defined to capture
    the standard output and error streams, sys.stdout and sys.stderr,
    respectively.  Output is captured using a StringIO().
    """

    def init(self):
        """
        Initialize a Capturer object.  Returns an instance of
        StringIO.
        """

        # Create a new StringIO stream
        return StringIO()

    def retrieve(self, st):
        """
        Retrieve data from a Capturer object.  The ``st`` argument is
        a StringIO object allocated by the init() method.  Returns a
        string with the contents of the StringIO object.
        """

        # Retrieve the value of the StringIO stream
        return st.getvalue()

    def install(self, new):
        """
        Install a CaptureProxy object.  The ``new`` argument is a
        CaptureProxy object, which is installed in place of sys.stdout
        or sys.stderr (depending on the name used to instantiate the
        Capturer instance).  Returns the original value of the stream
        being replaced.
        """

        # Retrieve and return the old stream and install the new one
        old = getattr(sys, self.name)
        setattr(sys, self.name, new)
        return old

    def uninstall(self, old):
        """
        Uninstall a CaptureProxy object.  The ``old`` argument is the
        original value of the stream, as returned by the install()
        method.  Re-installs that in place of the CaptureProxy object
        installed by install().
        """

        # Re-install the old stream
        setattr(sys, self.name, old)


# Add capturers for stdout and stderr
StdStreamCapturer('stdout', 'Standard Output')
StdStreamCapturer('stderr', 'Standard Error')
