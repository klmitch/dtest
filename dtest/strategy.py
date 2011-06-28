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
==========================
Parallelization Strategies
==========================

This module contains all the classes necessary for identifying
parallelization strategies.  A parallelization strategy provides
support for alternate modes of parallelizing multiple-result tests,
i.e., tests on which @repeat() has been used or which are generators
providing lists of other test functions to execute.  This module
contains SerialStrategy and UnlimitedParallelStrategy.
"""

from eventlet import spawn_n
from eventlet.event import Event
from eventlet.semaphore import Semaphore


class SerialStrategy(object):
    """
    SerialStrategy
    ============

    The SerialStrategy class is a parallelization strategy that causes
    spawned tests to be executed serially, one after another.
    """

    def prepare(self):
        """
        Prepares the SerialStrategy object to spawn a set of tests.
        Since SerialStrategy "spawns" tests by running them
        synchronously, this function is a no-op.
        """

        pass

    def spawn(self, call, *args, **kwargs):
        """
        Spawn a function.  The callable ``call`` will be executed with
        the provided positional and keyword arguments.  Since
        SerialStrategy "spawns" tests by running them synchronously,
        this function simply calls ``call`` directly.
        """

        call(*args, **kwargs)

    def wait(self):
        """
        Waits for spawned tests to complete.  Since SerialStrategy
        "spawns" tests by running them synchronously, this function is
        a no-op.
        """

        pass


class UnlimitedParallelStrategy(object):
    """
    UnlimitedParallelStrategy
    =======================

    The UnlimitedParallelStrategy class is a parallelization strategy
    that causes spawned tests to be executed in parallel, with no
    limit on the maximum number of tests that can be executing at one
    time.
    """

    def prepare(self):
        """
        Prepares the UnlimitedParallelStrategy object to spawn a set
        of tests.  Simply initializes a counter to zero and sets up an
        event to be signaled when all tests are done.
        """

        # Initialize the counter and the event
        self.count = 0
        self.lock = Semaphore()
        self.event = None

    def spawn(self, call, *args, **kwargs):
        """
        Spawn a function.  The callable ``call`` will be executed with
        the provided positional and keyword arguments.  The ``call``
        will be executed in a separate thread.
        """

        # Spawn our internal function in a separate thread
        self.count += 1
        spawn_n(self._spawn, call, args, kwargs)

    def _spawn(self, call, args, kwargs):
        """
        Executes ``call`` in a separate thread of control.  This
        helper method maintains the count and arranges for the event
        to be signaled when appropriate.
        """

        # Call the call
        call(*args, **kwargs)

        # Decrement the count
        self.count -= 1

        # Signal the event, if necessary
        with self.lock:
            if self.count == 0 and self.event is not None:
                self.event.send()

    def wait(self):
        """
        Waits for spawned tests to complete.
        """

        # Check for completion...
        with self.lock:
            if self.count == 0:
                # No tests still going, so just return
                return

            # OK, let's initialize the event...
            self.event = Event()

        # Now we wait on the event
        self.event.wait()

        # End by clearing the event
        self.event = None
