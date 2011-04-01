from eventlet import spawn_n
from eventlet.event import Event
from eventlet.semaphore import Semaphore

from dtest.constants import *
from dtest import test


class Queue(object):
    def __init__(self, maxth=None, skip=lambda dt: dt._skip):
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
            # Do we skip this one?
            if skip(dt):
                dt._skipped()
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

    def spawn(self, tests):
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
                elif test._depcheck():
                    # No longer waiting
                    self.waiting.remove(test)

                    # Spawn the test
                    self.th_count += 1
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
        # Walk through all the waiting tests; note the copy, to avoid
        # modifications to self.waiting from upsetting us
        self.spawn(self.waiting)

        # Wait for all tests to finish
        if self.th_count > 0:
            self.th_event.wait()

        # For convenience, return the full list of tests, which will
        # be searched for results
        return self.tests

    def run_test(self, test):
        # Acquire the semaphore
        if self.sem is not None:
            self.sem.acquire()

        # Set up arguments for the test
        args = []
        if test.class_ is not None:
            # Need self
            args.append(test.class_())

        # Execute the test
        test(*args)

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
