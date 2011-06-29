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
contains SerialStrategy, UnlimitedParallelStrategy, and
LimitedParallelStrategy.
"""

import dtest

from eventlet import spawn_n
from eventlet.event import Event
from eventlet.semaphore import Semaphore


class SerialStrategy(object):
    """
    SerialStrategy
    ==============

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
    =========================

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

        # Save the output and test for the status stream
        self.output = dtest.status.output
        self.test = dtest.status.test

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

        # Initialize the status stream
        dtest.status.setup(self.output, self.test)

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


class LimitedParallelStrategy(UnlimitedParallelStrategy):
    """
    LimitedParallelStrategy
    =======================

    The LimitedParallelStrategy class is an extension of the
    UnlimitedParallelStrategy that additionally limits the maximum
    number of threads that may be executing at any given time.
    """

    def __init__(self, limit):
        """
        Initializes a LimitedParallelStrategy object.  The ``limit``
        parameter specifies the maximum number of threads that may
        execute at any given time.
        """

        # Save the limit
        self.limit = limit

    def prepare(self):
        """
        Prepares the LimitedParallelStrategy to spawn a set of tests.
        In addition to the tasks performed by
        UnlimitedParallelStrategy.prepare(), sets up a semaphore to
        limit the maximum number of threads that may execute at once.
        """

        # Call our superclass prepare method
        super(LimitedParallelStrategy, self).prepare()

        # Also initialize a limiting semaphore
        self.limit_sem = Semaphore(self.limit)

    def _spawn(self, call, args, kwargs):
        """
        Executes ``call`` in a separate thread of control.  This
        helper method extends UnlimitedParallelStrategy._spawn() to
        acquire the limiting semaphore prior to executing the call.
        """

        # Call our superclass _spawn method with the limit semaphore
        with self.limit_sem:
            super(LimitedParallelStrategy, self)._spawn(call, args, kwargs)
