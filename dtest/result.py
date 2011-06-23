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
============
Test Results
============

This module contains the DTestResult and DTestMessage classes, which
are used to represent the results of tests.  Instances of DTestResult
contain the current state of a test, whether the test was successful
or if an error was encountered, and any exceptions and output messages
that were generated while running the test.  The output messages are
contained in an instance of DTestMessage.
"""

from dtest import capture
from dtest.constants import *

from eventlet.timeout import Timeout


class DTestResult(object):
    """
    DTestResult
    ===========

    The DTestResult class stores the current state of a test, as well
    as the results and output messages of a test and its immediate
    fixtures.  Various special methods are implemented, allowing the
    result to appear True if the test passed and False if the test did
    not pass, as well as allowing the messages to be accessed easily.
    Three public properties are available: the ``test`` property
    returns the associated test; the ``state`` property returns the
    state of the test, which can also indicate the final result; and
    the ``msgs`` property returns a list of the messages generated
    while executing the test.

    Note that the string representation of a DTestResult object is
    identical to its state.

    Test messages
    -------------

    Messages can be emitted during three separate phases of test
    execution.  The first step of executing a test is to execute the
    setUp() method defined for the class; the second step is executing
    the test itself; and the third step is to execute the tearDown()
    method defined for the class.  (The setUp() and tearDown() methods
    used can be set or overridden using the setUp() and tearDown()
    decorators of DTest.)  Messages produced by each phase are saved,
    and are identified by the constants PRE, TEST, and POST,
    respectively.  This could be used to warn a developer that,
    although a test passed, the following tearDown() function failed
    for some reason.

    The list of test message objects (instances of class DTestMessage)
    can be retrieved, in the order (PRE, TEST, POST), using the
    ``msgs`` property, as indicated above.  Additionally, the presence
    of each type of message can be discerned with the ``in`` operator
    (e.g., ``PRE in result``), and the message itself retrieved using
    array accessor syntax (e.g., ``result[TEST]``).  The total number
    of messages available can be determined using the len() operator.

    Context Handler
    ---------------

    Instances of DTestResult are context handlers, usable with the
    Python ``with`` statement.  This is used deep within the DTest
    class to collect and send the output into the correct DTestMessage
    object.  A DTestResult object should *never* be used in a ``with``
    statement without first calling the accumulate() method with a
    valid origin (one of the constants PRE, TEST, or POST).  For
    convenience, accumulate() returns the DTestResult object, allowing
    it to be used directly in the ``with`` statement.  This is an
    internal interface, and test developers should not need to use it.
    """

    def __init__(self, test):
        """
        Initialize a DTestResult object corresponding to the given
        ``test``.
        """

        self._test = test
        self._state = None
        self._result = None
        self._error = False
        self._nextctx = None
        self._ctx = None
        self._excs = None
        self._timeout = None
        self._msgs = {}

    def __enter__(self):
        """
        Begin the context handling.  Clears out any captured data and
        initializes any timeouts defined for the test.
        """

        # Set up the context
        self._ctx = self._nextctx

        # Clear the captured values for this thread
        capture.retrieve()

        # If test should be timed, set up the timeout
        if self._test._timeout:
            self._timeout = Timeout(self._test._timeout,
                                    AssertionError("Timed out after %s "
                                                   "seconds" %
                                                   self._test._timeout))

    def __exit__(self, exc_type, exc_value, tb):
        """
        Ends context handling.  Cancels any pending timeouts,
        retrieves output data and exceptions, and determines the final
        result of the test.  A DTestMessage object is initialized if
        necessary.
        """

        # Cancel the timeout if one is pending
        if self._timeout is not None:
            self._timeout.cancel()
            self._timeout = None

        # Get the output and clean up
        captured = capture.retrieve()

        # If this was the test, determine a result
        if self._ctx in (PRE, TEST):
            self._set_result(exc_type, exc_value, tb)

        # Generate a message, if necessary
        if captured or exc_type or exc_value or tb:
            self._storemsg(captured, exc_type, exc_value, tb)

        # Clean up the context
        self._ctx = None
        self._nextctx = None
        self._excs = None

        # We handled the exception
        return True

    def __nonzero__(self):
        """
        Allows a DTestResult object to be used in a boolean context;
        the object will test as True if the test passed, otherwise it
        will test as False.
        """

        # The boolean value is True for pass, False for fail or not
        # run
        return self._result is True

    def __len__(self):
        """
        Allows the len() built-in to be called on a DTestResult
        object.  Returns the number of messages.
        """

        # Return the number of messages
        return len(self._msgs)

    def __getitem__(self, key):
        """
        Allows a message, as specified by ``key``, to be retrieved
        using array access notation (square brackets, "[" and "]").
        Valid values for ``key`` are the constants PRE, TEST, and
        POST.
        """

        # Return the message for the desired key
        return self._msgs[key]

    def __contains__(self, key):
        """
        Allows the ``in`` operator to be used on a DTestResult object.
        Determines if the message specified by ``key`` is set on this
        result.  Valid values for ``key`` are the constants PRE, TEST,
        and POST.
        """

        # Does the key exist in the list of messages?
        return key in self._msgs

    def __str__(self):
        """
        Allows the str() built-in to be called on a DTestResult
        object.  Returns the string version of the test state.  In the
        event the test has not been run, returns the empty string.
        """

        # Return our state, which is an excellent summary of the
        # result
        return '' if self._state is None else self._state

    def __repr__(self):
        """
        Allows the repr() built-in to be called on a DTestResult
        object.  Augments the default representation to include the
        state and the messages present.
        """

        # Generate a representation of the result
        return ('<%s.%s object at %#x state %s with messages %r>' %
                (self.__class__.__module__, self.__class__.__name__,
                 id(self), self._state, self._msgs.keys()))

    def _transition(self, state=None, output=None):
        """
        Performs a transition to the given ``state``.  If ``state`` is
        None, the state will be determined from the status of the
        ``_result`` and ``_error`` attributes, set by __exit__().
        Note that the test's ``_exp_fail`` attribute is also consulted
        to determine if the result was expected or not.
        """

        # If state is None, determine the state to transition to based
        # on the result
        if state is None:
            if self._result:
                state = UOK if self._test._exp_fail else OK
            elif self._error:
                state = ERROR
            else:
                state = XFAIL if self._test._exp_fail else FAIL

        # Issue an appropriate notification
        if output is not None:
            output.notify(self._test, state)

        # Transition to the new state
        self._state = state

    def _set_result(self, exc_type, exc_value, tb):
        """
        Determines the result or error status of the test.  Only
        called if the context is PRE or TEST.
        """

        # Are we expecting any exceptions?
        if self._excs:
            self._result = exc_type in self._excs
            self._error = (exc_type not in self._excs and
                           exc_type != AssertionError)
        else:
            # Guess we're not...
            self._result = exc_type is None
            self._error = (exc_type is not None and
                           exc_type != AssertionError)

    def _storemsg(self, captured, exc_type, exc_value, tb):
        """
        Allocates and stores a DTestMessage instance which brings
        together captured output and exception values.
        """

        self._msgs[self._ctx] = DTestMessage(self._ctx, captured,
                                             exc_type, exc_value, tb)

    def accumulate(self, nextctx, excs=None):
        """
        Prepares the DTestResult object for use as a context manager.
        The ``nextctx`` argument must be one of the constants PRE,
        TEST, or POST, indicating which phase of test execution is
        about to occur.  If ``excs`` is not None, it should be a tuple
        of the exceptions to expect the execution to raise; the test
        passes if one of these exceptions is raised, or fails
        otherwise.
        """

        # Save the next context
        self._nextctx = nextctx
        self._excs = excs
        return self

    @property
    def test(self):
        """
        Retrieve the test associated with this DTestResult object.
        """

        # We want the test to be read-only, but to be accessed like an
        # attribute
        return self._test

    @property
    def state(self):
        """
        Retrieve the current state of this DTestResult object.  If the
        test has not been executed, returns None.
        """

        # We want the state to be read-only, but to be accessed like
        # an attribute
        return self._state

    @property
    def msgs(self):
        """
        Retrieve the list of messages associated with this DTestResult
        object.  The tests will be in the order (PRE, TEST, POST); if
        a given message does not exist, it will be omitted from the
        list.
        """

        # Retrieve the messages in order
        msglist = []
        for mt in (PRE, TEST, POST):
            if mt in self._msgs:
                msglist.append(self._msgs[mt])

        # Return the list of messages
        return msglist


class DTestMessage(object):
    """
    DTestMessage
    ============

    The DTestMessage class is a simple container class for messages
    generated by test execution.  The following attributes are
    defined:

    :ctx:
        The context in which the message was generated.  May be one of
        the constants PRE, TEST, or POST.

    :captured:
        A list of tuples containing captured output.  For each tuple,
        the first element is a short name; the second element is a
        description, suitable for display to the user; and the third
        element is the captured output.  All three elements are simple
        strings.

    :exc_type:
        If an unexpected exception (including AssertionError) is
        thrown while executing the test, this attribute will contain
        the type of the exception.  If no exception is thrown, this
        attribute will be None.

    :exc_value:
        If an unexpected exception (including AssertionError) is
        thrown while executing the test, this attribute will contain
        the actual exception object.  If no exception is thrown, this
        attribute will be None.

    :exc_tb:
        If an unexpected exception (including AssertionError) is
        thrown while executing the test, this attribute will contain
        the traceback object.  If no exception is thrown, this
        attribute will be None.
    """

    def __init__(self, ctx, captured, exc_type, exc_value, exc_tb):
        """
        Initialize a DTestMessage object.  See the class docstring for
        the meanings of the parameters.
        """

        # Save all the message information
        self.ctx = ctx
        self.captured = captured
        self.exc_type = exc_type
        self.exc_value = exc_value
        self.exc_tb = exc_tb
