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
        assert_true(self.class_setup)
        assert_true(self.instance_setup)

        TestInheritanceBase.class_setup = False
        self.instance_setup = False


# Let's really stress things out, here...
class TestInheritanceTwo(TestInheritance):
    def test_inheritance(self):
        # Make sure we can call our superclass method
        super(TestInheritanceTwo, self).test_inheritance()
