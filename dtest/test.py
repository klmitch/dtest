"""
=====
Tests
=====

This module contains all the classes and decorators necessary for
manipulating tests.  The DTestBase class is the root of the
inheritance tree for DTest and DTestFixture, which respectively
represent tests and test fixtures.  The DTestCaseMeta class is a
metaclass for DTestCase, which is equivalent to unittest.TestCase for
the dependency-based test framework.  This module also contains a
number of decorators, such as @istest, @nottest, @skip, @failing,
@attr(), @depends(), @raises(), and @timed(), along with the debugging
utility function dot().
"""

import re
import sys
import types

from dtest.constants import *
from dtest import exceptions
from dtest import result


SETUP = 'setUp'
TEARDOWN = 'tearDown'
CLASS = 'Class'


def _func_name(func, cls=None):
    """
    Generates a string representation of the fully-qualified name of
    ``func``.
    """

    # Determine the actual function...
    if not callable(func):
        func = func.__func__

    # Don't include the class name if cls is None
    if cls is None:
        return '.'.join([func.__module__, func.__name__])

    # Is cls a string?
    if not isinstance(cls, basestring):
        cls = cls.__name__

    return '.'.join([func.__module__, cls, func.__name__])


class DTestBase(object):
    """
    DTestBase
    =========

    The DTestBase class is a base class for the DTest and DTestFixture
    classes, and contains a number of common elements.  Most users
    will only be interested in the attribute manipulation methods,
    which allows attributes to be attached to tests (see also the
    @attr() decorator); the stringification method, which generates a
    string name for the test based on the function or method wrapped
    by the DTestBase instance; and the following properties:

    :result:
        The result of the most recent test run; may be None if the
        test has not yet been run.

    :state:
        The state of the most recent test run; may be None if the test
        has not yet been run.

    :test:
        The actual function or method implementing the test.

    :class_:
        If the test is a method of a class, this property will be the
        appropriate class; otherwise, None.

    :skip:
        True if the @skip decorator has been used on the test.

    :failing:
        True if the @failing decorator has been used on the test.

    :dependencies:
        The tests this test is dependent on.

    :dependents:
        The tests that are dependent on this test.

    :raises:
        The set of exceptions this test can raise; declared using the
        @raises() decorator.

    :timeout:
        The timeout set for this test; declared using the @timed()
        decorator.

    In addition, the setUp() and tearDown() methods are available to
    identify special set up and tear down functions or methods to
    override the class-level setUp() and tearDown() methods; these
    methods may be used as decorators, assuming the test has been
    decorated with the @istest decorator.  There is also an istest()
    method, which by default returns False; this is overridden by the
    DTest class to return True.
    """

    _tests = {}

    def __new__(cls, test, key=None):
        """
        Look up or allocate a DTestBase instance wrapping ``test``.
        """

        # If test is None, return None
        if test is None:
            return None

        # If test is a DTestBase subclass, then return it directly
        if isinstance(test, DTestBase):
            return test

        # We have to unwrap MethodType
        if isinstance(test, types.MethodType):
            test = test.__func__

        # Require it to be a callable...
        if (not callable(test) and not isinstance(test, classmethod) and
            not isinstance(test, staticmethod)):
            raise exceptions.DTestException("%r must be a callable" % test)

        # Generate the key, if necessary
        if key is None:
            key = _func_name(test)

        # Make sure we haven't already created one
        if key in DTestBase._tests:
            return DTestBase._tests[key]

        # OK, construct a new one
        dt = super(DTestBase, cls).__new__(cls)
        dt._key = key
        dt._test = test
        dt._class = None
        dt._exp_fail = False
        dt._skip = False
        dt._pre = None
        dt._post = None
        dt._deps = set()
        dt._revdeps = set()
        dt._partner = None
        dt._attrs = {}
        dt._raises = set()
        dt._timeout = None
        dt._result = None

        # Save it in the cache
        DTestBase._tests[key] = dt

        # And return it
        return dt

    def __get__(self, instance, owner):
        """
        Retrieve an instance method wrapping ourself, for use with
        super() and inheritance.
        """

        # If instance is None, just return ourself directly
        if instance is None:
            return self

        # OK, wrap ourself in an instance method
        return types.MethodType(self, instance, owner)

    def __getattr__(self, key):
        """
        Retrieve the attribute with the given ``key``.  Attributes may
        be set using the @attr() decorator.
        """

        # Get the attribute out of the _attrs map
        return self._attrs[key]

    def __setattr__(self, key, value):
        """
        Update the attribute with the given ``key`` to ``value``.
        Attributes may be initially set using the @attr() decorator.
        """

        # Is it an internal attribute?
        if key[0] == '_':
            return super(DTestBase, self).__setattr__(key, value)

        # Store that in the _attrs map
        self._attrs[key] = value

    def __delattr__(self, key):
        """
        Delete the attribute with the given ``key``.  Attributes may
        be initially set using the @attr() decorator.
        """

        # Is it an internal attribute?
        if key[0] == '_':
            return super(DTestBase, self).__delattr__(key)

        # Delete from the _attrs map
        del self._attrs[key]

    def __call__(self, *args, **kwargs):
        """
        Call the test function directly.
        """

        # May have to unwrap the test function
        method = self._test
        if not callable(method):
            method = method.__get__(args[0], args[0].__class__)

            # Consumed first argument...
            args = args[1:]

        # Call it
        return method(*args, **kwargs)

    def __int__(self):
        """
        Returns the value of the instance in an integer context.
        Normally returns 0, but DTest overrides this to return 1.
        This makes counting tests and not test fixtures easy.
        """

        # In an integer context, we're 0; this is how we can count the
        # number of tests
        return 0

    def __hash__(self):
        """
        Returns a hash code for this instance.  This allows instances
        of DTestBase to be stored in a set or used as hash keys.
        """

        # Return the hash of the key
        return hash(self._key)

    def __eq__(self, other):
        """
        Compares two instances of DTestBase for equality.  This allows
        instances of DTestBase to be stored in a set or used as hash
        keys.
        """

        # Compare test objects
        return self._key == other._key

    def __ne__(self, other):
        """
        Compares two instances of DTestBase for inequality.  This is
        for completeness, complementing __eq__().
        """

        # Compare test objects
        return self._key != other._key

    def __str__(self):
        """
        Generates a string representation of the test.  The string
        representation is the fully qualified name of the wrapped
        function or method.
        """

        return self._key

    def __repr__(self):
        """
        Generates a representation of the test.  This augments the
        standard __repr__() output to include the actual test function
        or method wrapped by the DTestBase instance.
        """

        # Generate a representation of the test
        return ('<%s.%s object at %#x wrapping %r>' %
                (self.__class__.__module__, self.__class__.__name__,
                 id(self), self._test))

    @property
    def result(self):
        """
        Retrieve the most recent result of running the test.  This may
        be None if the test has not yet been run.
        """

        # We want the result to be read-only, but to be accessed like
        # an attribute
        return self._result

    @property
    def state(self):
        """
        Retrieve the most recent state of the test.  This may be None
        if the test has not yet been run.
        """

        # We want the state to be read-only, but to be accessed like
        # an attribute; this is a short-cut for reading the state from
        # the result
        return self._result.state if self._result is not None else None

    @property
    def test(self):
        """
        Retrieve the test function or method wrapped by this DTestBase
        instance.
        """

        # We want the test to be read-only, but to be accessed like an
        # attribute
        return self._test

    @property
    def class_(self):
        """
        Retrieve the class in which the test method was defined.  If
        the wrapped test is a bare function, rather than a method,
        this will be None.
        """

        # We want the test's class to be read-only, but to be accessed
        # like an attribute
        return self._class

    @property
    def skip(self):
        """
        Retrieve the ``skip`` setting for the test.  This will be True
        only if the @skip decorator has been used on the test;
        otherwise, it will be False.
        """

        # We want the test's skip setting to be read-only, but to be
        # accessed like an attribute
        return self._skip

    @property
    def failing(self):
        """
        Retrieve the ``failing`` setting for the test.  This will be
        True only if the @failing decorator has been used on the test;
        otherwise, it will be False.
        """

        # We want the test's expected failure setting to be read-only,
        # but to be accessed like an attribute
        return self._exp_fail

    @property
    def dependencies(self):
        """
        Retrieve the set of tests this test is dependent on.  This
        returns a frozenset.
        """

        # We want the dependencies to be read-only, but to be accessed
        # like an attribute
        return frozenset(self._deps)

    @property
    def dependents(self):
        """
        Retrieve the set of tests that are dependent on this test.
        This returns a frozenset.
        """

        # We want the depedents to be read-only, but to be accessed
        # like an attribute
        return frozenset(self._revdeps)

    @property
    def raises(self):
        """
        Retrieve the set of exceptions this test is expected to raise.
        Will be empty unless the @raises() decorator has been used on
        this test.  This returns a frozenset.
        """

        # We want the exceptions to be read-only, but to be accessed
        # like an attribute
        return frozenset(self._raises)

    @property
    def timeout(self):
        """
        Retrieve the timeout for this test.  Will be None unless the
        @timed() decorator has been used on this test.
        """

        # We want the timeout to be read-only, but to be accessed like
        # an attribute
        return self._timeout

    def setUp(self, pre):
        """
        Explicitly set the setUp() function or method to be called
        immediately prior to executing the test.  This can be used as
        a decorator; however, the test in question must have been
        decorated for this method to be available.  If no other
        decorator is appropriate for the test, use the @istest
        decorator.
        """

        # Save the pre-test fixture.  This method can be used as a
        # decorator.
        self._pre = pre
        return pre

    def tearDown(self, post):
        """
        Explicitly set the tearDown() function or method to be called
        immediately after executing the test.  This can be used as a
        decorator; however, the test in question must have been
        decorated for this method to be available.  If no other
        decorator is appropriate for the test, use the @istest
        decorator.
        """

        # Save the post-test fixture.  This method can be used as a
        # decorator.
        self._post = post
        return post

    def istest(self):
        """
        Returns True if the instance is a test or False if the
        instance is a test fixture.  For all instances of DTestBase,
        returns False; the DTest class overrides this method to return
        True.
        """

        # Return True if this is a test
        return False

    def _attach(self, cls):
        """
        Attach a class to the test.  This may re-key the test.
        """

        # Set the class
        self._class = cls

        # Generate the new key and see if it matches...
        newkey = _func_name(self._test, cls)
        if newkey != self._key:
            # We've been rekeyed!  Remove ourself from the cache...
            del self.__class__._tests[self._key]

            # ...from all our dependencies...
            for dep in self._deps:
                dep._revdeps.remove(self)

            # ...and from all our dependents
            for dep in self._revdeps:
                dep._deps.remove(self)

            # Re-key ourself
            self._key = newkey

            # Add back to the cache...
            self.__class__._tests[newkey] = self

            # ...to all our dependencies...
            for dep in self._deps:
                dep._revdeps.add(self)

            # ...and to all our dependents
            for dep in self._revdeps:
                dep._deps.add(self)

    def _run(self, *args, **kwargs):
        """
        Perform the test.  Causes any fixtures discovered as part of
        the class or explicitly set (or overridden) by the setUp() and
        tearDown() methods to be executed before and after the actual
        test, respectively.  Returns the result of the test.  Note
        that the ``_output`` keyword argument is extracted and used to
        call a notify() method; see the run_tests() function for more
        details.
        """

        # Need a helper to unwrap and call class methods and static
        # methods
        def do_call(method, args, kwargs):
            if not callable(method):
                # Have to unwrap it
                method = method.__get__(args[0], args[0].__class__)

                # The first argument is now taken care of
                args = args[1:]

            # Now call it
            return method(*args, **kwargs)

        # Extract the notification
        output = kwargs.get('_output')
        if '_output' in kwargs:
            del kwargs['_output']

        # Transition to the running state
        self._result._transition(RUNNING, output=output)

        # Perform preliminary call
        if self._pre is not None:
            with self._result.accumulate(PRE):
                do_call(self._pre, args, kwargs)

        # Execute the test
        with self._result.accumulate(TEST, self._raises):
            do_call(self._test, args, kwargs)

        # Invoke any clean-up that's necessary (regardless of
        # exceptions)
        if self._post is not None:
            with self._result.accumulate(POST):
                do_call(self._post, args, kwargs)

        # Transition to the appropriate ending state
        self._result._transition(output=output)

        # Return the result
        return self._result

    def _depcheck(self, output):
        """
        Performs a check of all this test's dependencies, to determine
        if the test can be executed.  This is an abstract method that
        is overridden by the DTest and DTestFixture classes to
        implement class-specific behavior.
        """

        # Abstract method; subclasses must define!
        raise Exception("Subclasses must implement _depcheck()")

    def _skipped(self, output):
        """
        Marks this DTestBase instance as having been skipped.  This
        status propagates up and down the dependence graph, in order
        to mark all dependents as skipped and to cause unneeded
        fixtures to also be skipped.
        """

        # Mark that this test has been skipped by transitioning the
        # state
        if self.state is None:
            self._result._transition(SKIPPED, output=output)

            # Propagate up to tests dependent on us
            for dt in self._revdeps:
                dt._skipped(output)

            # Also notify tests we're dependent on
            for dt in self._deps:
                dt._notify_skipped(output)

    def _notify_skipped(self, output):
        """
        Notifies this DTestBase instance that a dependent has been
        skipped.  This is used by DTestFixture to identify when a
        given fixture should be skipped.
        """

        # Regular tests don't care that some test dependent on them
        # has been skipped
        pass

    def _prepare(self):
        """
        Prepares this test for execution by allocating a DTestResult
        instance.
        """

        # Prepares the test for running by setting up a result
        self._result = result.DTestResult(self)


class DTest(DTestBase):
    """
    DTest
    =====

    The DTest class represents individual tests to be executed.  It
    inherits most of its elements from the DTestBase class, but
    overrides the __int__(), _depcheck(), and istest() methods to
    implement test-specific behavior.
    """

    def __int__(self):
        """
        Returns the value of the instance in an integer context.
        Returns 1 to make counting tests and not test fixtures easy.
        """

        # This is a single test, so return 1 so we contribute to the
        # count
        return 1

    def _depcheck(self, output):
        """
        Performs a check of all this test's dependencies, to determine
        if the test can be executed.  Tests can only be executed if
        all their dependencies have passed.
        """

        # All dependencies must be OK
        for dep in self._deps:
            if (dep.state == FAIL or dep.state == ERROR or
                dep.state == XFAIL or dep.state == DEPFAIL):
                # Set our own state to DEPFAIL
                self._result._transition(DEPFAIL, output=output)
                return False
            elif dep.state == SKIPPED:
                # Set our own state to SKIPPED
                self._result._transition(SKIPPED, output=output)
                return False
            elif dep.state != OK and dep.state != UOK:
                # Dependencies haven't finished up, yet
                return False

        # All dependencies satisfied!
        return True

    def istest(self):
        """
        Returns True if the instance is a test or False if the
        instance is a test fixture.  Overrides DTestBase.istest() to
        return True.
        """

        # Return True, since this is a test
        return True


class DTestFixture(DTestBase):
    """
    DTestFixture
    ============

    The DTestFixture class represents test fixtures to be executed.
    It inherits most of its elements from the DTestBase class, but
    overrides the _depcheck(), _skipped(), and _notify_skipped()
    methods to implement test fixture-specific behavior.  In addition,
    provides the _set_partner() method, used for setting test fixture
    partners.
    """

    def _set_partner(self, setUp):
        """
        Sets the partner of a test fixture.  This method is called on
        tear down-type fixtures to pair them with the corresponding
        set up-type fixtures.  This ensures that a tear down fixture
        will not run unless the corresponding set up fixture ran
        successfully.
        """

        # Sanity-check setUp
        if setUp is None:
            return

        # First, set a dependency
        depends(setUp)(self)

        # Now, save our pair partner
        self._partner = setUp

    def _depcheck(self, output):
        """
        Performs a check of all this test fixture's dependencies, to
        determine if the test can be executed.  Test fixtures can only
        be executed if their partner (if one is specified) has passed
        and if all the tests the fixture is dependent on have finished
        running or been skipped.
        """

        # Make sure our partner succeeded
        if self._partner is not None:
            if (self._partner.state == FAIL or
                self._partner.state == XFAIL or
                self._partner.state == ERROR or
                self._partner.state == DEPFAIL):
                # Set our own state to DEPFAIL
                self._result._transition(DEPFAIL, output=output)
                return False
            elif self._partner.state == SKIPPED:
                # Set our own state to SKIPPED
                self._result._transition(SKIPPED, output=output)
                return False

        # Other dependencies must not be un-run or in the RUNNING
        # state
        for dep in self._deps:
            if dep.state is None or dep.state == RUNNING:
                return False

        # Dependencies can have failed, failed due to dependencies,
        # been skipped, or have completed--they just have to be in
        # that state before running the fixture
        return True

    def _skipped(self, output):
        """
        Marks this DTestFixture instance as having been skipped.  Test
        fixtures may only be skipped if *all* their dependencies have
        been skipped.
        """

        # Only bother if all our dependencies are also skipped--tear
        # down fixtures need to run any time the corresponding set up
        # fixtures have run
        for dep in self._deps:
            if dep is not self._partner and dep.state != SKIPPED:
                return

        # Call the superclass method
        super(DTestFixture, self)._skipped(output)

    def _notify_skipped(self, output):
        """
        Notifies this DTestFixture instance that a dependent has been
        skipped.  If all the fixture's dependents have been skipped,
        then the test fixture will also be skipped.
        """

        # If all tests dependent on us have been skipped, we don't
        # need to run
        for dep in self._revdeps:
            if dep.state != SKIPPED:
                return

        # Call the superclass's _skipped() method
        super(DTestFixture, self)._skipped(output)


def istest(func):
    """
    Decorates a function to indicate that the function is a test.  Can
    be used if the @func.setUp or @func.tearDown decorators need to be
    used, or if the test would not be picked up by the test discovery
    regular expression.
    """

    # Wrap func in a test
    return DTest(func)


def nottest(func):
    """
    Decorates a function to indicate that the function is not a test.
    Can be used if the test would be picked up by the test discovery
    regular expression but should not be.  Works by setting the
    ``_dt_nottest`` attribute on the function to True.
    """

    # Mark that a function should not be considered a test
    func._dt_nottest = True
    return func


def skip(func):
    """
    Decorates a test to indicate that the test should be skipped.
    """

    # Get the DTest object for the test
    dt = DTest(func)

    # Set up to skip it
    dt._skip = True

    # Return the test
    return dt


def failing(func):
    """
    Decorates a test to indicate that the test is expected to fail.
    """

    # Get the DTest object for the test
    dt = DTest(func)

    # Set up to expect it to fail
    dt._exp_fail = True

    # Return the test
    return dt


def attr(**kwargs):
    """
    Decorates a test to set attributes on the test.  Keyword arguments
    are converted to attributes on the test.  Note that all attributes
    beginning with underscore ("_") and the following list of
    attributes are reserved: ``result``, ``state``, ``test``,
    ``class_``, ``skip``, ``failing``, ``dependencies``,
    ``dependents``, ``raises``, ``timeout``, ``setUp``, ``tearDown``,
    and ``istest``.
    """

    # Need a wrapper to perform the actual decoration
    def wrapper(func):
        # Get the DTest object for the test
        dt = DTest(func)

        # Update the attributes
        dt._attrs.update(kwargs)

        # Return the test
        return dt

    # Return the actual decorator
    return wrapper


def depends(*deps):
    """
    Decorates a test to indicate other tests the test depends on.
    There is no need to explicitly specify test fixtures.  Take care
    to not introduce dependency cycles.  Note that this decorator
    takes references to the dependencies, and cannot handle dependency
    names.
    """

    # Get the DTest objects for the dependencies
    deps = [DTest(dep) for dep in deps]

    # Need a wrapper to perform the actual decoration
    def wrapper(func):
        # Get the DTest object for the test
        dt = DTest(func)

        # Add the dependencies
        dt._deps |= set(deps)

        # Add the reverse dependencies
        for dep in deps:
            dep._revdeps.add(dt)

        # Return the test
        return dt

    # Return the actual decorator
    return wrapper


def raises(*exc_types):
    """
    Decorates a test to indicate that the test may raise an exception.
    The valid exceptions are specified to the decorator as references.
    The list may include None, in which case the test not raising an
    exception is permissible.
    """

    # Need a wrapper to perform the actual decoration
    def wrapper(func):
        # Get the DTest object for the test
        dt = DTest(func)

        # Store the recognized exception types
        dt._raises |= set(exc_types)

        # Return the test
        return dt

    # Return the actual decorator
    return wrapper


def timed(timeout):
    """
    Decorates a test to indicate that the test must take less than
    ``timeout`` seconds (floats permissible).  If the test takes more
    than that amount of time, the test will fail.  Note that this uses
    the Eventlet timeout mechanism, which depends on the test
    cooperatively yielding; if the test exclusively performs
    computation without sleeping or performing I/O, this timeout may
    not trigger.
    """

    # Need a wrapper to perform the actual decoration
    def wrapper(func):
        # Get the DTest object for the test
        dt = DTest(func)

        # Store the timeout value (in seconds)
        dt._timeout = timeout

        # Return the test
        return dt

    # Return the actual decorator
    return wrapper


def _mod_fixtures(modname):
    """
    Helper function which searches a module's name heirarchy, based on
    the textual ``modname``, to find all test fixtures that apply to
    tests in that module.  Returns a tuple, where the first element is
    a list of set up fixtures and the second element is a list of tear
    down fixtures.
    """

    # Split up the module name
    mods = modname.split('.')

    # Now, walk up the tree
    setUps = []
    tearDowns = []
    for i in range(len(mods)):
        module = sys.modules['.'.join(mods[:i + 1])]

        # Make sure the module's been visited...
        visit_mod(module)

        # Does the module have the fixture?
        setUp = None
        if hasattr(module, SETUP):
            module.setUp = DTestFixture(module.setUp)
            setUps.append(module.setUp)
            setUp = module.setUp
        if hasattr(module, TEARDOWN):
            module.tearDown = DTestFixture(module.tearDown)
            tearDowns.append(module.tearDown)

            # Set the partner
            module.tearDown._set_partner(setUp)

    # Next, set up dependencies; each setUp() is dependent on all the
    # ones before it...
    for i in range(1, len(setUps)):
        depends(setUps[i - 1])(setUps[i])

    # While each tearDown() is dependent on all the ones after it...
    for i in range(len(tearDowns) - 1):
        depends(tearDowns[i + 1])(tearDowns[i])

    # Return the setUps and tearDowns
    return (setUps, tearDowns)


testRE = re.compile(r'(?:^|[\b_\.-])[Tt]est')


def visit_mod(mod):
    """
    Helper function which searches a module object, specified by
    ``mod``, for all tests and wraps discovered test fixtures in
    instances of DTestFixture.  Also sets up proper dependency
    information.  Called by _mod_fixtures().
    """

    # Have we visited the module before?
    if hasattr(mod, '_dt_visited') and mod._dt_visited:
        return

    # Mark that we're visiting the module
    mod._dt_visited = True

    # Check for package- and module-level fixtures
    setUps, tearDowns = _mod_fixtures(mod.__name__)

    # Search the module for tests
    updates = {}
    for k in dir(mod):
        # Skip internal functions
        if k[0] == '_':
            continue

        v = getattr(mod, k)

        # Skip non-callables
        if (not isinstance(v, types.FunctionType) and
            not isinstance(v, DTestBase)):
            continue

        # If it has the _dt_nottest attribute set to True, skip it
        if hasattr(v, '_dt_nottest') and v._dt_nottest:
            continue

        # If it's one of the test fixtures, skip it
        if k in (SETUP, TEARDOWN):
            continue

        # Does it match the test RE?
        if not isinstance(v, DTestBase) and not testRE.match(k):
            continue

        # Is it already a test?
        if not isinstance(v, DTestBase):
            # Convert it
            v = DTest(v)

            # Store an update for it
            updates[k] = v

        # Attach fixtures as appropriate...
        if setUps:
            depends(setUps[-1])(v)
        if tearDowns:
            depends(v)(tearDowns[-1])

    # Update the module
    for k, v in updates.items():
        setattr(mod, k, v)


class DTestCaseMeta(type):
    """
    DTestCaseMeta
    =============

    The DTestCaseMeta is a metaclass for DTestCase.  Before
    constructing the class, discovers all tests and related test
    fixtures (including module- and package-level fixtures) and sets
    up dependencies as appropriate.  Also ensures that the ``class_``
    attribute of tests and test fixtures is set appropriately.
    """

    def __new__(mcs, name, bases, dict_):
        """
        Constructs a new class with the given ``name``, ``bases``, and
        ``dict_``.  The ``dict_`` is searched for all tests and
        class-level test fixtures, and the module- and package-level
        test fixtures are attached using dependencies.
        """

        # Look up any test fixtures for the individual tests...
        setUp = dict_.get(SETUP, None)
        tearDown = dict_.get(TEARDOWN, None)

        # May also have to search our bases
        if setUp is None:
            for cls in bases:
                if hasattr(cls, SETUP):
                    setUp = getattr(cls, SETUP)

                    # Make sure it's a callable
                    if not callable(setUp):
                        setUp = None
                    break
        if tearDown is None:
            for cls in bases:
                if hasattr(cls, TEARDOWN):
                    tearDown = getattr(cls, TEARDOWN)

                    # Make sure it's a callable
                    if not callable(tearDown):
                        tearDown = None
                    break

        # Check for package- and module-level fixtures
        setUps, tearDowns = _mod_fixtures(dict_['__module__'])

        # Updates to the dict_ to apply later
        updates = {}

        # Check for class-level set up
        setUpClass = None
        if (SETUP + CLASS) in dict_:
            setUpClass = DTestFixture(dict_[SETUP + CLASS],
                                      _func_name(dict_[SETUP + CLASS], name))
            updates[SETUP + CLASS] = setUpClass
        else:
            for cls in bases:
                # If it has a setUpClass, use it
                if hasattr(cls, SETUP + CLASS):
                    setUpClass = getattr(cls, SETUP + CLASS)

                    # If it's a DTestBase, unwrap it
                    if isinstance(setUpClass, DTestBase):
                        setUpClass = setUpClass._test
                    elif (not callable(setUpClass) and
                          not isinstance(setUpClass, types.MethodType) and
                          not isinstance(setUpClass, classmethod) and
                          not isinstance(setUpClass, staticmethod)):
                        # Don't use it
                        setUpClass = None
                        break

                    # OK, we have to wrap it in a DTestFixture
                    setUpClass = DTestFixture(setUpClass,
                                              _func_name(setUpClass, name))
                    updates[SETUP + CLASS] = setUpClass
                    break

        # Set up dependencies
        if setUpClass is not None:
            if setUps:
                depends(setUps[-1])(setUpClass)
            setUps.append(setUpClass)

        # Check for class-level tear down
        tearDownClass = None
        if (TEARDOWN + CLASS) in dict_:
            tearDownClass = DTestFixture(dict_[TEARDOWN + CLASS],
                                         _func_name(dict_[TEARDOWN + CLASS],
                                                    name))
            updates[TEARDOWN + CLASS] = tearDownClass
        else:
            for cls in bases:
                # If it has a tearDownClass, use it
                if hasattr(cls, TEARDOWN + CLASS):
                    tearDownClass = getattr(cls, TEARDOWN + CLASS)

                    # If it's a DTestBase, unwrap it
                    if isinstance(tearDownClass, DTestBase):
                        tearDownClass = tearDownClass._test
                    elif (not callable(tearDownClass) and
                          not isinstance(tearDownClass, types.MethodType) and
                          not isinstance(tearDownClass, classmethod) and
                          not isinstance(tearDownClass, staticmethod)):
                        # Don't use it
                        tearDownClass = None
                        break

                    # OK, we have to wrap it in a DTestFixture
                    tearDownClass = DTestFixture(tearDownClass,
                                                 _func_name(tearDownClass,
                                                            name))
                    updates[TEARDOWN + CLASS] = tearDownClass
                    break

        # Set up dependencies
        if tearDownClass is not None:
            if tearDowns:
                depends(tearDownClass)(tearDowns[-1])
            tearDownClass._set_partner(setUpClass)
            tearDowns.append(tearDownClass)

        # Now, we want to walk through dict_ and replace values that
        # match the test RE with instances of DTest
        tests = []
        for k, v in dict_.items():
            # If it has the _dt_nottest attribute set to True, skip it
            if k[0] == '_' or (hasattr(v, '_dt_nottest') and v._dt_nottest):
                continue

            # If it's one of the test fixtures, skip it
            if k in (SETUP, TEARDOWN, SETUP + CLASS, TEARDOWN + CLASS):
                continue

            # Does it match the test RE?
            if not isinstance(v, DTestBase) and not testRE.match(k):
                continue

            # Is it already a test?
            if not isinstance(v, DTestBase):
                # Convert it
                v = DTest(v)

                # Store an update for it
                updates[k] = v

            # Remember test for attaching class later
            tests.append(v)

            # Attach fixtures as appropriate...
            if v._pre is None and setUp is not None:
                v.setUp(setUp)
            if v._post is None and tearDown is not None:
                v.tearDown(tearDown)

            # Do package-, module-, and class-level fixtures as well
            if setUps:
                depends(setUps[-1])(v)
            if tearDowns:
                depends(v)(tearDowns[-1])

        # Update the dict_
        dict_.update(updates)

        # Now that we've done the set-up, create the class
        cls = super(DTestCaseMeta, mcs).__new__(mcs, name, bases, dict_)

        # Attach cls to all the tests
        for t in tests:
            t._attach(cls)

        # Attach cls to in-class fixtures
        if setUpClass is not None:
            setUpClass._attach(cls)
        if tearDownClass is not None:
            tearDownClass._attach(cls)

        # Return the constructed class
        return cls


class DTestCase(object):
    """
    DTestCase
    =========

    The DTestCase class is a base class for classes of test methods.
    It is constructed using the DTestCaseMeta metaclass.  Any classes
    which contain tests must inherit from DTestCase or must use
    DTestCaseMeta as a metaclass.
    """

    __metaclass__ = DTestCaseMeta


def list_tests(fixtures=False):
    """
    Retrieve the list of all tests (and, if ``fixtures`` is True, test
    fixtures) that have been discovered and registered by the
    framework.
    """

    # Save ourselves some work...
    if fixtures:
        return DTestBase._tests.values()

    # OK, filter out the fixtures
    return [dt for dt in DTestBase._tests.values() if dt.istest()]


def dot(grname='testdeps'):
    """
    Constructs a GraphViz-compatible dependency graph with the given
    name (``testdeps``, by default).  Returns the graph as a string.
    The graph can be fed to the ``dot`` tool to generate a
    visualization of the dependency graph.  Note that red nodes in the
    graph indicate test fixtures, and red dashed edges indicate
    dependencies associated with test fixtures.  If the node outline
    is dotted, that indicates that the test was skipped in the most
    recent test run.
    """

    # Helper to generate node and edge options
    def mkopts(opts):
        # If there are no options, return an empty string
        if not opts:
            return ''

        # OK, let's do this...
        return ' [' + ','.join(['%s="%s"' % (k, opts[k])
                                for k in opts]) + ']'

    # Now, create the graph
    nodes = []
    edges = []
    for dt in DTestBase._tests.values():
        # If it's not a callable, must be class or static method;
        # get the real test
        test = dt._test if callable(dt._test) else dt._test.__func__

        # Make the node
        opts = dict(label=r'%s\n%s:%d' %
                    (dt, test.func_code.co_filename,
                     test.func_code.co_firstlineno))
        if dt.state:
            opts['label'] += r'\n(Result: %s)' % dt.state
        if (dt.state == FAIL or dt.state == XFAIL or dt.state == ERROR or
            dt.state == DEPFAIL):
            opts['color'] = 'red'
        elif isinstance(dt, DTestFixture):
            opts['color'] = 'blue'
        if dt.state == SKIPPED:
            opts['style'] = 'dotted'
        elif dt.state == DEPFAIL:
            opts['style'] = 'dashed'
        nodes.append('"%s"%s;' % (dt, mkopts(opts)))

        # Make all the edges
        for dep in dt._deps:
            opts = {}
            if (isinstance(dt, DTestFixture) or
                isinstance(dep, DTestFixture)):
                opts.update(dict(color='blue', style='dashed'))
            if dt._partner is not None and dep == dt._partner:
                opts['style'] = 'dotted'

            edges.append('"%s" -> "%s"%s;' % (dt, dep, mkopts(opts)))

    # Return a graph
    return (('strict digraph "%s" {\n\t' % grname) +
            '\n\t'.join(nodes) + '\n\n\t' + '\n\t'.join(edges) + '\n}')
