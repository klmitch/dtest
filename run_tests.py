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

import sys

import dtest
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
tests = dtest.explore(opts['directory'])

# Now, set up the dependency between tests.tearDown and our
# test_ordering() test
dtest.depends(sys.modules['tests'].tearDown)(test_ordering)

# Have to add test_ordering to tests
tests.add(test_ordering._dt_dtest)

# Implement the rest of dtest.main()
if not opts.get('dryrun', False):
    # Select the subset of options required
    subopts = {'skip': lambda dt: hasattr(dt, 'must_skip') and dt.must_skip}
    if 'maxth' in opts:
        subopts['maxth'] = opts['maxth']
    if 'output' in opts:
        subopts['output'] = opts['output']

    # Execute the tests
    result = dtest.run(tests, **subopts)
else:
    result = True

    # Print out the names of the tests
    print "Discovered tests:\n"
    for dt in tests:
        if dt.istest():
            print str(dt)

# Are we to dump the dependency graph?
if 'dotpath' in opts:
    with open(opts['dotpath'], 'w') as f:
        print >>f, dtest.dot(tests)

# All done!
sys.exit(result)
