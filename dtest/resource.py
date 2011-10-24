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
Test Resources
==============

This module contains the Resource class, along with a number of other
functions, which together provide the functionality for providing test
resources.  A test resource is simply a discrete object which is
required by a given test function or method; it could be a temporary
file containing configuration for a component, or a client object for
accessing a server, or virtually anything that would ordinarily be set
up in a test fixture.  Resources which are not modified (which are not
"dirty") may be reused by following tests, subject to threading
constraints.

This file does not contain the @require() decorator, which is defined
in the dtest.test module.
"""

import functools
import sys

from eventlet import semaphore


class ResourceObjectMeta(type):
    """
    ResourceObjectMeta class, which provides some utility class
    methods for the ResourceObject class without polluting its
    namespace.
    """

    def resource(cls, obj):
        """
        Retrieve the resource associated with a ResourceObject
        ``obj``.
        """

        return obj.__res_resource__

    def obj(cls, obj):
        """
        Retrieve the actual object associated with a ResourceObject
        ``obj``.
        """

        return obj.__res_obj__

    def dirty(cls, obj, new=None):
        """
        Retrieve the dirty flag associated with a ResourceObject
        ``obj``.  If ``new`` is provided, specifies a new value for
        the dirty flag.
        """

        # Save the current value
        old = obj.__res_dirty__

        # Update it
        if new is not None:
            obj.__res_dirty__ = new

        return old

    def makedirty(cls, obj, new):
        """
        Changes the 'makedirty' flag associated with a ResourceObject
        ``obj``.  Returns its previous value.
        """

        # Save the current value
        old = obj.__res_makedirty__

        # Update it
        obj.__res_makedirty__ = new

        return old


class ResourceObject(object):
    """
    ResourceObject class, which acts as a binding between a Resource
    and the actual resource object.  Acts as a transparent proxy, but
    calling any of the dirty methods or setting or deleting any
    attributes causes the resource to be marked as dirty.  Use the
    cleanaccess() function as a context manager to allow accesses that
    would normally dirty the resource.
    """

    __metaclass__ = ResourceObjectMeta

    def __init__(self, resource, resobj, dirtymeths):
        """
        Create a ResourceObject.  The ``resource`` is an instance of
        Resource, and ``resobj`` is the actual object to delegate
        accesses to.  The ``dirtymeths`` is a list of methods which,
        when called, cause the object to become dirty.
        """

        # We use __res_*__ to avoid conflicting with attributes on the
        # resource object
        self.__res_resource__ = resource
        self.__res_obj__ = resobj
        self.__res_dirtymeths__ = set(dirtymeths)
        self.__res_dirty__ = False
        self.__res_makedirty__ = True

    def __getattribute__(self, name):
        """
        Retrieves an attribute from the resource object.  If the
        attribute is a dirty method, it will be wrapped with a
        function which will set the dirty attribute on the resource.
        """

        # Short-cut the __res_*__ attributes...
        if name.startswith('__res_') and name.endswith('__'):
            return super(ResourceObject, self).__getattribute__(name)

        # First, get the attribute from the resource object
        attr = getattr(self.__res_obj__, name)

        # If it's a callable, and listed in dirtymeths, wrap it
        if callable(attr) and name in self.__res_dirtymeths__:
            @functools.wraps(attr)
            def wrapper(*args, **kwargs):
                # Mark it dirty
                if self.__res_makedirty__:
                    self.__res_dirty__ = True

                # Call the function
                return attr(*args, **kwargs)

            # Return our wrapper
            return wrapper

        return attr

    def __setattr__(self, name, value):
        """
        Sets an attribute on the resource object.  Sets the dirty
        attribute on the resource.
        """

        # Short-cut the __res_*__ attributes...
        if name.startswith('__res_') and name.endswith('__'):
            return super(ResourceObject, self).__setattr__(name, value)

        # OK, mark resource dirty
        if self.__res_makedirty__:
            self.__res_dirty__ = True

        # Delegate to the resource object
        return setattr(self.__res_obj__, name, value)

    def __delattr__(self, name):
        """
        Deletes an attribute on the resource object.  Sets the dirty
        attribute on the resource.
        """

        # Short-cut the __res_*__ attributes...
        if name.startswith('__res_') and name.endswith('__'):
            return super(ResourceObject, self).__delattr__(name)

        # OK, mark resource dirty
        if self.__res_makedirty__:
            self.__res_dirty__ = True

        # Delegate to the resource object
        return delattr(self.__res_obj__, name)


class CleanContext(object):
    """
    Context manager returned by cleanaccess().  Temporarily disables
    dirty detection for resource objects.
    """

    def __init__(self, objs):
        """
        Initialize the CleanContext.  Saves the list of objects for
        which temporary dirty detection must be disabled.
        """

        self.objs = objs
        self.makedirty = {}

    def __enter__(self):
        """
        Enter the context.  Turns off ``makedirty`` for all objects,
        saving the original values for later restoration.
        """

        for obj in self.objs:
            self.makedirty[id(obj)] = ResourceObject.makedirty(obj, False)

        # Return the list of objects
        return obj

    def __exit__(self, exc_type, exc_value, exc_tb):
        """
        Exit the context.  Restores the ``makedirty`` for all objects.
        """

        for obj in self.objs:
            ResourceObject.makedirty(obj, self.makedirty[id(obj)])


def cleanaccess(*objs):
    """
    Allows access to the objects given as arguments without affecting
    their ``dirty`` flags.
    """

    return CleanContext(objs)


def dirty(*objs):
    """
    Marks the objects given as arguments as dirty.
    """

    for obj in objs:
        ResourceObject.dirty(obj, True)


def clean(*objs):
    """
    Marks the objects given as arguments as clean.
    """

    for obj in objs:
        ResourceObject.dirty(obj, False)


def getobject(obj):
    """
    The resources system uses proxy objects, so it can catch actions
    which make a resource "dirty".  Sometimes, this interferes with
    the action of the base resource object, for instance, when the
    base resource object implements one of the special methods.  This
    function provides a means of accessing the base resource object
    directly, given a wrapped resource object ``obj``.
    """

    return ResourceObject.obj(obj)


class Resource(object):
    """
    Resource class, which describes test resources.  To define a
    resource, extend this class and implement the setUp() method and,
    optionally, the tearDown() method.  Subclasses may also specify
    alternate values for the ``oneshot`` and ``dirtymeths`` class
    attributes: if ``oneshot`` is True, every acquired resource will
    only be used once; and ``dirtymeths`` should be a list giving the
    name of methods which, when called, cause the resource object to
    be considered dirty.
    """

    # If set to True, resource will never be used more than once
    oneshot = False
    dirtymeths = []

    def __init__(self, *args, **kwargs):
        """
        Initialize a Resource.  This saves the arguments, which will
        later be passed to setUp().
        """

        # Build a key from the arguments
        key = [self.__class__]
        key += [str(a) for a in args]
        key += ['%s=%s' % (k, kwargs[k]) for k in sorted(kwargs.keys())]
        self.key = tuple(key)

        # Save the arguments
        self.args = args
        self.kwargs = kwargs

    def acquire(self):
        """
        Acquire a resource object.  This calls the setUp() method and
        binds its return result to this resource object using the
        ResourceObject class.
        """

        # Build and return the actual resource object
        obj = self.setUp(*self.args, **self.kwargs)

        # Build our proxy object
        return ResourceObject(self, obj, self.dirtymeths)

    def release(self, obj, msgs, status=None, force=False):
        """
        Release a resource object.  If the object cannot be reused, or
        if ``force`` is True, the tearDown() method will be called.
        Returns True if the object may be reused, otherwise returns
        False.
        """

        # Do we need to release the object?
        if force or self.oneshot or ResourceObject.dirty(obj):
            try:
                self.tearDown(ResourceObject.obj(obj), status)
            except:
                # In the event of an error releasing a resource, save
                # a message documenting the failure
                msgs.append((self, sys.exc_info()))
            return False

        return True

    def setUp(self, *args, **kwargs):
        """
        Sets up and returns the resource.  Must be implemented by all
        subclasses.
        """

        raise NotImplementedError("%s.%s.setUp() is not implemented" %
                                  (self.__class__.__module__,
                                   self.__class__.__name__))

    def tearDown(self, obj, status):
        """
        Tears down a resource allocated by setUp().  This is optional;
        implement it only if you need to release resources, such as
        open files.

        Note that the test's status will be passed as the ``status``
        argument, except in the case of cached resources being cleaned
        up after all tests have finished running.  This status value
        can be used to ensure that debugging resources, such as
        temporary files, are preserved in the event of a failure.
        """

        pass


class ResourceManager(object):
    """
    ResourceManager class, which manages a pool of resources.
    """

    def __init__(self):
        """
        Initializes the resource pool.
        """

        self._pool_lock = semaphore.Semaphore()
        self._pool = {}

        # Need a place to store error messages
        self._messages = []

    def _get_pool(self, res):
        """
        Retrieve the pool corresponding to the resource ``res``.  This
        method must be called with the pool lock held.
        """

        # Make sure we have the pool...
        if res.key not in self._pool:
            self._pool[res.key] = []

        # Return the resource pool
        return self._pool[res.key]

    def acquire(self, res):
        """
        Acquire a resource object corresponding to the resource
        ``res``.
        """

        # Hold the lock while we're accessing the resource pool
        with self._pool_lock:
            pool = self._get_pool(res)

            # Do we have an available resource?
            if len(pool) > 0:
                return pool.pop(0)

        # OK, create a new resource object
        return res.acquire()

    def release(self, obj, status=None):
        """
        Release a resource object ``obj``.  If the object is dirty, it
        will be discarded; otherwise, it will be added to the resource
        pool for later reuse.
        """

        # Get the resource
        res = ResourceObject.resource(obj)

        # Let the resource do any cleaning up it needs to do...
        if not res.release(obj, self._messages, status=status):
            # It was dirty, so we got rid of it
            return

        # OK, we're going to add it back to the resource pool, so grab
        # the lock
        with self._pool_lock:
            # Get the pool
            pool = self._get_pool(res)

            # Append resource object to the end of the pool, so we
            # have FIFO-style reuse
            pool.append(obj)

    def release_all(self):
        """
        Release all resources in the resource pool.
        """

        # Force-release all resource objects
        with self._pool_lock:
            for objlist in self._pool.values():
                for obj in objlist:
                    res = ResourceObject.resource(obj)
                    res.release(obj, self._messages, force=True)

            # Clear the pool
            self._pool = {}

    def collect(self, resources):
        """
        Collects the resources identified by the ``resources``
        dictionary and yields them as a dictionary to the caller.  The
        resources allocated are then released when the generator
        continues.  The generator's send() method should be called
        with the test status, which will then be passed to the
        resource tearDown() methods.
        """

        # Set up the resources we need...
        objects = {}
        for key, res in resources.items():
            objects[key] = self.acquire(res)

        # Yield the resource dictionary and get the test status
        status = yield objects

        # Now, release the resources we used
        for obj in objects.values():
            self.release(obj, status=status)

    @property
    def messages(self):
        """
        Retrieve all error messages accumulated while releasing
        resources.  Clears the message list.
        """

        # Get the current messages
        msgs = self._messages

        # Clear the list
        self._messages = []

        return msgs
