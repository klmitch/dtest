"""
============
Test Running
============

This module contains the run_test() function and the associated Queue
class, which together provide the functionality for executing tests in
a threaded manner while properly handling ordering implied by
dependencies.  Output is specified by passing references to functions
in to run_test().
"""

import sys
import traceback

from eventlet import spawn_n, monkey_patch
from eventlet.event import Event
from eventlet.semaphore import Semaphore

from dtest import capture
from dtest.constants import *
from dtest import test


DEF_LINEWIDTH = 78


class Queue(object):
    """
    Queue
    =====

    The Queue class maintains a queue of tests waiting to be run.  The
    constructor selects the tests, based on the result of the skip()
    function passed in, while the spawn() method selects and spawns
    the actual tests to be run.  The run() method is the entry point,
    causing the initial set of tests to be run, and run_test() is run
    in a separate thread for each test.  Note that the algorithm
    implemented here for selecting waiting tests may not properly
    detect cycles, and the test runner could hang as a result.

    Implementation Details
    ----------------------

    The ``sem`` attribute is either None or a Semaphore instance used
    to cap the number of threads that can be running at any given
    time.  The ``tests`` attribute is a utility attribute containing
    the list of defined tests, while the ``waiting`` attribute is a
    set containing all tests which are still waiting to be run
    (skipped tests will never appear in this set).  Thread safety
    requires that accesses to the ``waiting`` attribute be locked, so
    a Semaphore instance is stored in the ``waitlock`` parameter for
    this purpose.  Finally, the ``th_count`` and ``th_max`` attributes
    maintain a count of currently executing threads and the maximum
    thread count observed, respectively, while ``th_event`` contains
    an Event instance which is signaled once it is determined that all
    tests have been run.
    """

    def __init__(self, maxth, skip, notify):
        """
        Initialize a Queue.  The ``maxth`` argument must be either
        None or an integer specifying the maximum number of
        simultaneous threads permitted.  The ``skip`` and ``notify``
        arguments are function references; ``skip`` should take a test
        and return True if the test should be skipped, and ``notify``
        takes a test and the state to which it is transitioning, and
        may use that information to emit a test result.  Note that the
        ``notify`` function will receive state transitions to the
        RUNNING state, as well as state transitions for test fixtures;
        callers may find the DTestBase.istest() method useful for
        differentiating between regular tests and test fixtures for
        reporting purposes.

        Note that the ``maxth`` restriction is implemented by having
        the spawned thread wait on the Semaphore, and thus ``th_max``
        may be greater than ``maxth``.
        """

        # maxth allows us to limit the number of simultaneously
        # executing threads
        if maxth is None:
            self.sem = None
        else:
            self.sem = Semaphore(maxth)

        # When reporting is done, we need a list of all tests...
        self.tests = test.DTestBase.tests()

        # Generate a list of tests; skip() returns True to cause a
        # test to be skipped.  Default skip() tests the test's _skip
        # attribute.
        waiting = []
        for dt in self.tests:
            # Prepare the test--allocates a result
            dt._prepare()

            # Do we skip this one?
            if skip(dt):
                dt._skipped(notify)
            else:
                waiting.append(dt)

        # Some tests may have moved to the SKIPPED state due to
        # dependencies, so filter them out
        self.waiting = set([dt for dt in self.tests if dt.state != SKIPPED])
        self.waitlock = Semaphore()

        # Count threads, and allocate an event to be signaled when the
        # last thread exits
        self.th_count = 0
        self.th_event = Event()
        self.th_max = 0

    def spawn(self, tests, notify):
        """
        Selects all ready tests from the set or list specified in
        ``tests`` and spawns threads to execute them.  The ``notify``
        argument specifies a notification function, as for __init__().
        Note that the maximum thread count restriction is implemented
        by having the thread wait on the ``sem`` Semaphore after being
        spawned.
        """

        # Work with a copy of the tests
        tests = list(tests)

        # Loop through the list
        while tests:
            # Pop off a test to consider
            test = tests.pop(0)

            with self.waitlock:
                # Is test waiting?
                if test not in self.waiting:
                    continue

                # OK, check dependencies
                elif test._depcheck(notify):
                    # No longer waiting
                    self.waiting.remove(test)

                    # Spawn the test
                    self.th_count += 1
                    if self.th_count > self.th_max:
                        self.th_max = self.th_count
                    spawn_n(self.run_test, test, notify)

                # Dependencies failed; check if state changed and add
                # its dependents if so
                elif test.state is not None:
                    # No longer waiting
                    self.waiting.remove(test)

                    # Check all its dependents.  Note--not trying to
                    # remove duplicates, because some formerly
                    # unrunnable tests may now be runnable because of
                    # the state change
                    tests.extend(list(test.dependents))

    def run(self, notify):
        """
        Runs all tests that have been queued up in the Queue object.
        The ``notify`` argument specifies a notification function, as
        for __init__().  Does not return until all tests have been
        run.  Note that if dependency cycles are present, this
        function may hang.
        """

        # Walk through all the waiting tests; note the copy, to avoid
        # modifications to self.waiting from upsetting us
        self.spawn(self.waiting, notify)

        # Wait for all tests to finish
        if self.th_count > 0:
            self.th_event.wait()

        # For convenience, return the full list of results
        return [t.result for t in self.tests]

    def run_test(self, test, notify):
        """
        Execute ``test``.  The ``notify`` argument specifies a
        notification function, as for __init__().  This method is
        meant to be run in a new thread.

        Once a test is complete, the thread's dependents will be
        passed back to the spawn() method, in order to pick up and
        execute any tests that are now ready for execution.
        """

        # Acquire the semaphore
        if self.sem is not None:
            self.sem.acquire()

        # Set up arguments for the test
        args = []
        if test.class_ is not None:
            # Need self
            args.append(test.class_())

        # Execute the test
        test(*args, _notify=notify)

        # Now, walk through its dependents and check readiness
        self.spawn(test.dependents, notify)

        # All right, we're done; release the semaphore
        if self.sem is not None:
            self.sem.release()

        # Decrement the thread count
        self.th_count -= 1

        # If thread count is now 0, signal the event
        with self.waitlock:
            if len(self.waiting) == 0 and self.th_count == 0:
                self.th_event.send()


def _msg(test, m=None, hdr=''):
    """
    Default msg() function for run_tests().  The ``test`` argument
    specifies the test being run.  The ``m`` argument will be None or
    an instance of DTestMessage; in the latter case, the ``hdr``
    argument will specify a header to identify the origin of the
    message.

    In the case that ``m`` is None, a header identifying the test is
    emitted; otherwise, the message is emitted, prefixed by the header
    if one is specified.  Exception information is emitted before any
    output.
    """

    # Determine line width
    lw = DEF_LINEWIDTH

    # Output the banner if m is None
    if m is None:
        print
        print "=" * lw
        print str(test).center(lw)
        print "=" * lw
        return

    # Output header information
    if hdr:
        print hdr.center(lw)
        print '-' * lw

    # Format exception information
    if m.exc_type is not None:
        # Emit the exception information
        print (' Exception %s ' % m.exc_type.__name__).center(lw, '-')
        traceback.print_exception(m.exc_type, m.exc_value, m.exc_tb)

    # Format output data
    for name, desc, value in m.captured:
        print (' %s ' % desc).center(lw, '-')
        print value.rstrip()

    # Emit a closing line
    print '-' * lw


def _summary(counts):
    """
    Default summary() function for run_tests().  The ``counts``
    argument specifies the counts for each type of test result.

    Outputs a summary indicating the total number of tests executed
    and the number of threads that were used to execute the tests,
    then outputs a variable number of lines to summarize the count of
    each type of result.
    """

    # Emit summary data
    print ("%d tests run in %d max simultaneous threads" %
           (counts['total'], counts['threads']))
    if counts[OK] > 0:
        unexp = ''
        if counts[UOK] > 0:
            unexp = ' (%d unexpected)' % counts[UOK]
        print "  %d tests successful%s" % (counts[OK], unexp)
    if counts[SKIPPED] > 0:
        print "  %d tests skipped" % counts[SKIPPED]
    if counts[FAIL] + counts[ERROR] + counts[DEPFAIL] > 0:
        # Set up the breakdown
        bd = []
        total = 0
        if counts[FAIL] > 0:
            exp = ''
            if counts[XFAIL] > 0:
                exp = ' [%d expected]' % counts[XFAIL]
            bd.append('%d failed%s' % (counts[FAIL], exp))
            total += counts[FAIL]
        if counts[ERROR] > 0:
            bd.append('%d errors' % counts[ERROR])
            total += counts[ERROR]
        if counts[DEPFAIL] > 0:
            bd.append('%d failed due to dependencies' % counts[DEPFAIL])
            total += counts[DEPFAIL]

        print "  %d tests failed (%s)" % (total, ', '.join(bd))


def _notify(test, state):
    """
    Default notify() function for run_tests().  The ``test`` argument
    specifies the test or test fixture, and the ``state`` argument
    indicates the state the test is transitioning to.

    This implementation ignores test fixtures or transitions to the
    RUNNING state, and emits messages to sys.__stdout__ (since
    sys.stdout is being captured) containing the name of the test and
    the state being transitioned to.  This provides visual display of
    the result of a test.
    """

    lw = DEF_LINEWIDTH

    # Are we interested in this test?
    if not test.istest() or state == RUNNING:
        return

    # Determine the name of the test
    name = str(test)

    # Determine the width of the test name field
    width = lw - len(state) - 1

    # Truncate the name, if necessary
    if len(name) > width:
        name = name[:width - 3] + '...'

    # Emit the status message
    print >>sys.__stdout__, "%-*s %s" % (width, name, state)


def run_tests(maxth=None, skip=lambda dt: dt.skip,
              notify=_notify, msg=_msg, summary=_summary):
    """
    Run all defined tests.  The ``maxth`` argument, if an integer,
    indicates the maximum number of simultaneously executing threads
    that may be used.  The ``skip`` argument specifies a function
    which, when passed a test, returns True to indicate that that test
    should be skipped; by default, it returns the value of the
    ``skip`` attribute on the test, which may be set using the @skip
    decorator.  The ``notify`` argument specifies a function which
    takes as arguments the test and a state the test is transitioning
    to; it may emit status information to sys.__stdout__ (note that
    sys.stdout is captured while tests are running).  The ``msg``
    argument specifies a function which takes as arguments the test, a
    DTestMessage object, and a string header (note that the latter two
    arguments *must* be optional); the msg() function will be called
    first with just the test, after which it will be called once for
    each saved message.  If no messages are saved for a given test,
    the msg() function will not be called on that test.  Finally, the
    ``summary`` argument specifies a function which takes as its sole
    argument a dictionary with summary counts of each type of result.
    The keys are as follows:

    OK
        The number of tests which passed.  This includes the count of
        unexpected passes (tests marked with the @failing decorator
        which passed).

    UOK
        The number of tests which unexpectedly passed.

    SKIPPED
        The number of tests which were skipped in this test run.

    FAIL
        The number of tests which failed.  This includes the count of
        expected failures (tests marked with the @failing decorator
        which failed).

    XFAIL
        The number of tests which failed, where failure was expected.

    ERROR
        The number of tests which experienced an error--an unexpected
        exception thrown while executing the test.

    DEPFAIL
        The number of tests which could not be executed because tests
        they were dependent on failed.

    'total'
        The total number of tests considered for execution.

    'threads'
        The maximum number of threads which were utilized while
        running tests.

    Note that test fixtures are not included in these counts.  If a
    test fixture fails (raises an AssertionError) or raises any other
    exception, all tests dependent on that test fixture will fail due
    to dependencies.  The msg() function will be passed the test
    fixture descriptor.
    """

    # Let's begin by making sure we're monkey-patched
    monkey_patch()

    # Now, initialize the test queue...
    q = Queue(maxth, skip, notify)

    # Install the capture proxies...
    capture.install()

    # Run the tests
    results = q.run(notify)

    # Uninstall the capture proxies
    capture.uninstall()

    # Walk through the tests and output the results
    cnt = {
        OK: 0,
        UOK: 0,
        SKIPPED: 0,
        FAIL: 0,
        XFAIL: 0,
        ERROR: 0,
        DEPFAIL: 0,
        'total': 0,
        'threads': q.th_max,
        }
    for r in results:
        # Update the counts
        cnt[r.state] += int(r.test)
        cnt['total'] += int(r.test)

        # Special case update for unexpected OKs and expected failures
        if r.state == UOK:
            cnt[OK] += int(r.test)
        elif r.state == XFAIL:
            cnt[FAIL] += int(r.test)

        if len(r) > 0:
            # Emit the header
            msg(r.test)

            # Emit data from the pre-test fixture...
            if PRE in r:
                msg(r.test, r[PRE], 'Pre-test Fixture')

            # ...from the test itself...
            if TEST in r:
                msg(r.test, r[TEST])

            # ...and from the post-test fixture
            if POST in r:
                msg(r.test, r[POST], 'Post-test Fixture')

    # Emit summary data
    summary(cnt)
