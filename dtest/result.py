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


class ResultContext(object):
    """
    ResultContext
    =============

    The ResultContext class is a Python context manager used in the
    automatic collection of captured output and exception handling.
    It is instantiated by DTestResult.accumulate()
    """

    def __init__(self, result, ctx, excs):
        """
        Initialize a ResultContext associated with the given
        ``result``.  The context will handle messages for the part of
        the test run given by ``ctx`` (may be PRE, TEST, or POST).
        The exceptions listed in the ``excs`` tuple are expected; if
        no exceptions are expected, pass ``excs`` as None.
        """

        # Save the basic information
        self.result = result
        self.ctx = ctx
        self.excs = excs

        # There's no timeout...
        self.timeout = None

    def __enter__(self):
        """
        Begin the context handling.  Clears out any captured data and
        initializes any timeouts defined for the test.
        """

        # Clear the captured values for this thread
        capture.retrieve()

        # If test should be timed, set up the timeout
        if self.result._test._timeout:
            self.timeout = Timeout(self.result._test._timeout,
                                   AssertionError("Timed out after %s "
                                                  "seconds" %
                                                  self.result._test._timeout))

    def __exit__(self, exc_type, exc_value, tb):
        """
        Ends context handling.  Cancels any pending timeouts,
        retrieves output data and exceptions, and determines the final
        result of the test.  A DTestMessage object is initialized if
        necessary.
        """

        # Cancel the timeout if one is pending
        if self.timeout is not None:
            self.timeout.cancel()
            self.timeout = None

        # Get the output and clean up
        captured = capture.retrieve()

        # If this was the test, determine a result
        if self.ctx in (PRE, TEST):
            self.result._set_result(self, exc_type, exc_value, tb)

        # Generate a message, if necessary
        if captured or exc_type or exc_value or tb:
            self.result._storemsg(self, captured, exc_type, exc_value, tb)

        # We handled the exception
        return True

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
        self._msgs = {}

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

    def _set_result(self, ctx, exc_type, exc_value, tb):
        """
        Determines the result or error status of the test.  Only
        called if the context is PRE or TEST.
        """

        # Are we expecting any exceptions?
        if ctx.excs:
            self._result = exc_type in ctx.excs
            self._error = (exc_type not in ctx.excs and
                           exc_type != AssertionError)
        else:
            # Guess we're not...
            self._result = exc_type is None
            self._error = (exc_type is not None and
                           exc_type != AssertionError)

    def _storemsg(self, ctx, captured, exc_type, exc_value, tb):
        """
        Allocates and stores a DTestMessage instance which brings
        together captured output and exception values.
        """

        self._msgs[ctx.ctx] = DTestMessage(ctx.ctx, captured,
                                           exc_type, exc_value, tb)

    def accumulate(self, nextctx, excs=None):
        """
        Prepares a context manager for accumulating output for a
        portion of a test.  The ``nextctx`` argument must be one of
        the constants PRE, TEST, or POST, indicating which phase of
        test execution is about to occur.  If ``excs`` is not None, it
        should be a tuple of the exceptions to expect the execution to
        raise; the test passes if one of these exceptions is raised,
        or fails otherwise.
        """

        # Return a context for handling the result
        return ResultContext(self, nextctx, excs)

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

    @property
    def multi(self):
        """
        Returns True only if the result is a multi-result.
        """

        return False


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


class MultiResultContext(ResultContext):
    """
    MultiResultContext
    ==================

    The MultiResultContext class is an extension of the ResultContext
    context manager that adds the requisite support for message IDs.
    These are needed to differentiate the results of multiple test
    runs with DTestResultMulti.
    """

    def __init__(self, result, ctx, excs, msgid):
        """
        Initialize a MultiResultContext associated with the given
        ``result``.  The additional argument ``msgid`` is an ID to be
        associated with the messages that are generated as a result of
        the run; it may be None only if ``ctx`` is TEST.
        """

        # Initialize the superclass
        super(MultiResultContext, self).__init__(result, ctx, excs)

        # Save the message ID as well
        self.msgid = msgid


class DTestResultMulti(DTestResult):
    """
    DTestResultMulti
    ================

    The DTestResultMulti class is an extension of the DTestResult
    class which additionally provides the ability to store the results
    from multiple tests.  This is used, for example, when a defined
    test is a generator, to store the results from all generated
    functions.
    """

    def __init__(self, test):
        """
        Initialize a DTestResultMulti object corresponding to the
        given ``test``.
        """

        super(DTestResultMulti, self).__init__(test)

        # Pre-allocate the KeyedSequence, so we don't run into race
        # conditions
        self._msgseq = KeyedSequence()

        # Also keep track of IDs we've seen so the generated message
        # IDs are stable
        self._idseen = set()

        # Also need to count successes, failures, and errors
        self._success_cnt = 0
        self._failure_cnt = 0
        self._error_cnt = 0
        self._total_cnt = 0

    def _set_result(self, ctx, exc_type, exc_value, tb):
        """
        Extends the superclass method to support threshold-style final
        result computation.
        """

        # If we're in PRE, defer to the superclass method
        if ctx.ctx == PRE:
            super(DTestResultMulti, self)._set_result(ctx, exc_type,
                                                      exc_value, tb)
            return

        # Figure out if this is a success, failure, or an error
        result = None
        if ctx.excs:
            if exc_type in ctx.excs:
                result = '_success_cnt'
        else:
            if exc_type is None:
                result = '_success_cnt'
        if result is None:
            if exc_type != AssertionError:
                result = '_error_cnt'
            else:
                result = '_failure_cnt'

        # Keep track of the number of successes, failures, and errors
        setattr(self, result, getattr(self, result) + 1)
        self._total_cnt += 1

        # Finally, compute the values of _result and _error based on
        # the threshold strategy of the test
        self._result, self._error = self._test._comp_result(self._total_cnt,
                                                            self._success_cnt,
                                                            self._failure_cnt,
                                                            self._error_cnt)

    def _storemsg(self, ctx, captured, exc_type, exc_value, tb):
        """
        Allocates and stores a DTestMessageMulti instance which brings
        together captured output and exception values.
        """

        # We only specially TEST-context messages
        if ctx.ctx != TEST:
            super(DTestResultMulti, self)._storemsg(ctx, captured, exc_type,
                                                    exc_value, tb)
            return

        # Make sure the message sequence goes in the collection of
        # messages
        if TEST not in self._msgs:
            self._msgs[TEST] = self._msgseq

        # Store a message
        self._msgseq[ctx.msgid] = DTestMessageMulti(ctx.ctx, ctx.msgid,
                                                    captured, exc_type,
                                                    exc_value, tb)

    def accumulate(self, nextctx, excs=None, id=None):
        """
        Prepares the DTestResultMulti object for use as a context
        manager.  The ``nextctx`` argument must be one of the
        constants PRE, TEST, or POST, indicating which phase of test
        execution is about to occur.  If ``excs`` is not None, it
        should be a tuple of the exceptions to expect the execution to
        raise; the test passes if one of these exceptions is raised,
        or fails otherwise.

        The ``id`` parameter must be specified if ``nextctx`` is TEST;
        it identifies the test being executed.
        """

        # Force id to an empty string, if it's not specified
        if not id:
            id = ''

        # Starting with 'id', compute a message ID
        msgid = id
        i = 0
        while msgid in self._idseen:
            i += 1
            msgid = "%s#%d" % (id, i)

        # Mark this message ID as in use
        self._idseen.add(msgid)

        # Return a context for handling the result
        return MultiResultContext(self, nextctx, excs, msgid)

    @property
    def multi(self):
        """
        Returns True only if the result is a multi-result.
        """

        return True


class DTestMessageMulti(DTestMessage):
    """
    DTestMessageMulti
    =================

    The DTestMessageMulti class is an extension of DTestMessage that
    adds an :id: attribute to identify the origin of the message in a
    DTestResultMulti result.
    """

    def __init__(self, ctx, id, captured, exc_type, exc_value, exc_tb):
        """
        Initialize a DTestMessageMulti object.  See the class
        docstring for this class and its superclass for the meanings
        of the parameters.
        """

        # Call the superclass constructor
        super(DTestMessageMulti, self).__init__(ctx, captured, exc_type,
                                                exc_value, exc_tb)

        # Also save the id
        self.id = id


class KeyedSequence(object):
    """
    KeyedSequence
    =============

    The KeyedSequence class is a helper class for DTestResultMulti.
    Messages (DTestMessageMulti objects) from tests are stored in an
    ordered sequence, but the sequence should also be accessible by a
    test name.  This class implements an abbreviated sequence
    interface that enables the sequence to be indexed by an integer
    index (or array slice), or by a string key.  New items may not be
    added to the sequence using the standard operations such as
    append(); they may only be added to the sequence by using
    assignment by string key.

    This class does support iteration.
    """

    def __init__(self):
        """
        Initialize a KeyedSequence object.
        """

        # Keep an index of keys to list positions
        self._index = {}
        self._values = []

    def __contains__(self, key):
        """
        Determines if ``key`` exists within the sequence.  The ``key``
        may only be a string; there is no support for searching for
        items within the sequence.
        """

        # Check if the key exists
        return key in self._index

    def __getitem__(self, key):
        """
        Retrieve the item or items associated with ``key``.  The
        ``key`` may be an integer or a string.  Array slices are also
        supported.
        """

        # If key is an integer or a slice, use the values list
        if isinstance(key, (int, long, slice)):
            return self._values[key]

        # Get the index from the key and return that
        return self._values[self._index[key]]

    def __setitem__(self, key, value):
        """
        Set the item associated with ``key``.  The ``key`` may be an
        integer or a string.  Replacing multiple elements with an
        array slice is not permitted.
        """

        # If key is a slice, fault
        if isinstance(key, slice):
            raise TypeError("cannot replace slice")

        # If key is an integer, use the values list
        if isinstance(key, (int, long)):
            self._values[key] = value
            return

        # Does the key already exist?
        if key not in self._index:
            # Adding a new value, so let's add the key to the index
            self._index[key] = len(self)
            self._values.append(value)
            return

        # OK, just need to replace existing value
        self._values[self._index[key]] = value

    def __len__(self):
        """
        Return the number of items in the KeyedSequence.
        """

        # Return the values
        return len(self._values)

    def __iter__(self):
        """
        Return an iterator which will iterate over the items in the
        sequence.
        """

        # Iterate over the values
        return iter(self._values)

    def count(self, *args, **kwargs):
        """
        Count the number of instances of a particular item in the
        sequence.
        """

        # Use the values list
        return self._values.count(*args, **kwargs)

    def index(self, *args, **kwargs):
        """
        Determine the index of a particular item in the sequence.
        """

        # Use the values list
        return self._values.index(*args, **kwargs)
