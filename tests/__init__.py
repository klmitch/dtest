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

t_order = []


def setUp():
    # Make sure we're the first thing to have run
    assert len(t_order) == 0, "Ordering error running test suite"

    # Keep track of what has run
    t_order.append('tests.setUp')


def tearDown():
    # Make sure we're the fourteenth thing to have run
    assert len(t_order) == 13, "Ordering error running test suite"
    assert t_order[-1] == 'tests.ordering.tearDown', "Incorrect previous step"

    # Keep track of what has run
    t_order.append('tests.tearDown')
