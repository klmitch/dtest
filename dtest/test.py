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

import inspect
import re
import sys
import types

from dtest.constants import *
from dtest import exceptions
from dtest import policy as pol
from dtest import result
from dtest import strategy as strat


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

    # Keep a list of the recognized attributes for the promote()
    # classmethod
    _class_attributes = [
        '_name', '_test', '_class', '_exp_fail', '_skip', '_pre', '_post',
        '_deps', '_revdeps', '_partner', '_attrs', '_raises', '_timeout',
        '_result', '_repeat', '_strategy', '_policy', '_resources'
        ]

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
            try:
                test = test.__func__
            except AttributeError:
                # Python 2.6 doesn't have __func__ attribute on
                # classmethod or staticmethod, so let's kludge around
                # it...
                tmp = test.__get__(None, object)

                # If it's an instance of staticmethod, tmp is func
                if isinstance(test, staticmethod):
                    test = tmp

                # If it's an instance of classmethod, tmp has __func__
                else:
                    test = tmp.__func__

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
        self._repeat = 1
        self._strategy = strat.SerialStrategy()
        self._policy = pol.basicPolicy
        self._resources = {}

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
        try:
            return self._attrs[key]
        except KeyError:
            raise AttributeError(key)

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

    @property
    def repeat(self):
        """
        Retrieve the repeat count for this test.  Will be 1 unless the
        @repeat() decorator has been used on this test.
        """

        # We want the repeat count to be read-only, but to be accessed
        # like an attribute
        return self._repeat

    @classmethod
    def promote(cls, test):
        """
        Promotes a DTestBase instance from one class to another.
        """

        # If test is None, return None
        if test is None:
            return None

        # If it's already the same class, return it
        if test.__class__ == cls:
            return test

        # First, allocate a new instance
        newtest = object.__new__(cls)

        # Now, initialize it from test
        for attr in cls._class_attributes:
            setattr(newtest, attr, getattr(test, attr))

        # Walk through all dependencies/dependents and replace the
        # test
        for dep in newtest._deps:
            dep._revdeps.remove(test)
            dep._revdeps.add(newtest)
        for dep in newtest._revdeps:
            dep._deps.remove(test)
            dep._deps.add(newtest)

        # Replace the bindings in the test
        newtest._test._dt_dtest = newtest
        newtest._test.setUp = newtest.setUp
        newtest._test.tearDown = newtest.tearDown

        # Return the new test
        return newtest

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

    def _run(self, output, res_mgr):
        """
        Perform the test.  Causes any fixtures discovered as part of
        the class or explicitly set (or overridden) by the setUp() and
        tearDown() methods to be executed before and after the actual
        test, respectively.  Returns the result of the test.
        """

        # Need a helper to unwrap and call class methods and static
        # methods
        def get_call(method, obj):
            # If obj is not None, extract the method with getattr(),
            # so we use the right calling convention
            if obj is not None:
                method = getattr(obj, method.__name__)

            # Now call it
            return method

        # Transition to the running state
        self._result._transition(RUNNING, output=output)

        # Set up an object for the call, if necessary
        obj = None
        if self._class is not None:
            obj = self._class()

        # Perform preliminary call
        pre_status = True
        if self._pre is not None:
            with self._result.accumulate(PRE):
                get_call(self._pre, obj)()
            if not self._result:
                pre_status = False

        # Get the test resources...
        resgen = None
        if pre_status:
            with self._result.accumulate(PRE):
                resgen = res_mgr.collect(self._resources)
                resources = resgen.next()
            if not self._result:
                pre_status = False

        # Execute the test
        if pre_status:
            # Prepare the strategy...
            self._strategy.prepare()

            # Trigger the test
            self._trigger(self._test.__name__,
                          get_call(self._test, obj), (), resources)

            # Wait for spawned threads
            self._strategy.wait()

        # Invoke any clean-up that's necessary (regardless of
        # exceptions)
        if pre_status and self._post is not None:
            with self._result.accumulate(POST):
                get_call(self._post, obj)()

        # Transition to the appropriate ending state
        self._result._transition(output=output)

        # Clean up the resources
        if resgen:
            try:
                # We don't allow this to fail; failures in tearDown()
                # methods are pooled together and printed after all
                # the test failures
                resgen.send(str(self.result))
            except StopIteration:
                pass

        # Return the result
        return self._result

    def _parse_item(self, name, item):
        """
        Parses the tuple ``item`` returned by a generator "test".
        Returns a 4-element tuple consisting of the name, the
        callable, the positional arguments, and the keyword arguments.
        Note that ``item`` may also be a bare callable.
        """

        if callable(item):
            # It's a bare callable; make up name, arg, and kwargs
            return ("%s:%s" % (name, item.__name__), item, (), {})
        else:
            # Convert item into a list so we can mutate it
            try:
                item = list(item)
            except TypeError:
                # Hmmm...
                raise exceptions.DTestException("Generator result is not "
                                                "a sequence")

            # Make sure we have elements in the list
            if len(item) < 1:
                raise exceptions.DTestException("Generator result is an "
                                                "empty list")

            # Do we have a name?
            n = None
            if isinstance(item[0], basestring):
                n = item.pop(0)

            # Make sure we still have elements in the list
            if len(item) < 1:
                raise exceptions.DTestException("Generator result has no "
                                                "callable")

            # Get the callable
            c = item.pop(0)

            # Bail out if it's not actually callable
            if not callable(c):
                raise exceptions.DTestException("Generator result callable "
                                                "element is not callable")

            # Ensure we have a name
            if n is None:
                n = "%s:%s" % (name, c.__name__)

            # Now we need to look for arguments
            if len(item) < 1:
                a = ()
                k = {}
            elif len(item) >= 2:
                a, k = item[:2]
            else:
                tmp = item[0]

                # Is it a dictionary?
                if isinstance(tmp, dict):
                    a = ()
                    k = tmp
                else:
                    a = tmp
                    k = {}

        # Return the computed tuple
        return (n, c, a, k)

    def _trigger(self, name, call, args, kwargs):
        """
        Handles making a single call.  If the callable ``call`` is a
        generator function, it will be iterated over and each result
        sent recursively to _trigger.  Otherwise, the call will be
        repeated the number of times requested by @repeat().

        Generator functions may return a tuple consisting of an
        optional name (which must be a string), a callable (which may
        be another generator), a sequence of function arguments, and a
        dictionary of function keyword arguments.  Any element except
        the callable may be omitted.  Generators may also return a
        bare callable.
        """

        # First, check if this is a generator function
        if inspect.isgeneratorfunction(call):
            # Allocate and use a context for the generator itself
            with self._result.accumulate(TEST, id=name):
                # OK, we need to iterate over the result
                for item in call(*args, **kwargs):
                    # Make the recursive call
                    self._trigger(*self._parse_item(name, item))

            # Fully handled the generator function
            return

        # OK, it's a regular test function; let's allocate a result
        # context for it
        for i in range(self._repeat):
            # Allocate a context
            ctx = self._result.accumulate(TEST, self._raises, name)

            # Now, let's fire off the test
            self._strategy.spawn(self._fire, ctx, call, args, kwargs)

    def _fire(self, ctx, call, args, kwargs):
        """
        Performs the actual test function.  This is in a separate
        method so that it can be spawned as appropriate.
        """

        with ctx:
            call(*args, **kwargs)

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

        # Select the correct result container
        if self._repeat > 1 or inspect.isgeneratorfunction(self._test):
            # Will have multiple results
            self._result = result.DTestResultMulti(self)
        else:
            # Just one result; use the simpler machinery
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


class DTestFixtureSetUp(DTestFixture):
    """
    DTestFixtureSetUp
    =================

    The DTestFixtureSetUp class represents setUp() and setUpClass()
    test fixtures to be executed before enclosed tests.  It is derived
    from DTestFixture.
    """

    pass


class DTestFixtureTearDown(DTestFixture):
    """
    DTestFixtureTearDown
    ====================

    The DTestFixtureTearDown class represents tearDown() and
    tearDownClass() test fixtures to be executed after enclosed tests.
    It is derived from DTestFixture, but overrides the _depcheck()
    method to ensure that tearDown() and tearDownClass() are always
    called even if some of the dependencies have failed (unless the
    corresponding setUp() or setUpClass() fixtures have failed).
    """

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


def _gettest(func, testcls=DTest, promote=False):
    """
    Retrieves a DTest from--or, if ``testcls`` is not None, attaches a
    new test of that class to--``func``.  This is a helper function
    used by the decorators below.
    """

    # We could be passed a DTest, so return it if so
    if isinstance(func, DTestBase):
        return testcls.promote(func) if promote else func

    # If it's a class method or static method, unwrap it
    if isinstance(func, (classmethod, staticmethod)):
        try:
            func = func.__func__
        except AttributeError:
            # Python 2.6 doesn't have __func__ attribute on
            # classmethod or staticmethod, so let's kludge around
            # it...
            tmp = func.__get__(None, object)

            # If it's an instance of staticmethod, tmp is func
            if isinstance(func, staticmethod):
                func = tmp

            # If it's an instance of classmethod, tmp has __func__
            else:
                func = tmp.__func__

    # Always return None if _dt_nottest is set
    if func is None or (hasattr(func, '_dt_nottest') and func._dt_nottest):
        return None

    # Look up the test as a function attribute
    try:
        return testcls.promote(func._dt_dtest) if promote else func._dt_dtest
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


def isfixture(func):
    """
    Decorates a function to indicate that the function is a test
    fixture, i.e., package- or module-level setUp()/tearDown() or
    class-level setUpClass()/tearDownClass().

    This decorator is now deprecated.
    """

    # Return the function
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


def repeat(count):
    """
    Decorates a test to indicate that the test must be repeated
    ``count`` number of times.
    """

    # Need a wrapper to perform the actual decoration
    def wrapper(func):
        # Get the DTest object for the test
        dt = _gettest(func)

        # Store the repeat count
        dt._repeat = count

        # Return the function
        return func

    # Return the actual decorator
    return wrapper


def strategy(st, func=None):
    """
    Used to set the parallelization strategy for tests to ``st``.  If
    ``func`` is provided, the parallelization strategy for ``func`` is
    set; otherwise, returns a function which can be used as a
    decorator.  This behavior on the presence of ``func`` allows
    strategy() to be used to create user-defined parallelization
    strategy decorators.

    Parallelization strategies allow tests that are defined as
    generators or which are decorated with the @repeat() decorator to
    execute in parallel threads.  A parallelization strategy is an
    object defining prepare(), spawn(), and wait() methods, which will
    be called in that order.  The prepare() method is passed no
    arguments and simply prepares the strategy object for a sequence
    of spawn() calls.  The spawn() method is called with a callable
    and the arguments and keyword arguments, and should cause the
    callable to be executed (presumably in a separate thread of
    control) with the given arguments.  Once all calls have been
    spawned, DTest will call the wait() method, which must wait for
    all the spawned callables to complete execution.

    Note that the callable passed to the spawn() method is not a test,
    and no assumptions may be made about the callable or its
    arguments.
    """

    # Need a wrapper to perform the actual decoration
    def wrapper(f):
        # Get the DTest object for the test
        dt = _gettest(f)

        # Change the parallelization strategy
        dt._strategy = st

        # Return the function
        return f

    # If the function is specified, apply the wrapper directly
    if func is not None:
        return wrapper(func)

    # Return the actual decorator
    return wrapper


def parallel(arg):
    """
    Decorates a test to indicate that the test can be executed with a
    multithread parallelization strategy.  This is only meaningful on
    tests that are repeated or on generator function tests.  If used
    in the ``@parallel`` form, the maximum number of threads is
    unlimited; if used as ``@parallel(n)``, the maximum number of
    threads is limited to ``n``.
    """

    # Default strategy is the UnlimitedParallelStrategy
    st = strat.UnlimitedParallelStrategy()

    # Wrapper to actually attach the strategy to the test
    def wrapper(func):
        return strategy(st, func)

    # If arg is a callable, call wrapper directly
    if callable(arg):
        return wrapper(arg)

    # OK, arg is an integer and specifies a limit on the number of
    # threads; set up a LimitedParallelStrategy.
    st = strat.LimitedParallelStrategy(arg)

    # And return the wrapper, which will be the actual decorator
    return wrapper


def policy(p, func=None):
    """
    Used to set the result policy for tests to ``p``.  If ``func`` is
    provided, the result policy for ``func`` is set; otherwise,
    returns a function which can be used as a decorator.  This
    behavior on the presence of ``func`` allows policy() to be used to
    create user-defined result policy decorators.

    Result policies allow tests that are defined as generators or
    which are decorated with the @repeat() decorator to specify more
    complex computations than simply requiring all functions executed
    to succeed.  A result policy is simply a callable, and can be
    either a function or an object with a __call__() method.  It will
    be passed four counts--the total number of functions executed so
    far, the total number of successes seen so far, the total number
    of failures seen so far, and the total number of errors seen so
    far.  It must return a tuple of two boolean values; the first
    should be True if and only if the overall result is a success, and
    the second should be True if and only if the overall result is an
    error.  The second boolean may not be True if the first boolean is
    True.
    """

    # Need a wrapper to perform the actual decoration
    def wrapper(f):
        # Get the DTest object for the test
        dt = _gettest(f)

        # Change the result policy
        dt._policy = p

        # Return the function
        return f

    # If the function is specified, apply the wrapper directly
    if func is not None:
        return wrapper(func)

    # Return the actual decorator
    return wrapper


def threshold(th):
    """
    Decorates a test to indicate that the test's result policy is a
    threshold policy.  The ``th`` argument is a float between 0.0 and
    100.0, and indicates the minimum percentage of tests which must
    succeed for the overall result to be a success.  Note that any
    errors cause the overall result to be an error.
    """

    # Wrapper to actually attach the threshold to the test
    def wrapper(func):
        return policy(pol.ThresholdPolicy(th), func)

    # Now return the wrapper, which will be the actual decorator
    return wrapper


def require(**resources):
    """
    Decorates a test to indicate that the test requires certain
    resources.  Resources are specified as keyword arguments to the
    decorator, with the values being instances of subclasses of
    Resource; allocated versions of those resources will be passed in
    corresponding keyword arguments to the test function.
    """

    # Need a wrapper to perform the actual decoration
    def wrapper(func):
        # Get the DTest object for the test
        dt = _gettest(func)

        # Store the required resources
        dt._resources.update(resources)

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
        setUpLocal = _gettest(getattr(mod, SETUP),
                              DTestFixtureSetUp, True)

        # Set up the dependency
        if setUp is not None:
            depends(setUp)(setUpLocal)

        setUp = setUpLocal
    if hasattr(mod, TEARDOWN):
        tearDownLocal = _gettest(getattr(mod, TEARDOWN),
                                 DTestFixtureTearDown, True)

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
                              DTestFixtureSetUp, True)
        tearDownClass = _gettest(getattr(cls, TEARDOWN + CLASS, None),
                                 DTestFixtureTearDown, True)

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
