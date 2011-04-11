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

# Need t_order
import tests


def setUp():
    # Make sure we're the second thing to have run
    assert len(tests.t_order) == 1, "Ordering error running test suite"
    assert tests.t_order[-1] == 'tests.setUp', "Incorrect previous step"

    # Keep track of what has run
    tests.t_order.append('tests.ordering.setUp')


def tearDown():
    # Make sure we're the thirteenth thing to have run
    assert len(tests.t_order) == 12, "Ordering error running test suite"
    assert tests.t_order[-1] == 'tests.ordering.test_order.tearDown', \
        "Incorrect previous step"

    # Keep track of what has run
    tests.t_order.append('tests.ordering.tearDown')
