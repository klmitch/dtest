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
