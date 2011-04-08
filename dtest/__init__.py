"""
===============================
Dependency-based Test Framework
===============================

The dtest package defines a dependency-based test framework similar to
the standard unittest in the Python standard library.  The primary
advantage of a dependency-based test framework is that it is easy to
run tests in multiple threads, making test runs faster because tests
are performed simultaneously.  It is also possible to ensure that some
tests are skipped if other tests fail, perhaps because the tests to be
skipped are dependent on the very functionality that has been shown to
be improperly implemented.  These dependencies are also used, under
the hood, to safely permit the running of test fixtures at class-,
module-, and package-levels, without worrying about multi-threading
issues.

The dtest framework provides a DTestCase class, similar to
unittest.TestCase.  There are also a number of decorators available,
to do such things as: marking a function or method as being (or not
being) a test (@istest and @nottest); marking a test to be skipped by
default (@skip); marking a test as having an expected failure
(@failing); setting arbitrary attributes on a test (@attr());
indicating that a test is dependent on other tests (@depends());
indicating that a test is expected to raise a given exception or one
of a given set of exceptions (@raises()); and marking that a test
should conclude within a given time limit (@timed()).

Once tests have been discovered, a dependency graph may be generated
using the dot() function, or the test suite may be executed by calling
run_tests().  It is also possible to capture arbitrary output by
extending and instantiating the Capturer class (note that standard
output and standard error are captured by default).

Tests may be written using the ``assert`` statement, if desired, but a
number of utilities are available in the dtest.util package for
performing various common tests.

Note that both dtest and dtest.util are safe for use with "import *".
"""

from dtest.capture import Capturer
from dtest.constants import *
from dtest.exceptions import DTestException
from dtest.core import DTestOutput, run, explore, main, \
    optparser, opts_to_args
from dtest.test import istest, nottest, skip, failing, attr, depends, \
    raises, timed, DTestCase, tests, dot

__all__ = ['Capturer',
           'PRE', 'POST', 'TEST',
           'RUNNING', 'FAIL', 'XFAIL', 'ERROR', 'DEPFAIL', 'OK', 'UOK',
           'SKIPPED',
           'DTestException',
           'DTestOutput', 'run', 'explore', 'main',
           'optparser', 'opts_to_args',
           'istest', 'nottest', 'skip', 'failing', 'attr', 'depends',
           'raises', 'timed', 'DTestCase', 'tests', 'dot']
