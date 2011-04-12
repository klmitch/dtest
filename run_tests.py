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


exp_order = [
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
    ]

required = [
    'tests.explore.a_test',
    'tests.explore.test_discovered',
    'tests.explore.test_pkg.a_test',
    'tests.explore.test_pkg.test_discovered',
    'tests.explore.pkg_impl.a_test',
    'tests.explore.pkg_impl.test_discovered',
    'tests.explore.pkg_impl.test_impl.a_test',
    'tests.explore.pkg_impl.test_impl.test_discovered',
    ]

prohibited = [
    'tests.explore.test_not',
    'tests.explore.pkg.a_test',
    'tests.explore.pkg.test_not',
    'tests.explore.pkg.test_discovered',
    'tests.explore.pkg.nottest.a_test',
    'tests.explore.pkg.nottest.test_not',
    'tests.explore.pkg.nottest.test_discovered',
    'tests.explore.notpkg.a_test',
    'tests.explore.notpkg.test_not',
    'tests.explore.notpkg.test_discovered',
    'tests.explore.test_pkg.test_not',
    'tests.explore.test_notpkg.a_test',
    'tests.explore.test_notpkg.test_not',
    'tests.explore.test_notpkg.test_discovered',
    'tests.explore.pkg_impl.test_not',
    'tests.explore.pkg_impl.test_impl.test_not',
    ]


@dtest.istest
def test_ordering():
    # Look up t_order and make sure it's right
    t_order = sys.modules['tests'].t_order
    util.assert_list_equal(t_order, exp_order)


@dtest.istest
def test_discovery():
    # Get the list of test names
    tnames = set([str(t) for t in queue.tests])

    # Now go through the required list and make sure all those tests
    # are present
    for t in required:
        assert t in tnames, "Required test %r not discovered" % t

    # And similarly for the prohibited list
    for t in prohibited:
        assert t not in tnames, "Prohibited test %r discovered" % t


@dtest.istest
def test_partner_setUp():
    # Look up setUpRun and make sure it's right
    setUpRun = sys.modules['tests.test_partner'].setUpRun
    util.assert_false(setUpRun)


@dtest.istest
def test_partner_tearDown():
    # Look up tearDownRun and make sure it's right
    tearDownRun = sys.modules['tests.test_partner'].tearDownRun
    util.assert_false(tearDownRun)


# Start by processing the command-line arguments
(options, args) = dtest.optparser(usage="%prog [options]").parse_args()

# Get the options
opts = dtest.opts_to_args(options)

# If directory isn't set, use "tests"
if 'directory' not in opts:
    opts['directory'] = 'tests'

# Need to allocate a queue; select some suboptions for the task
subopts = {'skip': lambda dt: hasattr(dt, 'must_skip') and dt.must_skip}
if 'maxth' in opts:
    subopts['maxth'] = opts['maxth']
if 'output' in opts:
    subopts['output'] = opts['output']
queue = dtest.DTestQueue(**subopts)

# OK, we need to do the explore
dtest.explore(opts['directory'], queue)

# Now, set up the dependency between tests.tearDown and our
# test_ordering() test and the test_partner_*() tests
dtest.depends(sys.modules['tests'].tearDown)(test_ordering)
dtest.depends(sys.modules['tests'].tearDown)(test_partner_setUp)
dtest.depends(sys.modules['tests'].tearDown)(test_partner_tearDown)

# Have to add local tests to tests set
queue.add_test(test_ordering)
queue.add_test(test_discovery)
queue.add_test(test_partner_setUp)
queue.add_test(test_partner_tearDown)

# Implement the rest of dtest.main()
if not opts.get('dryrun', False):
    # Execute the tests
    result = queue.run()
else:
    result = True

    # Print out the names of the tests
    print "Discovered tests:\n"
    for dt in queue.tests:
        if dt.istest():
            print str(dt)

# Are we to dump the dependency graph?
if 'dotpath' in opts:
    with open(opts['dotpath'], 'w') as f:
        print >>f, dtest.dot(queue.tests)

# All done!
sys.exit(result)
