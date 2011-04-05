import re

from dtest.exceptions import DTestException


__all__ = ['assert_false', 'assert_true', 'assert_raises', 'assert_equal',
           'assert_not_equal', 'assert_almost_equal',
           'assert_not_almost_equal', 'assert_sequence_equal',
           'assert_list_equal', 'assert_tuple_equal', 'assert_set_equal',
           'assert_in', 'assert_not_in', 'assert_is', 'assert_is_not',
           'assert_dict_equal', 'assert_dict_contains', 'assert_items_equal',
           'assert_less', 'assert_less_equal', 'assert_greater',
           'assert_greater_equal', 'assert_is_none', 'assert_is_not_none',
           'assert_is_instance', 'assert_is_not_instance',
           'assert_regexp_matches', 'assert_not_regexp_matches']


def safe_repr(obj, maxlen=None):
    # Safely get the representation of an object
    try:
        result = repr(obj)
    except:
        # The repr() could call user code, so if it fails, we want to
        # be intelligent about what we return
        result = object.__repr__(obj)

    # Truncate representation if necessary
    if maxlen is not None and len(result) > maxlen:
        result = result[:maxlen - 3] + '...'

    return result


def select_msg(usermsg, defmsg):
    # Select the correct message to use
    if usermsg is None:
        return defmsg
    return usermsg


def make_re(regexp):
    # If it's None or not an instance of string, return it
    if regexp is None or not isinstance(regexp, basestring):
        return regexp

    # Convert to a regular expression
    return re.compile(regexp)


def assert_false(expr, msg=None):
    # Ensure expr is False
    if expr:
        msg = select_msg(msg, "%s is not False" % safe_repr(expr))
        raise AssertionError(msg)


def assert_true(expr, msg=None):
    # Ensure expr is True
    if not expr:
        msg = select_msg(msg, "%s is not True" % safe_repr(expr))
        raise AssertionError(msg)


class AssertRaisesContext(object):
    def __init__(self, excs, msg, regexp=None):
        self.excs = excs
        self.msg = msg
        self.regexp = make_re(regexp)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        # Ensure the appropriate exception was raised
        if exc_type is None:
            if None in self.excs:
                # Exception wasn't raised, but that's OK
                return True

            # OK, have to raise an assertion error
            msg = select_msg(self.msg, "No exception raised; expected one "
                             "of: (%s)" % ', '.join([self._exc_name(exc)
                                                     for exc in self.excs]))
            raise AssertionError(msg)

        # OK, an exception was raised; make sure it's one we were
        # expecting
        elif exc_type in self.excs or issubclass(exc_type, self.excs):
            # Do we need to check against a regexp?
            if (self.regexp is not None and
                not self.regexp.search(str(exc_value))):
                msg = select_msg(self.msg, 'Exception "%s" does not match '
                                 'expression "%s"' % (exc_value,
                                                      self.regexp.pattern))
                raise AssertionError(msg)

            # Assertion we were looking for, so say we handled it
            return True

        # Not an exception we were expecting, so let it bubble up
        return False

    @staticmethod
    def _exc_name(exc):
        try:
            # If it has a name, return it
            return exc.__name__
        except AttributeError:
            # OK, let's try to stringify it instead
            return str(exc)


def assert_raises(excepts, *args, **kwargs):
    # Extract callableObj from arguments
    callableObj = None
    if 'callableObj' in kwargs:
        callableObj = kwargs['callableObj']
        del kwargs['callableObj']
    elif args:
        callableObj = args[0]
        args = args[1:]

    # Extract noRaiseMsg from keyword arguments
    noRaiseMsg = None
    if 'noRaiseMsg' in kwargs:
        noRaiseMsg = kwargs['noRaiseMsg']
        del kwargs['noRaiseMsg']

    # Extract matchRegExp from keyword arguments
    matchRegExp = None
    if 'matchRegExp' in kwargs:
        matchRegExp = kwargs['matchRegExp']
        del kwargs['matchRegExp']

    # First, check if excepts is a sequence
    try:
        length = len(excepts)
    except (TypeError, NotImplementedError):
        excepts = [excepts]

    # Now, grab a context
    ctx = AssertRaisesContext(excepts, noRaiseMsg, matchRegExp)

    if callableObj is None:
        # No callable, so just return the context
        return ctx

    # Execute the callable
    with ctx:
        callableObj(*args, **kwargs)


def assert_equal(first, second, msg=None):
    # Ensure first == second
    if not first == second:
        msg = select_msg(msg, "%s != %s" %
                         (safe_repr(first), safe_repr(second)))
        raise AssertionError(msg)


def assert_not_equal(first, second, msg=None):
    # Ensure first != second
    if not first != second:
        msg = select_msg(msg, "%s == %s" %
                         (safe_repr(first), safe_repr(second)))
        raise AssertionError(msg)


def assert_almost_equal(first, second, msg=None, places=None, delta=None):
    # Sanity-check arguments
    if places is not None and delta is not None:
        raise DTestException("Specify delta or places, not both")

    # Ensure first and second are similar
    if first == second:
        # Short-circuit for the simple case
        return

    # Is this comparison a delta style?
    if delta is not None:
        if abs(first - second) <= delta:
            return

        stdmsg = "%s != %s within %s delta" % (safe_repr(first),
                                               safe_repr(second),
                                               safe_repr(delta))

    else:
        # OK, do a places-based comparison; default places to 7
        if places is None:
            places = 7

        if round(abs(first - second), places) == 0:
            return

        stdmsg = "%s != %s within %s places" % (safe_repr(first),
                                                safe_repr(second),
                                                safe_repr(places))

    # OK, they're not equal, so tell the caller
    raise AssertionError(select_msg(msg, stdmsg))


def assert_not_almost_equal(first, second, msg=None, places=None, delta=None):
    # Sanity-check arguments
    if places is not None and delta is not None:
        raise DTestException("Specify delta or places, not both")

    # Is this comparison a delta style?
    if delta is not None:
        if not (first == second) and abs(first - second) > delta:
            return

        stdmsg = "%s == %s within %s delta" % (safe_repr(first),
                                               safe_repr(second),
                                               safe_repr(delta))

    else:
        # OK, do a places-based comparison; default places to 7
        if places is None:
            places = 7

        if not (first == second) and round(abs(first - second), places) != 0:
            return

        stdmsg = "%s == %s within %s places" % (safe_repr(first),
                                                safe_repr(second),
                                                safe_repr(places))

    # OK, they're not equal, so tell the caller
    raise AssertionError(select_msg(msg, stdmsg))


def assert_sequence_equal(seq1, seq2, msg=None, seq_type=None):
    # Enforce sequence typing
    if seq_type is not None:
        st_name = seq_type.__name__
        if not isinstance(seq1, seq_type):
            raise AssertionError("First sequence is not a %s: %s" %
                                 (st_name, safe_repr(seq1)))
        if not isinstance(seq2, seq_type):
            raise AssertionError("Second sequence is not a %s: %s" %
                                 (st_name, safe_repr(seq2)))
    else:
        st_name = "sequence"

    # Grab the lengths of the sequences
    differing = None
    try:
        len1 = len(seq1)
    except (TypeError, NotImplementedError):
        differing = "First %s has no length.  Non-sequence?" % st_name
    if differing is None:
        try:
            len2 = len(seq2)
        except (TypeError, NotImplementedError):
            differing = "Second %s has no length.  Non-sequence?" % st_name

    # Now let's compare the sequences
    if differing is None:
        if seq1 == seq2:
            return

        # They differ somehow...
        seq1_repr = safe_repr(seq1)
        seq2_repr = safe_repr(seq2)
        if len(seq1_repr) > 30:
            seq1_repr = seq1_repr[:27] + "..."
        if len(seq2_repr) > 30:
            seq2_repr = seq2_repr[:27] + "..."
        differing = "%ss differ: %s != %s" % (st_name.capitalize(),
                                              seq1_repr, seq2_repr)

        # Compare sequences element by element
        for i in xrange(min(len1, len2)):
            try:
                item1 = seq1[i]
            except (TypeError, IndexError, NotImplementedError):
                differing += ("\nUnable to index element %d of first %s" %
                              (i, st_name))
                break

            try:
                item2 = seq2[i]
            except (TypeError, IndexError, NotImplementedError):
                differing += ("\nUnable to index element %d of second %s" %
                              (i, st_name))
                break

            if item1 != item2:
                differing += ("\nFirst differing element %d: %s != %s" %
                              (i, safe_repr(item1), safe_repr(item2)))
                break
        else:
            # The items tally up, but...
            if len1 == len2 and seq_type is None and type(seq1) != type(seq2):
                # Just differ in type; who cares?
                return

        # Emit the extra elements
        if len1 > len2:
            differing += ("\nFirst %s contains %d additional elements" %
                          (st_name, len1 - len2))
            try:
                differing += ("\nFirst extra element %d: %s" %
                              (len2, safe_repr(seq1[len2])))
            except (TypeError, IndexError, NotImplementedError):
                differing += ("\nUnable to index element %d of first %s" %
                              (len2, st_name))
        elif len1 < len2:
            differing += ("\nSecond %s contains %d additional elements" %
                          (st_name, len2 - len1))
            try:
                differing += ("\nFirst extra element %d: %s" %
                              (len1, safe_repr(seq2[len1])))
            except (TypeError, IndexError, NotImplementedError):
                differing += ("\nUnable to index element %d of second %s" %
                              (len1, st_name))

    # Not going to bother with the whole diff stuff unittest does
    raise AssertionError(select_msg(msg, differing))


def assert_list_equal(list1, list2, msg=None):
    assert_sequence_equal(list1, list2, msg=msg, seq_type=list)


def assert_tuple_equal(tuple1, tuple2, msg=None):
    assert_sequence_equal(tuple1, tuple2, msg=msg, seq_type=tuple)


def assert_set_equal(set1, set2, msg=None):
    # Obtain the two set differences
    try:
        diff1 = set1.difference(set2)
    except TypeError as e:
        raise AssertionError("Invalid type when attempting set "
                             "difference: %s" % e)
    except AttributeError as e:
        raise AssertionError("First set does not support set "
                             "difference: %s" % e)

    try:
        diff2 = set2.difference(set1)
    except TypeError as e:
        raise AssertionError("Invalid type when attempting set "
                             "difference: %s" % e)
    except AttributeError as e:
        raise AssertionError("Second set does not support set "
                             "difference: %s" % e)

    # If both differences are empty, then we're fine
    if not (diff1 or diff2):
        return

    # Accumulate items in one but not the other
    stdmsg = ''
    if diff1:
        stdmsg += ("Items in the first set but not the second: %s" %
                   ', '.join([safe_repr(item) for item in diff1]))
    if diff2:
        if stdmsg:
            stdmsg += "\n"
        stdmsg += ("Items in the second set but not the first: %s" %
                   ', '.join([safe_repr(item) for item in diff2]))

    # Tell the caller
    raise AssertionError(select_msg(msg, stdmsg))


def assert_in(member, container, msg=None):
    # Ensure member is in container
    if member not in container:
        msg = select_msg(msg, "%s not found in %s" %
                         (safe_repr(member), safe_repr(container)))
        raise AssertionError(msg)


def assert_not_in(member, container, msg=None):
    # Ensure member is not in container
    if member in container:
        msg = select_msg(msg, "%s unexpectedly found in %s" %
                         (safe_repr(member), safe_repr(container)))
        raise AssertionError(msg)


def assert_is(expr1, expr2, msg=None):
    # Ensure expr1 is expr2
    if expr1 is not expr2:
        msg = select_msg(msg, "%s is not %s" %
                         (safe_repr(expr1), safe_repr(expr2)))
        raise AssertionError(msg)


def assert_is_not(expr1, expr2, msg=None):
    # Ensure expr1 is not expr2
    if expr1 is expr2:
        msg = select_msg(msg, "%s is unexpectedly %s" %
                         (safe_repr(expr1), safe_repr(expr2)))
        raise AssertionError(msg)


def assert_dict_equal(d1, d2, msg=None):
    # Make sure both are dict instances
    if not isinstance(d1, dict):
        raise AssertionError("First argument is not a dictionary")
    if not isinstance(d2, dict):
        raise AssertionError("Second argument is not a dictionary")

    # Ensure they're equal
    if d1 != d2:
        stdmsg = "%s != %s" % (safe_repr(d1, 30), safe_repr(d2, 30))
        raise AssertionError(select_msg(msg, stdmsg))


def assert_dict_contains(actual, expected, msg=None):
    # Determine missing or mismatched keys
    missing = []
    mismatched = []
    for k, v in expected.items():
        if k not in actual:
            missing.append(k)
        elif v != actual[k]:
            mismatched.append("Key %s: expected %s, actual %s" %
                              (safe_repr(k), safe_repr(v),
                               safe_repr(actual[k])))

    # Are there any problems?
    if not (missing or mismatched):
        return

    # Build up the standard message
    stdmsg = ''
    if missing:
        stdmsg += "Missing keys: %s" % ', '.join([safe_repr(k)
                                                  for k in missing])
    if mismatched:
        if stdmsg:
            stdmsg += '; '
        stdmsg += "Mismatched values: %s" % '; '.join(mismatched)

    raise AssertionError(select_msg(msg, stdmsg))


def assert_items_equal(actual, expected, msg=None):
    # Order n^2 algorithm for comparing items in the lists
    missing = []
    while expected:
        item = expected.pop()
        try:
            # Take it out of what we actually got
            actual.remove(item)
        except ValueError:
            # It wasn't there!
            missing.append(item)

    # Now, missing contains those items in expected which were not in
    # actual, and actual contains those items which were not in
    # expected; if missing and actual are empty, we're fine
    if not missing and not actual:
        return

    # Build the error message
    stdmsg = ''
    if missing:
        stdmsg += ("Missing items: %s" %
                   ', '.join([safe_repr(i) for i in missing]))
    if actual:
        if stdmsg:
            stdmsg += '; '
        stdmsg += ("Unexpected items: %s" %
                   ', '.join([safe_repr(i) for i in actual]))
    raise AssertionError(select_msg(msg, stdmsg))


def assert_less(a, b, msg=None):
    # Ensure a < b
    if not a < b:
        msg = select_msg(msg, "%s not less than %s" %
                         (safe_repr(a), safe_repr(b)))
        raise AssertionError(msg)


def assert_less_equal(a, b, msg=None):
    # Ensure a <= b
    if not a <= b:
        msg = select_msg(msg, "%s not less than or equal to %s" %
                         (safe_repr(a), safe_repr(b)))
        raise AssertionError(msg)


def assert_greater(a, b, msg=None):
    # Ensure a > b
    if not a > b:
        msg = select_msg(msg, "%s not greater than %s" %
                         (safe_repr(a), safe_repr(b)))
        raise AssertionError(msg)


def assert_greater_equal(a, b, msg=None):
    # Ensure a >= b
    if not a >= b:
        msg = select_msg(msg, "%s not greater than or equal to %s" %
                         (safe_repr(a), safe_repr(b)))
        raise AssertionError(msg)


def assert_is_none(obj, msg=None):
    # Ensure obj is None
    if obj is not None:
        msg = select_msg(msg, "%s is not None" % safe_repr(obj))
        raise AssertionError(msg)


def assert_is_not_none(obj, msg=None):
    # Ensure obj is not None
    if obj is None:
        msg = select_msg(msg, "%s is None" % safe_repr(obj))
        raise AssertionError(msg)


def assert_is_instance(obj, cls, msg=None):
    # Ensure obj is an instance of cls
    if not isinstance(obj, cls):
        msg = select_msg(msg, "%s is not an instance of %r" %
                         (safe_repr(obj), cls))
        raise AssertionError(msg)


def assert_is_not_instance(obj, cls, msg=None):
    # Ensure obj is not an instance of cls
    if isinstance(obj, cls):
        msg = select_msg(msg, "%s is an instance of %r" %
                         (safe_repr(obj), cls))
        raise AssertionError(msg)


def assert_regexp_matches(text, regexp, msg=None):
    # Get the regular expression
    regexp = make_re(regexp)

    # Does it match?
    if not regexp.search(text):
        msg = select_msg(msg, "'%s' does not match text %s" %
                         (regexp.pattern, safe_repr(text)))
        raise AssertionError(msg)


def assert_not_regexp_matches(text, regexp, msg=None):
    # Get the regular expression
    regexp = make_re(regexp)

    # Does it match?
    match = regexp.search(text)
    if match:
        msg = select_msg(msg, "'%s' matches text %r from %s" %
                         (regexp.pattern, text[match.start():match.end()],
                          safe_repr(text)))
        raise AssertionError(msg)
