# Result origins
PRE = 'PRE'    # Error in pre-execute fixture
POST = 'POST'  # Error in post-execute fixture
TEST = 'TEST'  # Error from the test itself


class DTestResult(object):
    def __init__(self, test):
        self._test = test
        self._result = None
        self._nextctx = None
        self._ctx = None
        self._msgs = {}

    def __enter__(self):
        # Set up the context
        self._ctx = self._nextctx

        # Clear the streams for this thread
        stream.pop()

    def __exit__(self, exc_type, exc_value, tb):
        # Get the output and clean up
        outdata, errdata = stream.pop()

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
