#!/usr/bin/python

import sys

import dtest
from dtest import test
from dtest import util


def test_ordering():
    # Look up t_order and make sure it's right
    t_order = sys.modules['tests'].t_order
    util.assert_list_equal(t_order, [
            'tests.setUp',
            'tests.ordering.setUp',
            'tests.ordering.test_order.setUp',
            'tests.ordering.test_order.OrderingTestCase.setUpClass',
            'tests.ordering.test_order.OrderingTestCase.setUp',
            'tests.ordering.test_order.OrderingTestCase.test1',
            'tests.ordering.test_order.OrderingTestCase.tearDown',
            'tests.ordering.test_order.OrderingTestCase.setUp',
            'tests.ordering.test_order.OrderingTestCase.test2',
            'tests.ordering.test_order.OrderingTestCase.tearDown',
            'tests.ordering.test_order.OrderingTestCase.tearDownClass',
            'tests.ordering.test_order.tearDown',
            'tests.ordering.tearDown',
            'tests.tearDown',
            ])


# Start by processing the command-line arguments
(options, args) = dtest.optparser(usage="%prog [options]").parse_args()

# Get the options
opts = dtest.opts_to_args(options)

# If directory isn't set, use "tests"
if 'directory' not in opts:
    opts['directory'] = 'tests'

# OK, we need to do the explore
dtest.explore(opts['directory'])

# Now, set up the dependency between tests.tearDown and our
# test_ordering() test
dtest.depends(sys.modules['tests'].tearDown)(test_ordering)

# Implement the rest of dtest.main()
if not opts.get('dryrun', False):
    # Select the subset of options required
    subopts = {}
    if 'maxth' in opts:
        subopts['maxth'] = opts['maxth']
    if 'skip' in opts:
        subopts['skip'] = opts['skip']
    if 'output' in opts:
        subopts['output'] = opts['output']

    # Execute the tests
    result = dtest.run(**subopts)
else:
    result = True

    # Print out the names of the tests
    print "Discovered tests:\n"
    for dt in test.DTestBase.tests():
        if dt.istest():
            print str(dt)

# Are we to dump the dependency graph?
if 'dotpath' in opts:
    with open(opts['dotpath'], 'w') as f:
        print >>f, dtest.dot()

# All done!
sys.exit(result)
