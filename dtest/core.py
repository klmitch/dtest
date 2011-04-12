#!/usr/bin/python
#
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
Test Running
============

This module contains the run_test() function and the associated Queue
class, which together provide the functionality for executing tests in
a threaded manner while properly handling ordering implied by
dependencies.  Output is specified by passing an instance of
DTestOutput to run().

If this file is executed directly, the main() function--which first
calls explore(), then returns the result of run()--is called, and its
return value will be passed to sys.exit().  Command line arguments are
also available, and the module can be executed by passing "-m
dtest.core" to the Python interpreter.
"""

import imp
from optparse import OptionParser
import os
import os.path
import sys
import traceback

from eventlet import spawn_n, monkey_patch
from eventlet.event import Event
from eventlet.semaphore import Semaphore

from dtest import capture
from dtest.constants import *
from dtest.exceptions import DTestException
from dtest import test


DEF_LINEWIDTH = 78


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
            The maximum number of simultaneously executing threads
            which were utilized while running tests.

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

    def caught(self, exc_list):
        """
        Called after emitting summary data to report any exceptions
        encountered within the dtest framework itself while running
        the test.  The ``exc_list`` argument is a list of
        three-element tuples.  For each tuple, the first element is an
        exception type; the second element is the exception value; and
        the third element is a traceback object.  Under most
        circumstances, this function will not be called; if it is, the
        exception data reported should be sent back to the dtest
        framework developers.
        """

        # Emit exception data
        print >>self.output, "\nThe following exceptions were encountered:"
        for exc_type, exc_value, tb in exc_list:
            exc_hdr = ' Exception %s ' % exc_type.__name__
            tb = ''.join(traceback.format_exception(exc_type, exc_value, tb))
            print >>self.output, exc_hdr.center(self.linewidth, '-')
            print >>self.output, tb.rstrip()
        print >>self.output, '-' * self.linewidth
        print >>self.output, ("Please report the above errors to the "
                              "developers of the dtest framework.")

    def imports(self, exc_list):
        """
        Called by main() if import errors were encountered while
        discovering tests.  The ``exc_list`` argument is a list of
        tuples containing three elements: the first element is the
        full path to the file for which import was attempted; the
        second element is the module path for which import was
        attempted; and the third is a three-element tuple returned by
        sys.exc_info().
        """

        # Emit import error data
        print >>self.output, "The following import errors were encountered:"
        for path, pkgname, (exc_type, exc_value, tb) in exc_list:
            exc_hdr = ' %s (%s) ' % (os.path.relpath(path), pkgname)
            tb = ''.join(traceback.format_exception(exc_type, exc_value, tb))
            print >>self.output, exc_hdr.center(self.linewidth, '-')
            print >>self.output, tb.rstrip()
        print >>self.output, ('-' * self.linewidth) + "\n"


class DTestQueue(object):
    """
    DTestQueue
    ==========

    The DTestQueue class maintains a queue of tests waiting to be run.
    The constructor initializes the queue to an empty state and stores
    a maximum simultaneous thread count ``maxth`` (None means
    unlimited); a ``skip`` evaluation routine (defaults to testing the
    ``skip`` attribute of the test); and an instance of DTestOutput.
    The list of all tests in the queue is maintained in the ``tests``
    attribute; tests may be added to a queue with add_test() (for a
    single test) or add_tests() (for a sequence of tests).  The tests
    in the queue may be run by invoking the run() method.
    """

    def __init__(self, maxth=None, skip=lambda dt: dt.skip,
                 output=DTestOutput()):
        """
        Initialize a DTestQueue.  The ``maxth`` argument must be
        either None or an integer specifying the maximum number of
        simultaneous threads permitted.  The ``skip`` arguments is
        function references; it should take a test and return True if
        the test should be skipped.  The ``output`` argument should be
        an instance of DTestOutput containing a notify() method, which
        takes a test and the state to which it is transitioning, and
        may use that information to emit a test result.  Note that the
        notify() method will receive state transitions to the RUNNING
        state, as well as state transitions for test fixtures; callers
        may find the DTestBase.istest() method useful for
        differentiating between regular tests and test fixtures for
        reporting purposes.
        """

        # Save our maximum thread count
        if maxth is None:
            self.sem = None
        else:
            self.sem = Semaphore(maxth)

        # Need to remember the skip routine
        self.skip = skip

        # Also remember the output
        self.output = output

        # Initialize the lists of tests
        self.tests = set()
        self.waiting = None

        # Need a lock for the waiting list
        self.waitlock = Semaphore()

        # Set up some statistics...
        self.th_count = 0
        self.th_event = Event()
        self.th_simul = 0
        self.th_max = 0

        # Place to keep any exceptions we encounter within dtest
        # itself
        self.caught = []

        # We're not yet running
        self.running = False

    def add_test(self, tst):
        """
        Add a test ``tst`` to the queue.  Tests can be added multiple
        times, but the test will only be run once.
        """

        # Can't add a test if the queue is running
        if self.running:
            raise DTestException("Cannot add tests to a running queue.")

        # First we need to get the test object
        dt = test._gettest(tst)

        # Add it to the set of tests
        self.tests.add(dt)

    def add_tests(self, tests):
        """
        Add a sequence of tests ``tests`` to the queue.  Tests can be
        added multiple times, but the test will only be run once.
        """

        # Can't add a test if the queue is running
        if self.running:
            raise DTestException("Cannot add tests to a running queue.")

        # Run add_test() in a loop
        for tst in tests:
            self.add_test(tst)

    def run(self):
        """
        Runs all tests that have been queued up.  Does not return
        until all tests have been run.  Causes test results and
        summary data to be emitted using the ``output`` object
        registered when the queue was initialized.  Note that if
        dependency cycles are present, this function may hang.
        """

        # Can't run an already running queue
        if self.running:
            raise DTestException("Queue is already running.")

        # OK, put ourselves into the running state
        self.running = True

        # Must begin by ensuring we're monkey-patched
        monkey_patch()

        # OK, let's prepare all the tests...
        for dt in self.tests:
            dt._prepare()

        # Second pass--determine which tests are being skipped
        waiting = []
        for dt in self.tests:
            # Do we skip this one?
            willskip = self.skip(dt)

            # If not, check if it's a fixture with no dependencies...
            if not willskip and not dt.istest():
                if dt._partner is None:
                    if len(dt._revdeps) == 0:
                        willskip = True
                else:
                    if len(dt._revdeps) == 1:
                        willskip = True

            # OK, mark it skipped if we're skipping
            if willskip:
                dt._skipped(self.output)
            else:
                waiting.append(dt)

        # OK, last pass: generate list of waiting tests; have to
        # filter out SKIPPED tests
        self.waiting = set([dt for dt in self.tests if dt.state != SKIPPED])

        # Install the capture proxies...
        capture.install()

        # Spawn waiting tests
        self._spawn(self.waiting)

        # Wait for all tests to finish
        if self.th_count > 0:
            self.th_event.wait()

        # OK, uninstall the capture proxies
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
            'threads': self.th_max,
            }
        for t in self.tests:
            # Get the result object
            r = t.result

            # Update the counts
            cnt[r.state] += int(r.test)
            cnt['total'] += int(r.test)

            # Special case update for unexpected OKs and expected failures
            if r.state == UOK:
                cnt[OK] += int(r.test)
            elif r.state == XFAIL:
                cnt[FAIL] += int(r.test)

            self.output.result(r)

        # Emit summary data
        self.output.summary(cnt)

        # If we saw exceptions, emit data about them
        if self.caught:
            self.output.caught(self.caught)

        # We're done running; re-running should be legal
        self.running = False

        # Return False if there were any unexpected failures or errors
        if cnt[FAIL] > 0 or cnt[ERROR] > 0 or cnt[DEPFAIL] > 0:
            return False

        # All tests passed!
        return True

    def _spawn(self, tests):
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
            dt = tests.pop(0)

            with self.waitlock:
                # Is test waiting?
                if dt not in self.waiting:
                    continue

                # OK, check dependencies
                elif dt._depcheck(self.output):
                    # No longer waiting
                    self.waiting.remove(dt)

                    # Spawn the test
                    self.th_count += 1
                    spawn_n(self._run_test, dt)

                # Dependencies failed; check if state changed and add
                # its dependents if so
                elif dt.state is not None:
                    # No longer waiting
                    self.waiting.remove(dt)

                    # Check all its dependents.  Note--not trying to
                    # remove duplicates, because some formerly
                    # unrunnable tests may now be runnable because of
                    # the state change
                    tests.extend(list(dt.dependents))

    def _run_test(self, dt):
        """
        Execute ``dt``.  This method is meant to be run in a new
        thread.

        Once a test is complete, the thread's dependents will be
        passed back to the spawn() method, in order to pick up and
        execute any tests that are now ready for execution.
        """

        # Acquire the thread semaphore
        if self.sem is not None:
            self.sem.acquire()

        # Increment the simultaneous thread count
        self.th_simul += 1
        if self.th_simul > self.th_max:
            self.th_max = self.th_simul

        # Execute the test
        try:
            dt._run(self.output)
        except:
            # Add the exception to the caught list
            self.caught.append(sys.exc_info())

            # Manually transition the test to the ERROR state
            dt._result._transition(ERROR)

        # Now, walk through its dependents and check readiness
        self._spawn(dt.dependents)

        # All right, we're done; release the semaphore
        if self.sem is not None:
            self.sem.release()

        # Decrement the thread count
        self.th_simul -= 1
        self.th_count -= 1

        # If thread count is now 0, signal the event
        with self.waitlock:
            if len(self.waiting) == 0 and self.th_count == 0:
                self.th_event.send()


def explore(directory=None, queue=None):
    """
    Explore ``directory`` (by default, the current working directory)
    for all modules matching the test regular expression and import
    them.  Each module imported will be further explored for tests.
    This function may be used to discover all registered tests prior
    to running them.  Returns a tuple; the first element is a set of
    all discovered tests, and the second element is a list of tuples
    containing information about all ImportError exceptions caught.
    The elements of this exception information tuple are, in order, a
    path, the module name, and a tuple of exception information as
    returned by sys.exc_info().
    """

    # If no queue is provided, allocate one with the default settings
    if queue is None:
        queue = DTestQueue()

    # Set of all discovered tests
    tests = set()

    # List of all import exceptions
    caught = []

    # Need the allowable suffixes
    suffixes = [sfx[0] for sfx in imp.get_suffixes()]

    # Obtain the canonical directory name
    if directory is None:
        directory = os.getcwd()
    else:
        directory = os.path.abspath(directory)

    # This is the directory we'll be searching
    searchdir = directory

    # But does it have an __init__.py?
    pkgpath = None
    for sfx in suffixes:
        if os.path.exists(os.path.join(directory, '__init__' + sfx)):
            # Refigure the directory
            directory, pkgpath = os.path.split(directory)

    # Now, let's jigger the import path
    tmppath = sys.path
    sys.path = [directory] + sys.path

    # Import the package, if necessary
    if pkgpath is not None:
        try:
            __import__(pkgpath)
            test.visit_mod(sys.modules[pkgpath], tests)
        except ImportError:
            # Remember the exception we got
            caught.append((searchdir, pkgpath, sys.exc_info()))

    # Having done that, we now begin walking the directory tree
    for root, dirs, files in os.walk(searchdir):
        # Let's determine the module's package path
        if root == directory:
            pkgpath = ''
        else:
            sep = root[len(directory)]
            subdir = root[len(directory) + 1:]
            pkgpath = '.'.join(subdir.split(sep)) + '.'

        # Start with files...
        for f in files:
            # Does it match the testRE?
            if not test.testRE.match(f):
                continue

            # Only interested in files we can load
            for sfx in suffixes:
                if f.endswith(sfx):
                    modname = f[:-len(sfx)]
                    break
            else:
                # Can't load it, so skip it
                continue

            # Determine the module's full path
            fullmodname = pkgpath + modname

            # Let's try to import it
            try:
                __import__(fullmodname)
                mod = sys.modules[fullmodname]
            except ImportError:
                # Remember the exception we got
                caught.append((os.path.join(root, f), fullmodname,
                               sys.exc_info()))

                # Can't import it, so move on
                continue

            test.visit_mod(mod, tests)

        # Now we want to determine which subdirectories are packages;
        # they'll contain __init__.py
        subdirs = []
        for d in dirs:
            # Only interested in directories which contain __init__.py
            for sfx in suffixes:
                if os.path.exists(os.path.join(root, d, '__init__' + sfx)):
                    break
            else:
                # Not a package, so skip it
                continue

            # Does it match the testRE?
            if not test.testRE.match(d):
                # No, but let's continue exploring under it
                subdirs.append(d)
                continue

            # Determine the package's full path
            fullpkgname = pkgpath + d

            # Let's try to import it
            try:
                __import__(fullpkgname)
                pkg = sys.modules[fullpkgname]
            except ImportError:
                # Remember the exception we got
                caught.append((os.path.join(root, d), fullpkgname,
                               sys.exc_info()))

                # Can't import it, no point exploring under it
                continue

            test.visit_mod(pkg, tests)

            # We also want to explore under it
            subdirs.append(d)

        # Make sure to set up our pruned subdirectory list
        dirs[:] = subdirs

    # We have finished loading all tests; restore the original import
    # path
    sys.path = tmppath

    # Add the discovered tests to the queue
    queue.add_tests(tests)

    # Output the import errors, if any
    if caught:
        queue.output.imports(caught)

    # Return the queue
    return queue


def main(directory=None, maxth=None, skip=lambda dt: dt.skip,
         output=DTestOutput(), dryrun=False, dotpath=None):
    """
    Discover tests under ``directory`` (by default, the current
    directory), then run the tests under control of ``maxth``,
    ``skip``, and ``output`` (see the documentation for the run()
    function for more information on these three parameters).  Returns
    True if all tests (with the exclusion of expected failures)
    passed, False if a failure or error was encountered.
    """

    # First, allocate a queue
    queue = DTestQueue(maxth, skip, output)

    # Next, discover the tests of interest
    explore(directory, queue)

    # Is this a dry run?
    if not dryrun:
        # Nope, execute the tests
        result = queue.run()
    else:
        result = True

        # Print out the names of the tests
        print "Discovered tests:\n"
        for dt in queue.tests:
            if dt.istest():
                print str(dt)

    # Are we to dump the dependency graph?
    if dotpath is not None:
        with open(dotpath, 'w') as f:
            print >>f, test.dot(queue.tests)

    # Now, let's return the result of the test run
    return result


def optparser(*args, **kwargs):
    """
    Builds and returns an option parser with the default options
    recognized by the dtest framework.  All arguments are passed to
    the OptionParser constructor.
    """

    # Set up an OptionParser
    op = OptionParser(*args, **kwargs)

    # Set up our default options
    op.add_option("-d", "--directory",
                  action="store", type="string", dest="directory",
                  help="The directory to search for tests to run.")
    op.add_option("-m", "--max-threads",
                  action="store", type="int", dest="maxth",
                  help="The maximum number of tests to run simultaneously; if "
                  "not specified, an unlimited number of tests may run "
                  "simultaneously.")
    op.add_option("-s", "--skip",
                  action="store", type="string", dest="skip",
                  help="Specifies a rule to control which tests are skipped.  "
                  "If value contains '=', tests having an attribute with the "
                  "given value will be skipped.  If value does not contain "
                  "'=', tests that have the attribute will be skipped.")
    op.add_option("--no-skip",
                  action="store_true", dest="noskip",
                  help="Specifies that no test should be skipped.  Overrides "
                  "--skip, if specified.")
    op.add_option("-n", "--dry-run",
                  action="store_true", dest="dryrun",
                  help="Performs a dry run.  After discovering all tests, "
                  "the list of tests is printed to standard output.")
    op.add_option("--dot",
                  action="store", type="string", dest="dotpath",
                  help="After running tests, a text representation of the "
                  "dependency graph is placed in the indicated file.  This "
                  "file may then be passed to the \"dot\" tool of the "
                  "GraphViz package to visualize the dependency graph.  "
                  "This option may be used in combination with \"-n\".")

    # Return the OptionParser
    return op


def opts_to_args(options):
    """
    Converts an options object--as returned by calling the
    parse_args() method of the return value from the optparser()
    function--into a dictionary that can be fed to the main() function
    to execute the desired test operation.
    """

    # Build the arguments dictionary
    args = {}

    # Start with the skip-related arguments
    if options.noskip is True:
        args['skip'] = lambda dt: False
    elif options.skip is not None:
        if '=' in options.skip:
            k, v = options.skip.split('=', 1)
            args['skip'] = lambda dt: getattr(dt, k, None) == v
        else:
            args['skip'] = lambda dt: hasattr(dt, options.skip)

    # Now look at max threads
    if options.maxth is not None:
        args['maxth'] = options.maxth

    # Are we doing a dry run?
    if options.dryrun is True:
        args['dryrun'] = True

    # How about dumping the dependency graph?
    if options.dotpath is not None:
        args['dotpath'] = options.dotpath

    # And, finally, directory
    if options.directory is not None:
        args['directory'] = options.directory

    # Return the built arguments object
    return args


if __name__ == '__main__':
    # Obtain the options
    opts = optparser(usage="%prog [options]")

    # Process command-line arguments
    (options, args) = opts.parse_args()

    # Execute the test suite
    sys.exit(main(**opts_to_args(options)))
