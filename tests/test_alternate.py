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
