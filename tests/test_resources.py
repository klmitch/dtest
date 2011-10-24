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
from dtest.resource import ResourceObject
from dtest.util import *


class ObjTest(object):
    pass


class ResourceTest(Resource):
    oneshot = True
    def setUp(self, name, value):
        t = ObjTest()
        setattr(t, name, value)
        return t


@require(test1=ResourceTest('foo', 'bar'),
         test2=ResourceTest('bar', 'foo'))
def test_basic(test1, test2):
    assert_is_instance(test1, ResourceObject)
    assert_is_instance(test2, ResourceObject)
    assert_is_instance(getobject(test1), ObjTest)
    assert_is_instance(getobject(test2), ObjTest)
    assert_not_equal(id(test1), id(test2))
    assert_not_equal(id(getobject(test1)), id(getobject(test2)))
    assert_equal(test1.foo, 'bar')
    assert_equal(test2.bar, 'foo')


@require(test=ResourceTest('foo', True))
def test_dirty_direct(test):
    assert_equal(ResourceObject.dirty(test), False)
    dirty(test)
    assert_equal(ResourceObject.dirty(test), True)
    clean(test)
    assert_equal(ResourceObject.dirty(test), False)


@depends(test_dirty_direct)
@require(test=ResourceTest('foo', True))
def test_dirty_attr(test):
    assert_equal(ResourceObject.dirty(test), False)
    test.foo = False
    assert_equal(ResourceObject.dirty(test), True)
    clean(test)
    assert_equal(ResourceObject.dirty(test), False)
    del test.foo
    assert_equal(ResourceObject.dirty(test), True)


@depends(test_dirty_direct)
@require(test=ResourceTest('foo', True))
def test_dirty_access(test):
    assert_equal(ResourceObject.dirty(test), False)
    with cleanaccess(test):
        test.foo = True
    assert_equal(ResourceObject.dirty(test), False)
    with cleanaccess(test):
        del test.foo
    assert_equal(ResourceObject.dirty(test), False)


class ObjTestMeth(object):
    def foo(self):
        self.test = False
    def bar(self):
        self.test = True


class ResourceTestMeth(Resource):
    oneshot = True
    dirtymeths = ['foo']
    def setUp(self):
        t = ObjTestMeth()
        t.test = True
        return t


@depends(test_dirty_direct)
@require(test=ResourceTestMeth())
def test_dirty_meth(test):
    assert_equal(ResourceObject.dirty(test), False)
    assert_equal(test.test, True)
    test.foo()
    assert_equal(ResourceObject.dirty(test), True)
    assert_equal(test.test, False)
    clean(test)
    assert_equal(ResourceObject.dirty(test), False)
    test.bar()
    assert_equal(ResourceObject.dirty(test), False)
    assert_equal(test.test, True)
    with cleanaccess(test):
        test.foo()
    assert_equal(ResourceObject.dirty(test), False)
    assert_equal(test.test, False)


reuse_cache = None


class ReuseObj(object):
    pass


class ResourceTestReuse(Resource):
    def setUp(self, name, value):
        t = ReuseObj()
        setattr(t, name, value)
        return t


@require(test=ResourceTestReuse('foo', True))
def test_reuse1(test):
    global reuse_cache
    reuse_cache = test


@depends(test_reuse1)
@require(test=ResourceTestReuse('foo', True))
def test_reuse2(test):
    assert_equal(reuse_cache, test)


@depends(test_reuse2)
@require(test=ResourceTestReuse('foo', False))
def test_reuse3(test):
    assert_not_equal(reuse_cache, test)


@depends(test_reuse3)
@require(test=ResourceTestReuse('foo', True))
def test_reuse4(test):
    assert_equal(reuse_cache, test)
    dirty(test)


@depends(test_reuse4)
@require(test=ResourceTestReuse('foo', True))
def test_reuse5(test):
    assert_not_equal(reuse_cache, test)


teardown_oneshot_cache = None


class ObjTestTearDown(object):
    pass


class ResourceTestTearDownOneShot(Resource):
    oneshot = True
    def setUp(self, name, value):
        t = ObjTestTearDown()
        setattr(t, name, value)
        return t

    def tearDown(self, obj, result):
        obj.torndown = result


@require(test=ResourceTestTearDownOneShot('foo', True))
def test_teardown1_oneshot(test):
    global teardown_oneshot_cache
    teardown_oneshot_cache = test
    assert_equal(getattr(test, 'torndown', None), None)


@depends(test_teardown1_oneshot)
def test_teardown2_oneshot():
    assert_equal(getattr(teardown_oneshot_cache, 'torndown', None), 'OK')


teardown_dirty_cache = None


class ResourceTestTearDownDirty(Resource):
    def setUp(self, name, value):
        t = ObjTestTearDown()
        setattr(t, name, value)
        return t

    def tearDown(self, obj, result):
        obj.torndown = result


@require(test=ResourceTestTearDownDirty('foo', True))
def test_teardown1_dirty(test):
    global teardown_dirty_cache
    teardown_dirty_cache = test
    dirty(test)
    assert_equal(getattr(test, 'torndown', None), None)


@depends(test_teardown1_dirty)
def test_teardown2_dirty():
    assert_equal(getattr(teardown_dirty_cache, 'torndown', None), 'OK')
