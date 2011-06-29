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
===============
Result Policies
===============

This module contains all the functions and classes necessary for
identifying result policies.  A result policy comes into play only for
tests that result in multiple test calls.  Result policies are simply
callables (functions or objects with __call__() methods) that receive
four counts--the total number of results accumulated so far, the total
number that succeeded, the total number that failed, and the total
number of errors encountered.  They must return a tuple containing two
boolean values--one indicating whether the test is an overall success
(True) or not, and the second indicating whether the test is an error.
(The second may only be True if the first is False.)
"""


def basicPolicy(tot, suc, fail, err):
    """
    Implements the basic policy--all tests must be a success for the
    overall result to be a success, and if there are any errors, the
    overall result is an error.
    """

    return (fail == 0 and err == 0), (err > 0)


class ThresholdPolicy(object):
    """
    ThresholdPolicy
    ===============

    Implements the threshold policy--there must be no errors, and the
    number of successes must exceed a given threshold (expressed as a
    percentage) for the overall result to be a success.
    """

    def __init__(self, threshold):
        """
        Initialize the ThresholdPolicy object.  The ``threshold`` must
        be expressed as a percentage (0 to 100); float values are
        legal here.
        """

        # Save the threshold
        self.threshold = threshold

    def __call__(self, tot, suc, fail, err):
        """
        Implements the threshold policy.  If ``err`` is greater than
        zero, the overall result is an error; otherwise, if ``suc``
        represents more than the configured threshold percentage of
        ``tot``, the overall result is a success.  Note that if
        ``fail`` is zero, the threshold logic is skipped.
        """

        # If there are any errors, we have an error result
        if err > 0:
            return False, True

        # If fail is 0, no point going on
        if fail == 0:
            return True, False

        # Compute the percentage of successes...
        percent = (suc * 100.0) / tot

        # We're successful only if percent is greater than threshold
        return (percent >= self.threshold), False
