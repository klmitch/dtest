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
from dtest.strategy import SerialStrategy, UnlimitedParallelStrategy, \
    LimitedParallelStrategy
from dtest.test import DTestFixture
from dtest.util import *


class TestThrowaway(DTestCase):
    def test_fordep(self):
        pass


@skip
def test_skip():
    pass


@failing
def test_failing():
    assert False


@attr(attr1=1, attr2=2)
def test_attr():
    pass


@depends(test_skip, test_attr, TestThrowaway.test_fordep)
def test_depends():
    pass


class DecoratorTestException(Exception):
    pass


@raises(DecoratorTestException)
def test_raises():
    raise DecoratorTestException()


@timed(1)
def test_timed():
    pass


@repeat(2)
def test_repeat():
    pass


@parallel
def test_parallel():
    pass


@parallel(2)
def test_parallel_limited():
    pass


class TestDecorators(DTestCase):
    @depends(test_timed)
    @classmethod
    def setUpClass(cls):
        pass

    @istest
    def skip(self):
        # Verify that skip is true...
        assert_true(test_skip._dt_dtest.skip)

        # Verify that it's false on something else
        assert_false(test_failing._dt_dtest.skip)

    @istest
    def failing(self):
        # Verify that failing is true...
        assert_true(test_failing._dt_dtest.failing)

        # Verify that it's false on something else
        assert_false(test_skip._dt_dtest.failing)

    @istest
    def attr(self):
        # Verify that the attributes are set as expected
        assert_equal(test_attr._dt_dtest.attr1, 1)
        assert_equal(test_attr._dt_dtest.attr2, 2)

    @istest
    def depends(self):
        # Part 1: Verify that test_depends() is dependent on
        # test_skip() and test_attr()
        assert_in(test_skip._dt_dtest, test_depends._dt_dtest.dependencies)
        assert_in(test_attr._dt_dtest, test_depends._dt_dtest.dependencies)
        assert_in(TestThrowaway.test_fordep._dt_dtest,
                  test_depends._dt_dtest.dependencies)

        # Part 2: Verify that test_depends() is in the depedents set
        # of test_skip() and test_attr()
        assert_in(test_depends._dt_dtest, test_skip._dt_dtest.dependents)
        assert_in(test_depends._dt_dtest, test_attr._dt_dtest.dependents)
        assert_in(test_depends._dt_dtest,
                  TestThrowaway.test_fordep._dt_dtest.dependents)

    @istest
    def raises(self):
        # Verify that the set of expected exceptions is as expected
        assert_set_equal(test_raises._dt_dtest.raises,
                         set([DecoratorTestException]))

        # Verify that it's the empty set on something else
        assert_set_equal(test_timed._dt_dtest.raises, set())

    @istest
    def timed(self):
        # Verify that the timeout is set properly
        assert_equal(test_timed._dt_dtest.timeout, 1)

        # Verify that it's None on something else
        assert_is_none(test_raises._dt_dtest.timeout)

    @istest
    def repeat(self):
        # Verify that the repeat count is set properly
        assert_equal(test_repeat._dt_dtest.repeat, 2)

        # Verify that it's 1 on something else
        assert_equal(test_timed._dt_dtest.repeat, 1)

    @istest
    def parallel(self):
        # Verify that the strategy is set properly
        assert_is_instance(test_parallel._dt_dtest._strategy,
                           UnlimitedParallelStrategy)

        # Verify that it's SerialStrategy on something else
        assert_is_instance(test_timed._dt_dtest._strategy, SerialStrategy)

    @istest
    def parallel_limited(self):
        # Verify that the strategy is set properly
        assert_is_instance(test_parallel_limited._dt_dtest._strategy,
                           LimitedParallelStrategy)

        # Verify that the limit is set properly
        assert_equal(test_parallel_limited._dt_dtest._strategy.limit, 2)

    @istest
    def isfixture(self):
        # Verify that setUpClass has a fixture associated with it
        assert_is_instance(self.setUpClass._dt_dtest, DTestFixture)

        # Verify that we have the appropriate dependencies
        assert_in(test_timed._dt_dtest, self.setUpClass._dt_dtest.dependencies)

        # Verify that we have the appropriate dependents
        assert_in(self.setUpClass._dt_dtest, test_timed._dt_dtest.dependents)
