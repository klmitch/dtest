# Test states
RUNNING = 'RUNNING'  # test running
FAIL = 'FAIL'        # test failed
XFAIL = 'XFAIL'      # test expected to fail
ERROR = 'ERROR'      # error running test
DEPFAIL = 'DEPFAIL'  # dependency failed or errored out
OK = 'OK'            # test completed successfully
UOK = 'UOK'          # test unexpectedly completed successfully
SKIPPED = 'SKIPPED'  # test was skipped


# Result origins
PRE = 'PRE'    # Error in pre-execute fixture
POST = 'POST'  # Error in post-execute fixture
TEST = 'TEST'  # Error from the test itself
