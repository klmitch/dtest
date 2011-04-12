# Copyright 2011 OpenStack LLC.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

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

    def __init__(self, test):
        """
        Initialize a DTestBase instance wrapping ``test``.
        """

        # The test cannot be None
        if test is None:
            raise exceptions.DTestException("None is an invalid test")

        # We have to unwrap MethodType and class and static methods
        if (isinstance(test, types.MethodType) or
            isinstance(test, classmethod) or isinstance(test, staticmethod)):
            test = test.__func__

        # Require it to be a callable...
        if not callable(test):
            raise exceptions.DTestException("%r must be a callable" % test)

        # Initialize ourself
        self._name = None
        self._test = test
        self._class = None
        self._exp_fail = False
        self._skip = False
        self._pre = None
        self._post = None
        self._deps = set()
        self._revdeps = set()
        self._partner = None
        self._attrs = {}
        self._raises = set()
        self._timeout = None
        self._result = None

        # Attach ourself to the test
        test._dt_dtest = self
        test.setUp = self.setUp
        test.tearDown = self.tearDown

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
        return hash(id(self))

    def __eq__(self, other):
        """
        Compares two instances of DTestBase for equality.  This allows
        instances of DTestBase to be stored in a set or used as hash
        keys.
        """

        # Compare test objects
        return self is other

    def __ne__(self, other):
        """
        Compares two instances of DTestBase for inequality.  This is
        for completeness, complementing __eq__().
        """

        # Compare test objects
        return self is not other

    def __str__(self):
        """
        Generates a string representation of the test.  The string
        representation is the fully qualified name of the wrapped
        function or method.
        """

        # If our name has not been generated, do so...
        if self._name is None:
            if self._class is None:
                # No class is involved
                self._name = '.'.join([self._test.__module__,
                                       self._test.__name__])
            else:
                # Have to include the class name
                self._name = '.'.join([self._test.__module__,
                                       self._class.__name__,
                                       self._test.__name__])

        # Return the name
        return self._name

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

        # If a class is already associated, do nothing
        if self._class is not None:
            return

        # Set the class
        self._class = cls

        # Re-set our name
        self._name = None

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
        def do_call(method, obj, args, kwargs):
            # If obj is not None, extract the method with getattr(),
            # so we use the right calling convention
            if obj is not None:
                method = getattr(obj, method.__name__)

            # Now call it
            return method(*args, **kwargs)

        # Extract the notification
        output = kwargs.get('_output')
        if '_output' in kwargs:
            del kwargs['_output']

        # Transition to the running state
        self._result._transition(RUNNING, output=output)

        # Set up an object for the call, if necessary
        obj = None
        if self._class is not None:
            obj = self._class()

        # Perform preliminary call
        if self._pre is not None:
            with self._result.accumulate(PRE):
                do_call(self._pre, obj, args, kwargs)

        # Execute the test
        with self._result.accumulate(TEST, self._raises):
            do_call(self._test, obj, args, kwargs)

        # Invoke any clean-up that's necessary (regardless of
        # exceptions)
        if self._post is not None:
            with self._result.accumulate(POST):
                do_call(self._post, obj, args, kwargs)

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


def _gettest(func, testcls=DTest):
    """
    Retrieves a DTest from--or, if ``testcls`` is not None, attaches a
    new test of that class to--``func``.  This is a helper function
    used by the decorators below.
    """

    # We could be passed a DTest, so return it if so
    if isinstance(func, DTestBase):
        return func

    # Always return None if _dt_nottest is set
    if func is None or (hasattr(func, '_dt_nottest') and func._dt_nottest):
        return None

    # Look up the test as a function attribute
    try:
        return func._dt_dtest
    except AttributeError:
        # Don't want to create one, I guess
        if testcls is None:
            return None

        # Not yet declared, so let's go ahead and attach one
        dt = testcls(func)

        # Return the test
        return dt


def istest(func):
    """
    Decorates a function to indicate that the function is a test.  Can
    be used if the @func.setUp or @func.tearDown decorators need to be
    used, or if the test would not be picked up by the test discovery
    regular expression.
    """

    # Make sure func has a DTest associated with it
    _gettest(func)

    # Return the function
    return func


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
    dt = _gettest(func)

    # Set up to skip it
    dt._skip = True

    # Return the function
    return func


def failing(func):
    """
    Decorates a test to indicate that the test is expected to fail.
    """

    # Get the DTest object for the test
    dt = _gettest(func)

    # Set up to expect it to fail
    dt._exp_fail = True

    # Return the function
    return func


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
        dt = _gettest(func)

        # Update the attributes
        dt._attrs.update(kwargs)

        # Return the function
        return func

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
    deps = [_gettest(dep) for dep in deps]

    # Need a wrapper to perform the actual decoration
    def wrapper(func):
        # Get the DTest object for the test
        dt = _gettest(func)

        # Add the dependencies
        dt._deps |= set(deps)

        # Add the reverse dependencies
        for dep in deps:
            dep._revdeps.add(dt)

        # Return the function
        return func

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
        dt = _gettest(func)

        # Store the recognized exception types
        dt._raises |= set(exc_types)

        # Return the function
        return func

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
        dt = _gettest(func)

        # Store the timeout value (in seconds)
        dt._timeout = timeout

        # Return the function
        return func

    # Return the actual decorator
    return wrapper


testRE = re.compile(r'(?:^|[\b_\.-])[Tt]est')


def visit_mod(mod, tests):
    """
    Helper function which searches a module object, specified by
    ``mod``, for all tests, test classes, and test fixtures, then sets
    up proper dependency information.  All discovered tests are added
    to the set specified by ``tests``.  Returns a tuple containing the
    closest discovered test fixtures (needed because visit_mod() is
    recursive).
    """

    # Have we visited this module before?
    if hasattr(mod, '_dt_visited'):
        # We cache the tests in this module (and parent modules) in
        # _dt_visited
        tests |= mod._dt_visited
        return mod._dt_setUp, mod._dt_tearDown

    # OK, set up the visited cache
    mod._dt_visited = set()

    # If we have a parent package...
    setUp = None
    tearDown = None
    if '.' in mod.__name__:
        pkgname, modname = mod.__name__.rsplit('.', 1)

        # Visit up one level
        setUp, tearDown = visit_mod(sys.modules[pkgname], mod._dt_visited)

    # See if we have fixtures in this module
    setUpLocal = None
    if hasattr(mod, SETUP):
        setUpLocal = _gettest(getattr(mod, SETUP), DTestFixture)

        # Set up the dependency
        if setUp is not None:
            depends(setUp)(setUpLocal)

        setUp = setUpLocal
    if hasattr(mod, TEARDOWN):
        tearDownLocal = _gettest(getattr(mod, TEARDOWN), DTestFixture)

        # Set up the dependency
        if tearDown is not None:
            depends(tearDownLocal)(tearDown)

        # Also set up the partner dependency
        if setUpLocal is not None:
            tearDownLocal._set_partner(setUpLocal)

        tearDown = tearDownLocal

    # OK, we now have the test fixtures; let's cache them
    mod._dt_setUp = setUp
    mod._dt_tearDown = tearDown

    # Also add them to the set of discovered tests
    if setUp is not None:
        mod._dt_visited.add(setUp)
    if tearDown is not None:
        mod._dt_visited.add(tearDown)

    # Now, let's scan all the module attributes and set them up as
    # tests with appropriate dependencies...
    for k in dir(mod):
        # Skip internal attributes and the fixtures
        if k[0] == '_' or k == SETUP or k == TEARDOWN:
            continue

        # Get the value
        v = getattr(mod, k)

        # Skip non-callables
        if not callable(v):
            continue

        # Is it explicitly not a test?
        if hasattr(v, '_dt_nottest') and v._dt_nottest:
            continue

        # If it's a DTestCase, handle it specially
        try:
            if issubclass(v, DTestCase):
                # Set up dependencies
                if setUp is not None:
                    if hasattr(v, SETUP + CLASS):
                        # That's easy...
                        depends(setUp)(getattr(v, SETUP + CLASS))
                    else:
                        # Set up a dependency for each test
                        for t in v._dt_tests:
                            depends(setUp)(t)
                if tearDown is not None:
                    if hasattr(v, TEARDOWN + CLASS):
                        # That's easy...
                        depends(getattr(v, TEARDOWN + CLASS))(tearDown)
                    else:
                        # Set up a dependency for each test
                        for t in v._dt_tests:
                            depends(t)(tearDown)

                # Add all the tests
                mod._dt_visited |= v._dt_tests

            # Well, it's probably a class, so ignore it
            continue
        except TypeError:
            # Guess it's not a class...
            pass

        # OK, let's try to get the test
        dt = _gettest(v, DTest if testRE.match(k) else None)
        if dt is None:
            # Not a test
            continue

        # Keep track of tests in this module
        mod._dt_visited.add(dt)

        # Set up the dependencies on setUp and tearDown
        if setUp is not None:
            depends(setUp)(dt)
        if tearDown is not None:
            depends(dt)(tearDown)

    # Set up the list of tests
    tests |= mod._dt_visited

    # OK, let's return the fixtures for recursive calls
    return setUp, tearDown


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
        class-level test fixtures.
        """

        # We want to discover all tests, both here and in bases.  The
        # easiest way of doing this is to begin by constructing the
        # class...
        cls = super(DTestCaseMeta, mcs).__new__(mcs, name, bases, dict_)

        # Look for the fixtures
        setUp = getattr(cls, SETUP, None)
        tearDown = getattr(cls, TEARDOWN, None)
        setUpClass = _gettest(getattr(cls, SETUP + CLASS, None),
                              DTestFixture)
        tearDownClass = _gettest(getattr(cls, TEARDOWN + CLASS, None),
                                 DTestFixture)

        # Attach the class to the fixtures
        if setUpClass is not None:
            setUpClass._attach(cls)
        if tearDownClass is not None:
            tearDownClass._attach(cls)

        # Also set up the dependency between setUpClass and
        # tearDownClass
        if setUpClass is not None and tearDownClass is not None:
            tearDownClass._set_partner(setUpClass)

        # Now, let's scan all the class attributes and set them up as
        # tests with appropriate dependencies...
        tests = []
        for k in dir(cls):
            # Skip internal attributes and the fixtures
            if (k[0] == '_' or k == SETUP or k == TEARDOWN or
                k == SETUP + CLASS or k == TEARDOWN + CLASS):
                continue

            # Get the value
            v = getattr(cls, k)

            # Skip non-callables
            if not callable(v):
                continue

            # Is it explicitly not a test?
            if hasattr(v, '_dt_nottest') and v._dt_nottest:
                continue

            # OK, let's try to get the test
            dt = _gettest(v, DTest if testRE.match(k) else None)
            if dt is None:
                # Not a test
                continue

            # Attach the class to the test
            dt._attach(cls)

            # Keep a list of the tests in this class
            tests.append(dt)

            # We now have a test; let's attach fixtures as
            # appropriate...
            if dt._pre is None and setUp is not None:
                dt.setUp(setUp)
            if dt._post is None and tearDown is not None:
                dt.tearDown(tearDown)

            # Also set up the dependencies on setUpClass and
            # tearDownClass
            if setUpClass is not None:
                depends(setUpClass)(dt)
            if tearDownClass is not None:
                depends(dt)(tearDownClass)

        # Save the list of tests
        cls._dt_tests = set(tests)

        # Also need to list the fixtures
        if setUpClass is not None:
            cls._dt_tests.add(setUpClass)
        if tearDownClass is not None:
            cls._dt_tests.add(tearDownClass)

        # OK, let's return the constructed class
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


def dot(tests, grname='testdeps'):
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
    for dt in tests:
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
