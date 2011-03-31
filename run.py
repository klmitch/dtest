from eventlet import spawn_n
from eventlet.semaphore import Semaphore

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
        self.waiting = set([dt for dt in tests if dt.state != SKIPPED])

    def check(self, test):
        # Is test waiting?
        if test not in self.waiting:
            return False

        # OK, check dependencies
        elif test._depcheck():
            self.waiting.remove(test)
            return True

        # Dependencies failed; check if state changed (i.e., to
        # DEPFAILED)
        elif test.state is not None:
            self.waiting.remove(test)

        # Test isn't ready to run
        return False

    def run(self):
        # Walk through all the waiting tests; note the copy, to avoid
        # modifications to self.waiting from upsetting us
        for test in self.waiting:
            if self.check(test):
                spawn_n(self.run_test, test)

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
        for dep in test.dependents:
            if self.check(dep):
                spawn_n(self.run_test, dep)

        # All right, we're done; release the semaphore
        if self.sem is not None:
            self.sem.release()
