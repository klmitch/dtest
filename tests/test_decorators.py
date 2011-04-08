from dtest import *
from dtest.util import *


@skip
def test_skip():
    pass


@failing
def test_failing():
    pass


@attr(attr1=1, attr2=2)
def test_attr():
    pass


@depends(test_skip, test_failing, test_attr)
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


class TestDecorators(DTestCase):
    @istest
    def skip(self):
        # Verify that skip is true...
        assert_true(test_skip.skip)

        # Verify that it's false on something else
        assert_false(test_failing.skip)

    @istest
    def failing(self):
        # Verify that failing is true...
        assert_true(test_failing.failing)

        # Verify that it's false on something else
        assert_false(test_skip.failing)

    @istest
    def attr(self):
        # Verify that the attributes are set as expected
        assert_equal(test_attr.attr1, 1)
        assert_equal(test_attr.attr2, 2)

    @istest
    def depends(self):
        # Part 1: Verify that test_depends() is dependent on
        # test_skip(), test_failing(), and test_attr()
        assert_in(test_skip, test_depends.dependencies)
        assert_in(test_failing, test_depends.dependencies)
        assert_in(test_attr, test_depends.dependencies)

        # Part 2: Verify that test_depends() is in the depedents set
        # of test_skip(), test_failing(), and test_attr()
        assert_in(test_depends, test_skip.dependents)
        assert_in(test_depends, test_failing.dependents)
        assert_in(test_depends, test_attr.dependents)

    @istest
    def raises(self):
        # Verify that the set of expected exceptions is as expected
        assert_set_equal(test_raises.raises, set([DecoratorTestException]))

        # Verify that it's the empty set on something else
        assert_set_equal(test_timed.raises, set())

    @istest
    def timed(self):
        # Verify that the timeout is set properly
        assert_equal(test_timed.timeout, 1)

        # Verify that it's None on something else
        assert_is_none(test_raises.timeout)
