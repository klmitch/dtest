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

"""
==============
Test Constants
==============

This module contains the various constants used by the test framework.
The constants are the various states that a test may be in (RUNNING,
FAIL, XFAIL, ERROR, DEPFAIL, OK, UOK, and SKIPPED) and the origins of
messages in the result (PRE, POST, and TEST).
"""

# Test states
RUNNING = 'RUNNING'  # test running
FAIL = 'FAIL'        # test failed
XFAIL = 'XFAIL'      # test expected to fail
ERROR = 'ERROR'      # error running test
DEPFAIL = 'DEPFAIL'  # dependency failed or errored out
OK = 'OK'            # test completed successfully
UOK = 'UOK'          # test unexpectedly completed successfully
SKIPPED = 'SKIPPED'  # test was skipped


# Result message origins
PRE = 'PRE'    # Error in pre-execute fixture
POST = 'POST'  # Error in post-execute fixture
TEST = 'TEST'  # Error from the test itself
