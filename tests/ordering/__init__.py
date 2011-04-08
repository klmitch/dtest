# Need t_order
import tests


def setUp():
    # Make sure we're the second thing to have run
    assert len(tests.t_order) == 1, "Ordering error running test suite"
    assert tests.t_order[-1] == 'tests.setUp', "Incorrect previous step"

    # Keep track of what has run
    tests.t_order.append('tests.ordering.setUp')


def tearDown():
    # Make sure we're the thirteenth thing to have run
    assert len(tests.t_order) == 12, "Ordering error running test suite"
    assert tests.t_order[-1] == 'tests.ordering.test_order.tearDown', \
        "Incorrect previous step"

    # Keep track of what has run
    tests.t_order.append('tests.ordering.tearDown')
