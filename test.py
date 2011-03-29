import StringIO
import sys


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

    def __repr__(self):
        # Generate a representation of the test
        return ('<%s.%s object at %#x wrapping %r>' %
                (self.__class__.__module__, self.__class__.__name__,
                 id(self), self.test))

    def _set_pre(self, pre):
        # Save the pre-test fixture
        self._pre = pre

    def _set_post(self, post):
        # Save the post-test fixture
        self._post = post

    @property
    def result(self):
        # We want the result to be read-only, but to be accessed like
        # an attribute
        return self._result

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
        self._msgs = {}
        self._out = None
        self._orig_out = None
        self._err = None
        self._orig_err = None

    def __enter__(self):
        # Set up the context
        self._ctx = self._nextctx

        # Save the current stdout and stderr
        self._orig_out = sys.stdout
        self._orig_err = sys.stderr

        # Set up string buffers for output and error
        self._out = StringIO.StringIO()
        self._err = StringIO.StringIO()

        # And set them up
        sys.stdout = self._out
        sys.stderr = self._err

    def __exit__(self, exc_type, exc_value, tb):
        # Restore standard output and error
        sys.stdout = self._orig_out
        sys.stderr = self._orig_err
        self._orig_out = None
        self._orig_err = None

        # Get the output information and clean up
        outdata = self._out.getvalue()
        self._out.close()
        self._out = None

        # Get the error information and clean up
        errdata = self._err.getvalue()
        self._err.close()
        self._err = None

        # If this was the test, determine a result
        if self._ctx == TEST:
            self._result = exc_type is None

        # Generate a message, if necessary
        if outdata or errdata or exc_type or exc_value or tb:
            self._msgs[self._ctx] = DTestMessage(self._ctx,
                                                 outdata, errdata,
                                                 exc_type, exc_value, tb)

        # Clean up the context
        self._ctx = None
        self._nextctx = None

        # We handled the exception
        return True

    def __nonzero__(self):
        # The boolean value is True for pass, False for fail or not
        # run
        return self._result is True

    def __len__(self):
        # Return the number of messages
        return len(self._msgs)

    def __getitem__(self, key):
        # Return the message for the desired key
        return self._msgs[key]

    def __contains__(self, key):
        # Does the key exist in the list of messages?
        return key in self._msgs

    def __repr__(self):
        # Generate a representation of the result
        return ('<%s.%s object at %#x result %r with messages %r>' %
                (self.__class__.__module__, self.__class__.__name__,
                 id(self), self._result, self._msgs.keys()))

    def accumulate(self, nextctx):
        # Save the next context
        self._nextctx = nextctx
        return self


class DTestMessage(object):
    def __init__(self, ctx, out, err, exc_type, exc_value, tb):
        # Save all the message information
        self.ctx = ctx
        self.out = out
        self.err = err
        self.exc_type = exc_type
        self.exc_value = exc_value
        self.exc_tb = tb
