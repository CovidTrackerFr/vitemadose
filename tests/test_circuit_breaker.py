import pytest
from scraper.circuit_breaker import CircuitBreaker, CircuitBreakerOffException

def noop():
    pass
def true():
    return True
def false():
    return False

def test_calls_on_function ():
    # Given
    on_count = 0
    def on_func ():
        nonlocal on_count
        on_count = on_count +1

    breaker = CircuitBreaker(on=on_func, off=noop)
    # When
    breaker()
    breaker()
    breaker()
    breaker()
    breaker()

    # Then
    assert on_count == 5

def test_calls_on_function_with_args ():
    # Given
    on_args = None
    on_kwargs = None
    ret = { "some": 'return value' }

    def on_func (*args, **kwargs):
        nonlocal on_args, on_kwargs, ret
        on_args = args
        on_kwargs = kwargs
        return ret

    breaker = CircuitBreaker(on=on_func, off=noop)

    # When
    actual = breaker(8, 6, 'Hey', salut="bonjour")

    # Then
    assert on_args == (8, 6, 'Hey')
    assert on_kwargs == { 'salut': "bonjour" }
    assert actual == ret

def test_calls_default_off_behaviour ():
    # Given
    expected_error_msg = f"CircuitBreaker 'test name' is currently off"
    def on_func (*args, **kwargs):
        raise Exception("some error")

    breaker = CircuitBreaker(on=on_func, name="test name", trigger=1)
    actual = None

    # When
    ignore_exception(lambda: breaker())
    try:
        breaker()
    except Exception as e:
        actual = e

    # Then
    assert True == isinstance(actual, CircuitBreakerOffException)
    assert actual.message == expected_error_msg

def test_calls_off_function_with_args ():
    # Given
    off_args = None
    off_kwargs = None

    def off_func (*args, **kwargs):
        nonlocal off_args, off_kwargs
        off_args = args
        off_kwargs = kwargs
        return "OFF"

    def on_func (*args, **kwargs):
        raise Exception("SomeError")

    breaker = CircuitBreaker(on=on_func, off=off_func, trigger=1)

    # When
    ignore_exception(lambda: breaker(8, 6, 'Hey', salut="bonjour"))
    actual = breaker(8, 6, 'Hey', salut="bonjour")

    # Then
    assert off_args == (8, 6, 'Hey')
    assert off_kwargs == { 'salut': "bonjour" }
    assert actual == "OFF"

def test_calls_on_function_again ():
    # Given
    off_count = 0
    on_count = 0

    def off_func (*args, **kwargs):
        nonlocal off_count
        off_count += 1

    def on_func (*args, **kwargs):
        nonlocal on_count
        on_count += 1
        if on_count == 1:
            raise Exception('Some Error')
        return 'ON'

    breaker = CircuitBreaker(on=on_func, off=off_func, trigger=1)

    # When
    ignore_exception(lambda: breaker())
    breaker()
    breaker()
    breaker()
    breaker()
    breaker()
    breaker()
    breaker()
    breaker()
    breaker()
    breaker()
    actual = actual = breaker()

    # Then
    assert actual == "ON"
    assert on_count == 2
    assert off_count == 10

def test_calls_off_after_trigger ():
    # Given
    off_count = 0
    on_count = 0

    def off_func (*args, **kwargs):
        nonlocal off_count
        off_count += 1

    def on_func (*args, **kwargs):
        nonlocal on_count
        on_count += 1
        if on_count <= 6:
            raise Exception('Some Error')
        return 'ON'

    breaker = CircuitBreaker(on=on_func, off=off_func, trigger=3, release=5)

    # When
    ignore_exception(lambda: breaker()) # fail
    ignore_exception(lambda: breaker()) # fail
    ignore_exception(lambda: breaker()) # fail
    breaker() # pass
    breaker() # pass
    breaker() # pass
    breaker() # pass
    breaker() # pass
    ignore_exception(lambda: breaker()) # fail
    ignore_exception(lambda: breaker()) # fail
    ignore_exception(lambda: breaker()) # fail
    breaker() # pass
    breaker() # pass
    breaker() # pass
    breaker() # pass
    breaker() # pass
    actual = breaker()

    # Then
    assert on_count == 7
    assert off_count == 10
    assert actual == "ON"

def test_calls_off_after_soft_trigger ():
    # Given
    off_count = 0
    on_count = 0

    def off_func (*args, **kwargs):
        nonlocal off_count
        off_count += 1

    def on_func (*args, **kwargs):
        nonlocal on_count
        on_count += 1
        if (on_count % 3) == 0:
            return 'ON'
        else:
            raise Exception('Some Error')

    breaker = CircuitBreaker(on=on_func, off=off_func, trigger=3, release=5)

    # When
    ignore_exception(lambda: breaker()) # ON fail
    ignore_exception(lambda: breaker()) # ON fail
    breaker() # ON pass
    ignore_exception(lambda: breaker()) # ON fail
    ignore_exception(lambda: breaker()) # ON fail
    breaker() # OFF pass
    breaker() # OFF pass
    breaker() # OFF pass
    breaker() # OFF pass
    breaker() # OFF pass
    actual = breaker() # ON pass

    # Then
    assert on_count == 6
    assert off_count == 5
    assert actual == "ON"


def ignore_exception (func):
    try:
        return func()
    except Exception:
        pass

