from dtest import *
from dtest.util import *


# Ensure that the alternate setUp/tearDown decorators work
class TestAlternate(DTestCase):
    alternate = None

    def setUp(self):
        assert_is_none(self.alternate)
        self.alternate = False

    def tearDown(self):
        assert_false(self.alternate)

    # Should use the default setUp/tearDown
    def test1(self):
        assert_false(self.alternate)

    # Have to use @istest here to make the decorators available
    @istest
    def test2(self):
        assert_true(self.alternate)

    # Alternate setUp/tearDown for test2
    @test2.setUp
    def alternateSetUp(self):
        assert_is_none(self.alternate)
        self.alternate = True

    @test2.tearDown
    def alternateTearDown(self):
        assert_true(self.alternate)
