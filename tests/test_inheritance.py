from dtest import *
from dtest.util import *


# Define setUpClass/tearDownClass/setUp/tearDown for inheritance
class TestInheritanceBase(DTestCase):
    class_setup = None
    instance_setup = None

    @classmethod
    def setUpClass(cls):
        assert_is_none(cls.class_setup)
        cls.class_setup = True

    @classmethod
    def tearDownClass(cls):
        assert_false(cls.class_setup)

    def setUp(self):
        assert_is_none(self.instance_setup)
        self.instance_setup = True

    def tearDown(self):
        assert_false(self.instance_setup)


# See if we inherited them
class TestInheritance(TestInheritanceBase):
    @attr(must_skip=True)
    def test_inheritance(self):
        assert_true(self.__class__.class_setup)
        assert_true(self.instance_setup)

        self.__class__.class_setup = False
        self.instance_setup = False


# Let's really stress things out, here...
class TestInheritanceTwo(TestInheritance):
    def test_inheritance(self):
        # Make sure we can call our superclass method
        super(TestInheritanceTwo, self).test_inheritance(self)
