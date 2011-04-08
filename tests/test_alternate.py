from dtest import *
from dtest.util import *


class TestAlternate(DTestCase):
    alternate = None

    def setUp(self):
        assert_is_none(self.alternate)
        self.alternate = False

    def tearDown(self):
        assert_false(self.alternate)

    def test1(self):
        assert_false(self.alternate)

    @istest
    def test2(self):
        assert_true(self.alternate)

    @test2.setUp
    def alternateSetUp(self):
        assert_is_none(self.alternate)
        self.alternate = True

    @test2.tearDown
    def alternateTearDown(self):
        assert_true(self.alternate)
