from dtest import capture
from dtest.constants import *


class DTestResult(object):
    def __init__(self, test):
        self._test = test
        self._state = None
        self._result = None
        self._error = False
        self._nextctx = None
        self._ctx = None
        self._msgs = {}

    def __enter__(self):
        # Set up the context
        self._ctx = self._nextctx

        # Clear the captured values for this thread
        capture.retrieve()

    def __exit__(self, exc_type, exc_value, tb):
        # Get the output and clean up
        captured = capture.retrieve()

        # If this was the test, determine a result
        if self._ctx == TEST:
            self._result = exc_type is None
            self._error = exc_type is not None and exc_type != AssertionError

        # Generate a message, if necessary
        if captured or exc_type or exc_value or tb:
            self._msgs[self._ctx] = DTestMessage(self._ctx, captured,
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

    def __str__(self):
        # Return our state, which is an excellent summary of the
        # result
        return self._state

    def __repr__(self):
        # Generate a representation of the result
        return ('<%s.%s object at %#x state %s with messages %r>' %
                (self.__class__.__module__, self.__class__.__name__,
                 id(self), self._state, self._msgs.keys()))

    def _transition(self, state=None, notify=None):
        # If state is None, determine the state to transition to based
        # on the result
        if state is None:
            if self:
                state = UOK if self._test._exp_fail else OK
            elif self._error:
                state = ERROR
            else:
                state = XFAIL if self._test._exp_fail else FAIL

        # Issue an appropriate notification
        if notify is not None:
            notify(self._test, state)

        # Transition to the new state
        self._state = state

    def accumulate(self, nextctx):
        # Save the next context
        self._nextctx = nextctx
        return self

    @property
    def test(self):
        # We want the test to be read-only, but to be accessed like an
        # attribute
        return self._test

    @property
    def state(self):
        # We want the state to be read-only, but to be accessed like
        # an attribute
        return self._state

    @property
    def msgs(self):
        # Retrieve the messages in order
        msglist = []
        for mt in (PRE, TEST, POST):
            if mt in self._msgs:
                msglist.append(self._msgs[mt])

        # Return the list of messages
        return msglist


class DTestMessage(object):
    def __init__(self, ctx, captured, exc_type, exc_value, tb):
        # Save all the message information
        self.ctx = ctx
        self.captured = captured
        self.exc_type = exc_type
        self.exc_value = exc_value
        self.exc_tb = tb
