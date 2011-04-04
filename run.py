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
    def __init__(self, maxth, skip, notify):
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

    def spawn(self, tests, notify):
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
        # Walk through all the waiting tests; note the copy, to avoid
        # modifications to self.waiting from upsetting us
        self.spawn(self.waiting, notify)

        # Wait for all tests to finish
        if self.th_count > 0:
            self.th_event.wait()

        # For convenience, return the full list of results
        return [t.result for t in self.tests]

    def run_test(self, test, notify):
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
    # Emit summary data
    print "%d tests run" % counts['total']
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
