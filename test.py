# Test states
RUNNING = 'RUNNING'    # test running
FAILED = 'FAILED'      # test failed
DEPFAIL = 'DEPFAIL'    # dependency failed
COMPLETE = 'COMPLETE'  # test completed

# Result origins
PRE = 'PRE'    # Error in pre-execute fixture
POST = 'POST'  # Error in post-execute fixture
TEST = 'TEST'  # Error from the test itself


class DTestBase(object):
    _tests = {}

    def __new__(cls, test):
        # If func is a DTestBase subclass, then return it directly
        if isinstance(test, DTestBase):
            return test

        # Require it to be a callable...
        if not callable(test):
            raise TestException("%r must be a callable" % test)

        # Make sure we haven't already created one
        if test in DTestBase._tests:
            return DTestBase._tests[test]

        # OK, construct a new one
        dt = super(DTestBase, cls).__new__(cls)
        dt._test = test
        dt._exp_pass = True
        dt._skip = False
        dt._state = None
        dt._pre = None
        dt._post = None
        dt._deps = set()
        dt._attrs = {}
        dt._result = DTestResult(dt)

        # Save it in the cache
        DTestBase._tests[test] = dt

        # And return it
        return dt

    def __getattr__(self, key):
        # Get the attribute out of the _attrs map
        return dt._attrs[key]

    def __setattr__(self, key, value):
        # Is it an internal attribute?
        if key[0] == '_':
            return super(DTestBase, self).__setattr__(key, value)

        # Store that in the _attrs map
        self._attrs[key] = value

    def __delattr__(self, key):
        # Is it an internal attribute?
        if key[0] == '_':
            return super(DTestBase, self).__delattr__(key)

        # Delete from the _attrs map
        del self._attrs[key]

    def __call__(self, *args, **kwargs):
        # Transition to the running state
        self._state = RUNNING

        # Perform preliminary call
        if self._pre is not None:
            with self._result.accumulate(PRE):
                self._pre()

        # Execute the test
        with self._result.accumulate(TEST):
            self._test(*args, **kwargs)

        # Invoke any clean-up that's necessary
        if self._post is not None:
            with self._result.accumulate(POST):
                self._post()

        # Transition to the appropriate ending state
        self._state = COMPLETE if self._result else FAILED

    def __int__(self):
        # In an integer context, we're 0; this is how we can count the
        # number of tests
        return 0

    def __hash__(self):
        # Return the hash of the backing test
        return hash(self.test)

    def __eq__(self, other):
        # Compare test objects
        return self.test is other.test

    def __ne__(self, other):
        # Compare test objects
        return self.test is not other.test

    def add_dep(self, dep):
        # First, we need to find the requisite DTest (fixtures can be
        # passed in as DTestFixture instances to override)
        dt = DTest(dep)

        # Now simply add it to the list of dependencies
        self._deps.add(dt)


class DTest(DTestBase):
    def __int__(self):
        # This is a single test, so return 1 so we contribute to the
        # count
        return 1


class DTestFixture(DTestBase):
    pass


class DTestResult(object):
    def __init__(self, test):
        self._test = test
        self._result = None
        self._nextctx = None
        self._ctx = None
        self._msgs = []

    def __enter__(self):
        # Set up the context
        self._ctx = self._nextctx

    def __exit__(self, exc_type, exc_value, tb):
        # If this was the test, determine a result
        if self._ctx == TEST:
            self._result = exc_type is None

        # Now, if there was an exception, generate a message
        if exc_type is not None:
            # XXX generate message
            pass

    def __nonzero__(self):
        return self._result is True

    def accumulate(self, nextctx):
        # Save the next context
        self._nextctx = nextctx
        return self
