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

import dtest

# Need t_order
import tests


def setUp():
    # Make sure we're the third thing to have run
    assert len(tests.t_order) == 2, "Ordering error running test suite"
    assert tests.t_order[-1] == 'tests.ordering.setUp', \
        "Incorrect previous step"

    # Keep track of what has run
    tests.t_order.append('tests.ordering.test_order.setUp')


def tearDown():
    # Make sure we're the twelfth thing to have run
    assert len(tests.t_order) == 11, "Ordering error running test suite"
    assert tests.t_order[-1] == ('tests.ordering.test_order.'
                                 'OrderingTestCase.tearDownClass'), \
                                 "Incorrect previous step"

    # Keep track of what has run
    tests.t_order.append('tests.ordering.test_order.tearDown')


class OrderingTestCase(dtest.DTestCase):
    @staticmethod
    def setUpClass():
        # Make sure we're the fourth thing to have run
        assert len(tests.t_order) == 3, "Ordering error running test suite"
        assert tests.t_order[-1] == 'tests.ordering.test_order.setUp', \
            "Incorrect previous step"

        # Keep track of what has run
        tests.t_order.append('tests.ordering.test_order.'
                             'OrderingTestCase.setUpClass')

    @staticmethod
    def tearDownClass():
        # Make sure we're the eleventh thing to have run
        assert len(tests.t_order) == 10, "Ordering error running test suite"
        assert tests.t_order[-1] == ('tests.ordering.test_order.'
                                     'OrderingTestCase.tearDown'), \
                                     "Incorrect previous step"

        # Keep track of what has run
        tests.t_order.append('tests.ordering.test_order.'
                             'OrderingTestCase.tearDownClass')

    def setUp(self):
        # Make sure we're the fifth or eighth thing to have run
        assert len(tests.t_order) == 4 or len(tests.t_order) == 7, \
            "Ordering error running test suite"
        if len(tests.t_order) == 4:
            assert tests.t_order[-1] == ('tests.ordering.test_order.'
                                         'OrderingTestCase.setUpClass'), \
                                         "Incorrect previous step"
        else:
            assert tests.t_order[-1] == ('tests.ordering.test_order.'
                                         'OrderingTestCase.tearDown'), \
                                         "Incorrect previous step"

        # Keep track of what has run
        tests.t_order.append('tests.ordering.test_order.'
                             'OrderingTestCase.setUp')

    def tearDown(self):
        # Make sure we're the seventh or tenth thing to have run
        assert len(tests.t_order) == 6 or len(tests.t_order) == 9, \
            "Ordering error running test suite"
        if len(tests.t_order) == 6:
            assert tests.t_order[-1] == ('tests.ordering.test_order.'
                                         'OrderingTestCase.test1'), \
                                         "Incorrect previous step"
        else:
            assert tests.t_order[-1] == ('tests.ordering.test_order.'
                                         'OrderingTestCase.test2'), \
                                         "Incorrect previous step"

        # Keep track of what has run
        tests.t_order.append('tests.ordering.test_order.'
                             'OrderingTestCase.tearDown')

    def test1(self):
        # Make sure we're the sixth thing to have run
        assert len(tests.t_order) == 5, "Ordering error running test suite"
        assert tests.t_order[-1] == ('tests.ordering.test_order.'
                                     'OrderingTestCase.setUp'), \
                                     "Incorrect previous step"

        # Keep track of what has run
        tests.t_order.append('tests.ordering.test_order.'
                             'OrderingTestCase.test1')

    @dtest.depends(test1)
    def test2(self):
        # Make sure we're the ninth thing to have run
        assert len(tests.t_order) == 8, "Ordering error running test suite"
        assert tests.t_order[-1] == ('tests.ordering.test_order.'
                                     'OrderingTestCase.setUp'), \
                                     "Incorrect previous step"

        # Keep track of what has run
        tests.t_order.append('tests.ordering.test_order.'
                             'OrderingTestCase.test2')
