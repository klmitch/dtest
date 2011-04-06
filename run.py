"""
============
Test Running
============

This module contains the run_test() function and the associated Queue
class, which together provide the functionality for executing tests in
a threaded manner while properly handling ordering implied by
dependencies.  Output is specified by passing an instance of
DTestOutput to run_tests().
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

    The ``notify`` attribute references the notify function to be
    passed when running a test.  The ``sem`` attribute is either None
    or a Semaphore instance used to cap the number of threads that can
    be running at any given time.  The ``tests`` attribute is a
    utility attribute containing the list of defined tests, while the
    ``waiting`` attribute is a set containing all tests which are
    still waiting to be run (skipped tests will never appear in this
    set).  Thread safety requires that accesses to the ``waiting``
    attribute be locked, so a Semaphore instance is stored in the
    ``waitlock`` parameter for this purpose.  Finally, the
    ``th_count`` and ``th_max`` attributes maintain a count of
    currently executing threads and the maximum thread count observed,
    respectively, while ``th_event`` contains an Event instance which
    is signaled once it is determined that all tests have been run.
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

        # Save notify for future use
        self.notify = notify

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
                dt._skipped(self.notify)
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

    def spawn(self, tests):
        """
        Selects all ready tests from the set or list specified in
        ``tests`` and spawns threads to execute them.  Note that the
        maximum thread count restriction is implemented by having the
        thread wait on the ``sem`` Semaphore after being spawned.
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
                elif test._depcheck(self.notify):
                    # No longer waiting
                    self.waiting.remove(test)

                    # Spawn the test
                    self.th_count += 1
                    if self.th_count > self.th_max:
                        self.th_max = self.th_count
                    spawn_n(self.run_test, test)

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

    def run(self):
        """
        Runs all tests that have been queued up in the Queue object.
        Does not return until all tests have been run.  Note that if
        dependency cycles are present, this function may hang.
        """

        # Walk through all the waiting tests; note the copy, to avoid
        # modifications to self.waiting from upsetting us
        self.spawn(self.waiting)

        # Wait for all tests to finish
        if self.th_count > 0:
            self.th_event.wait()

        # For convenience, return the full list of results
        return [t.result for t in self.tests]

    def run_test(self, test):
        """
        Execute ``test``.  This method is meant to be run in a new
        thread.

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
        test(*args, _notify=self.notify)

        # Now, walk through its dependents and check readiness
        self.spawn(test.dependents)

        # All right, we're done; release the semaphore
        if self.sem is not None:
            self.sem.release()

        # Decrement the thread count
        self.th_count -= 1

        # If thread count is now 0, signal the event
        with self.waitlock:
            if len(self.waiting) == 0 and self.th_count == 0:
                self.th_event.send()


class DTestOutput(object):
    """
    DTestOutput
    ===========

    The DTestOutput class is a utility class for grouping together all
    output generation for the test framework.  The ``output``
    attribute contains a stream-like object to which output may be
    sent, and defaults to sys.__stdout__ (note that sys.stdout may be
    captured as the output of a test).  The notify() method is called
    whenever a test or test fixture transitions to an alternate state;
    the result() method is called to output the results of a test; and
    the summary() method is called to output a summary of the results
    of a test.  The default implementations of these methods send
    their output to the stream in the ``output`` attribute, but each
    may be overridden to perform alternate output.  This could, for
    instance, be used to display test framework output in a GUI or to
    generate a web page.
    """

    def __init__(self, output=sys.__stdout__, linewidth=DEF_LINEWIDTH):
        """
        Initialize a DTestOutput object with the given ``output``
        stream (defaults to sys.__stdout__) and linewidth.
        """

        # Save the output and linewidth
        self.output = output
        self.linewidth = linewidth

    def notify(self, test, state):
        """
        Called when a test or test fixture, identified by ``test``,
        transitions to ``state``.  The default implementation ignores
        state transitions by test fixtures or transitions to the
        RUNNING state.
        """

        # Are we interested in this test?
        if not test.istest() or state == RUNNING:
            return

        # Determine the name of the test
        name = str(test)

        # Determine the width of the test name field
        width = self.linewidth - len(state) - 1

        # Truncate the name, if necessary
        if len(name) > width:
            name = name[:width - 3] + '...'

        # Emit the status message
        print >>self.output, "%-*s %s" % (width, name, state)

    def result(self, result):
        """
        Called at the end of a test run to emit ``result`` information
        for a given test.  Called once for each result.  Should emit
        all exception and captured output information, if any.  Will
        also be called for results from test fixtures, in order to
        emit errors encountered while executing them.  The default
        implementation ignores results containing no messages.
        """

        # Helper for reporting output
        def out_msg(msg, hdr=None):
            # Output header information
            if hdr:
                print >>self.output, (hdr.center(self.linewidth) + "\n" +
                                      ('-' * self.linewidth))

            # Output exception information
            if msg.exc_type is not None:
                exc_hdr = ' Exception %s ' % msg.exc_type.__name__
                tb = ''.join(traceback.format_exception(msg.exc_type,
                                                        msg.exc_value,
                                                        msg.exc_tb))
                print >>self.output, exc_hdr.center(self.linewidth, '-')
                print >>self.output, tb.rstrip()

            # Format output data
            for name, desc, value in msg.captured:
                print >>self.output, (' %s ' % desc).center(self.linewidth,
                                                            '-')
                print >>self.output, value.rstrip()

            # Emit a closing line
            print >>self.output, '-' * self.linewidth

        # Skip results with no messages
        if len(result) == 0:
            return

        # Emit a banner for the result
        print >>self.output, ("\n" + ("=" * self.linewidth) + "\n" +
                              str(result.test).center(self.linewidth) + "\n" +
                              ("=" * self.linewidth))

        # Emit the data for each step
        if PRE in result:
            out_msg(result[PRE], 'Pre-test Fixture')
        if TEST in result:
            out_msg(result[TEST])
        if POST in result:
            out_msg(result[POST], 'Post-test Fixture')

    def summary(self, counts):
        """
        Called at the end of a test run to emit summary information
        about the run.  The ``counts`` argument is a dictionary
        containing the following keys:

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
        to dependencies.
        """

        # Emit summary data
        print >>self.output, ("%d tests run in %d max simultaneous threads" %
                              (counts['total'], counts['threads']))
        if counts[OK] > 0:
            unexp = ''
            if counts[UOK] > 0:
                unexp = ' (%d unexpected)' % counts[UOK]
            print >>self.output, ("  %d tests successful%s" %
                                  (counts[OK], unexp))
        if counts[SKIPPED] > 0:
            print >>self.output, "  %d tests skipped" % counts[SKIPPED]
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

            print >>self.output, ("  %d tests failed (%s)" %
                                  (total, ', '.join(bd)))


def run_tests(maxth=None, skip=lambda dt: dt.skip, output=DTestOutput()):
    """
    Run all defined tests.  The ``maxth`` argument, if an integer,
    indicates the maximum number of simultaneously executing threads
    that may be used.  The ``skip`` argument specifies a function
    which, when passed a test, returns True to indicate that that test
    should be skipped; by default, it returns the value of the
    ``skip`` attribute on the test, which may be set using the @skip
    decorator.  The ``output`` argument specifies an instance of
    DTestOutput, which is expected to implement notify(), result(),
    and summary() methods to generate the relevant output in the
    desired format; see the documentation for DTestOutput for more
    information.
    """

    # Let's begin by making sure we're monkey-patched
    monkey_patch()

    # Now, initialize the test queue...
    q = Queue(maxth, skip, output.notify)

    # Install the capture proxies...
    capture.install()

    # Run the tests
    results = q.run()

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

        output.result(r)

    # Emit summary data
    output.summary(cnt)
