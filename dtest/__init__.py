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
of a given set of exceptions (@raises()); marking that a test should
conclude within a given time limit (@timed()); requesting that a test
be executed multiple times (@repeat()); setting an alternate
parallelization strategy (@strategy()); and using the multithreaded
parallelization strategies (@parallel()).

Tests may be discovered using the explore() function, which returns an
instance of DTestQueue.  (This instance may be passed to other
invocation of explore(), to discover tests in multiple directories.)
Once tests have been discovered, a dependency graph may then be
generated using the DTestQueue.dot() method, or the test suite may be
executed by calling the DTestQueue.run().

It is possible to capture arbitrary forms of output by extending and
instantiating the Capturer class.  Note that standard output and
standard error are captured by default.  Capturing may be disabled for
a test run by passing a True ``debug`` argument to the
DTestQueue.run() method.

Tests themselves may be written using the ``assert`` statement, if
desired, but a number of utilities are available in the dtest.util
package for performing various common tests.  Additionally, a special
output stream, ``dtest.status``, is provided; this stream may be used
to emit status messages to inform the user of the status of a
long-running test.  (Additional properties and methods are available
on ``dtest.status`` for supporting this special stream within
newly-created threads.  The built-in parallelization strategies
already use this support.  For more information, see the documentation
for ``dtest.status.output``, ``dtest.status.test``, and
``dtest.status.setup()``.)

For complex testing behavior, generator test functions are possible.
These test functions should yield either a callable or a tuple.  If a
tuple is yielded, the first or second element must be a callable, and
the elements after the callable identify positional arguments, keyword
arguments, or both (in the order positional arguments as a sequence,
followed by keyword arguments as a dictionary).  If the callable is
the second element of the tuple, the first must be a string giving a
name for the test.  Note that yielded tests cannot have dependencies,
fixtures or any of the other DTest decorators; all such enhancements
must be attached to the generator function; on the other hand, it is
legal for the yielded callable to be a generator itself, which will be
treated identically to the top-level generator function.  Also note
that when the @repeat() decorator is applied to a generator test
function, each yielded function will be called the designated number
of times, but the generator itself will be called only once.

Note that both dtest and dtest.util are safe for use with "import *".
"""

from dtest.capture import Capturer
from dtest.constants import *
from dtest.exceptions import DTestException
from dtest.core import DTestQueue, DTestOutput, status, explore, main, \
    optparser, opts_to_args
from dtest.test import istest, nottest, isfixture, skip, failing, attr, \
    depends, raises, timed, repeat, strategy, parallel, DTestCase

__all__ = ['Capturer',
           'PRE', 'POST', 'TEST',
           'RUNNING', 'FAIL', 'XFAIL', 'ERROR', 'DEPFAIL', 'OK', 'UOK',
           'SKIPPED',
           'DTestException',
           'DTestQueue', 'DTestOutput', 'status', 'explore', 'main',
           'optparser', 'opts_to_args',
           'istest', 'nottest', 'isfixture', 'skip', 'failing', 'attr',
           'depends', 'raises', 'timed', 'repeat', 'strategy', 'parallel',
           'DTestCase']
