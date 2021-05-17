import pytest
from scraper.circuit_breaker import CircuitBreaker, CircuitBreakerOffException, ShortCircuit
from multiprocessing import Pool
import random
import time

name = 'test_circuit_breaker'

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

    breaker = CircuitBreaker(name=name, on=on_func, off=noop)
    breaker.clear()
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

    breaker = CircuitBreaker(name=name, on=on_func, off=noop)
    breaker.clear()

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
    breaker.clear()
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

    breaker = CircuitBreaker(name=name, on=on_func, off=off_func, trigger=1)
    breaker.clear()

    # When
    ignore_exception(lambda: breaker(8, 6, 'Hey', salut="bonjour"))
    actual = breaker(8, 6, 'Hey', salut="bonjour")

    # Then
    assert off_args == (8, 6, 'Hey')
    assert off_kwargs == { 'salut': "bonjour" }
    assert actual == "OFF"

def test_turns_off_if_too_long ():
    # Given
    off_count = 0
    on_count = 0
    time_limit = 0.1

    def off_func (*args, **kwargs):
        nonlocal off_count
        off_count += 1
        return "OFF"

    def on_func (*args, **kwargs):
        nonlocal on_count
        on_count += 1
        time.sleep(0.04 * on_count)
        return 'ON'

    breaker = CircuitBreaker(name=name, on=on_func, off=off_func, trigger=1, time_limit=time_limit)
    breaker.clear()

    # When
    breaker() # ON in 40ms
    breaker() # ON in 80ms
    breaker() # ON in 120ms -> fail
    breaker() # OFF

    # Then
    assert off_count == 1
    assert on_count == 3

@ShortCircuit('short_circuit_test', trigger=3, release=3)
def breakable (*args, **kwargs):
    raise Exception("SomeError")

def run(chunk):
    try:
        breakable()
        return 'on'
    except CircuitBreakerOffException:
        return 'off'
    except Exception:
        return 'on'

def test_breaks_accross_processes ():
    # Given
    breakable.clear()

    # When
    actual = None
    with Pool(4) as pool:
        actual = pool.map(run, range(15), 1)

    # Then
    times_on = [on for on in actual if on == "on"]
    times_off = [off for off in actual if off == "off"]
    assert len(times_on) == 9
    assert len(times_off) == 6


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

    breaker = CircuitBreaker(name=name, on=on_func, off=off_func, trigger=1)
    breaker.clear()

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
    actual = breaker()

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

    breaker = CircuitBreaker(name=name, on=on_func, off=off_func, trigger=3, release=5)
    breaker.clear()

    # When
    ignore_exception(lambda: breaker()) # fail ON
    ignore_exception(lambda: breaker()) # fail ON
    ignore_exception(lambda: breaker()) # fail ON
    breaker() # pass OFF
    breaker() # pass OFF
    breaker() # pass OFF
    breaker() # pass OFF
    breaker() # pass OFF
    ignore_exception(lambda: breaker()) # fail ON
    ignore_exception(lambda: breaker()) # fail ON
    ignore_exception(lambda: breaker()) # fail ON
    breaker() # pass OFF
    breaker() # pass OFF
    breaker() # pass OFF
    breaker() # pass OFF
    breaker() # pass OFF
    actual = breaker() # pass ON

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

    breaker = CircuitBreaker(name=name, on=on_func, off=off_func, trigger=3, release=5)
    breaker.clear()

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

