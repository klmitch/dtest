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

from dtest import *
from dtest.util import *


@repeat(2)
def test_multi():
    # Set up a list to record executions
    recorded = []

    # Now, define an inner function
    def inner(*args, **kwargs):
        # Place the arguments into the recorded list
        recorded.append((args, kwargs))

    # Now, yield the inner function once...
    yield ('inner1', inner, (1,), dict(kw=1))

    # Yield it again
    yield ('inner2', inner, (2,), dict(kw=2))

    # Now, check if recorded has what we expect
    assert_equal(len(recorded), 4)
    assert_tuple_equal(recorded[0][0], (1,))
    assert_dict_equal(recorded[0][1], dict(kw=1))
    assert_tuple_equal(recorded[1][0], (1,))
    assert_dict_equal(recorded[1][1], dict(kw=1))
    assert_tuple_equal(recorded[2][0], (2,))
    assert_dict_equal(recorded[2][1], dict(kw=2))
    assert_tuple_equal(recorded[3][0], (2,))
    assert_dict_equal(recorded[3][1], dict(kw=2))
