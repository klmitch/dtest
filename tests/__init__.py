t_order = []


def setUp():
    # Make sure we're the first thing to have run
    assert len(t_order) == 0, "Ordering error running test suite"

    # Keep track of what has run
    t_order.append('tests.setUp')


def tearDown():
    # Make sure we're the fourteenth thing to have run
    assert len(t_order) == 13, "Ordering error running test suite"
    assert t_order[-1] == 'tests.ordering.tearDown', "Incorrect previous step"

    # Keep track of what has run
    t_order.append('tests.tearDown')
