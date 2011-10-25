========================================
Dependency-based Threaded Test Framework
========================================

The DTest framework is a testing framework, similar to the standard
``unittest`` package provided by Python.  The value-add for DTest,
however, is that test execution is threaded, through use of the
``eventlet`` package.  The DTest package also provides the concept of
"dependencies" between tests and test fixtures--thus the "D" in
"DTest"--which ensure that tests don't run until the matching set up
test fixtures have completed, and that the tear down test fixtures
don't run until all the associated tests have completed.  Dependencies
may also be used to ensure that tests requiring the availability of
certain functionality don't run if the tests of that specific
functionality fail.

Writing Tests
=============

The simplest test programs are simple functions with names beginning
with "test," located in Python source files whose names also begin
with "test."  It is not even necessary to import any portion of the
DTest framework.  If tests are collected in classes, however, or if
use of the more advanced features of DTest is desired, a simple ``from
dtest import *`` is necessary.  This makes available the ``DTestCase``
class--which should be extended by all classes containing tests--as
well as such decorators as ``@skip`` and ``@nottest``.

Tests may be performed using the standard Python ``assert`` statement;
however, a number of utility routines are available in the
``dtest.util`` module (also safe for ``import *``).  Many of these
utility routines have names similar to methods of
``unittest.TestCase``--e.g., ``dtest.util.assert_dict_equal()`` is
analogous to ``unittest.TestCase.assertDictEqual()``.

Test Fixtures
=============

The DTest framework supports test fixtures--set up and tear down
functions--at the class, module, and package level.  Package-level
fixtures consist of functions named ``setUp()`` and ``tearDown()``
contained within "__init__.py" files; similarly, module-level fixtures
consist of functions samed ``setUp()`` and ``tearDown()`` within
modules containing test functions and classes of test methods.  At the
class level, classes may contain ``setUpClass()`` and
``tearDownClass()`` class methods (or static methods), which may
perform set up and tear down for each class.  In all cases, the
``setUp()`` functions and the ``setUpClass()`` method are executed
before any of the tests within the same scope; similarly, after all
the tests at a given scope have executed, the corresponding
``tearDownClass()`` method and ``tearDown()`` functions are executed.

The DTest framework also supports per-test ``setUp()`` and
``tearDown()`` functions or methods, which are run before and after
each associated test.  For classes containing tests, each test
automatically has the setUp() and tearDown() methods of the class
associated with them; however, for all tests, these fixtures can be
explicitly set (or overridden from the class default).  Consider the
following example::

    @istest
    def test_something():
        # Test something here
        pass

    @test_something.setUp
    def something_setup():
        # Get everything set up ready to go...
        pass

    @test_something.tearDown
    def something_teardown():
        # Clean up after ourselves
        pass

In this example, a DTest decorator (other than ``@nottest``) is
necessary preceding ``test_something()``; here we used ``@istest``,
but any other available DTest decorator could be used here.  This
makes the ``@test_something.setUp`` and ``@test_something.tearDown``
decorators available.  (For something analogous in the standard
Python, check out the built-in ``@property`` decorator.)

Test Resources
==============

Many test suites use test fixtures to set up temporary resources
needed for a particular test.  For instance, it's not uncommon for a
fixture to set up a utility object, such as a server client, which
could be reused by other tests.  The DTest framework provides an
alternative means of setting up such objects: test resources.

A test resource is any single object that may be required by a given
test.  To create one, set up a class extending the ``Resource`` class
and implement the ``setUp()`` method on the class (and, optionally,
the ``tearDown()`` method).  There are two additional class attributes
that can be set.  The first is ``oneshot``: if set to True, the
resource returned by ``setUp()`` will only be used once, then
discarded.  The second is ``dirtymeths``, which should contain a list
of methods which, when called, will cause the object to become
"dirty", causing it to be discarded after the test.  (Setting or
deleting object attributes will also cause the object to be marked as
"dirty".)

To mark that a test requires a particular resource, use the
``@require()`` decorator; this decorator takes keyword arguments,
where the keys will be taken as the names of arguments to the test,
and the values must be instances of subclasses of ``Resource``.  When
the test is run, DTest will create the actual resource objects and
pass them to the test as keyword arguments.  As long as the object
does not become dirty, it will be reused for subsequent tests, subject
to threading constraints (resource objects may only be used by one
thread at a time).

Resource Limitations
--------------------

Resources are subject to one limitation: the object actually passed to
the test is a proxy object which delegates attribute accesses to the
actual object allocated by the ``setUp()`` method.  Because of
optimizations within Python itself, it is not possible for this proxy
object to properly delegate special methods, such as ``__getitem__()``
or ``__add__()``.  Because of this, it is possible to retrieve the
true resource object, using the ``getobject()`` function.  Because
this removes the ability of the resources system to determine if the
resource becomes dirty, the ``dirty()`` and ``clean()`` functions are
also provided.  Finally, to prevent an access from marking the object
as dirty, the ``cleanaccess()`` function can be used in conjunction
with the ``with`` statement like so::

    with cleanaccess(resource):
        resource.attribute = "some value"

Without the ``with`` statement, this attribute setting would cause the
resource to be marked as dirty, but the ``with`` inhibits this.  Note
that it is legal to nest calls to ``cleanaccess()``, if necessary.

Resource Options
----------------

Resources may be specified with options, which should be
string-coercible constants.  Any positional or keyword arguments
passed to the ``Resource`` constructor will be saved and passed to the
``setUp()`` method when a resource must be constructed.  In addition,
the resource caching mechanism uses these options to ensure that a
test is only passed resources with matching options.

Optional ``tearDown()``
-----------------------

If some special cleanup is needed for a resource, implement the
``tearDown()`` method on your ``Resource`` subclass.  It should take
two arguments: the object that was returned by ``setUp()``, and the
status of the test.  For most resources, unless a test renders them
dirty, the status will be ``None``, and ``tearDown()`` will be called
after all tests have run to completion; however, for resources which
have ``oneshot`` set to True, the status should never be ``None``.
One possible use case for this is a test which uses temporary files,
which should be cleaned up after the test passes; should the test
fail, it may be useful to leave the temporary file around for
debugging purposes.

Running Tests
=============

Running tests using the DTest framework is fairly straight-forward.  A
script called ``run-dtests`` is available.  By default, the current
directory is scanned for all modules or packages whose names begin
with "test"; the search also recurses down through all packages.  (A
"package" is defined as a directory containing "__init__.py".)  Once
all tests are discovered, they are then executed, and the results of
the tests emitted to standard output.

Several command-line options are available for controlling the
behavior of ``run-dtests``.  For instance, the "--no-skip" option will
cause ``run-dtests`` to run all tests, even those decorated with the
``@skip`` decorator, and the "-d" option causes ``run-dtests`` to
search a specific directory, rather than the current directory.  For a
full list of options, use the "-h" or "--help" option.

Running ``run-dtests`` from the command line is not the only way to
run tests, however.  The ``run-dtests`` script is a very simple script
that parses command-line options (using the ``OptionParser``
constructed by the ``dtest.optparser()`` function), converts those
options into a set of keyword arguments (using
``dtest.opts_to_args()``), then passes those keyword arguments to the
``dtest.main()`` function.  Users can use these functions to build the
same functionality with user-specific extensions, such as providing an
alternate DTestOutput instance to control how test results are
displayed, or providing an alternate method for controlling which
tests are skipped.  See the documentation strings for these functions
and classes for more information.
