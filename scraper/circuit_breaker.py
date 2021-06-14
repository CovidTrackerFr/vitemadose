from collections import deque
from diskcache import Deque
import time
import os
import sys

sys.setrecursionlimit(10 ** 8)


def ShortCircuit(name, trigger=3, release=10, time_limit=120):
    def decorator(fn):
        breaker = CircuitBreaker(on=fn, name=name, trigger=trigger, release=release, time_limit=time_limit)
        return breaker

    return decorator


# Circuit Breaker helper
# When ON
#  - delegates to the `on` parameter function
#  - if `on()` fails it adds the failure to its count
#  - if this count exceeds `trigger`, the breaker becomes OFF
#  - if `on()` succeeds, it decrements the count
# When OFF
#  - delefates to the `off` parameter function
#  - counts the numbers of times `off` is called
#  - if this counts exceeds `release`, the breaker becomes ON
class CircuitBreaker:
    def __init__(self, name, on, off=None, trigger=3, release=10, time_limit=120):
        self.policies = Deque(trigger * ["ON"], f"/tmp/breaker/{name}")
        self.time_limit = time_limit
        self.on_func = on
        self.off_func = off
        self.release = release
        self.trigger = trigger
        self.name = name
        self.enabled = True

    def clear(self):
        with self.policies.transact():
            self.policies.clear()
            self.policies += ["ON"] * self.trigger

    def __str__(self):
        return f"[{self.name}:{os.getpid():5}] {[x for x in self.policies]}"

    def __call__(self, *args, **kwargs):
        return self.call(*args, **kwargs)

    def call(self, *args, **kwargs):
        if not self.enabled:
            return self.on_func(*args, **kwargs)

        policy = self.get_policy()
        if policy == "OFF":
            return self.call_off(*args, **kwargs)

        error = None
        value = None
        try:
            start_time = time.time()
            value = self.on_func(*args, **kwargs)
            elapsed_time = time.time() - start_time
            if elapsed_time > self.time_limit:
                raise CircuitBreakerTooLongException(self.name)

            with self.policies.transact():
                self.policies.append("ON")
                if len(self.policies) < self.trigger:
                    self.policies.append("ON")
            return value

        except CircuitBreakerTooLongException:
            self.count_error()
            return value
        except Exception as e:
            self.count_error()
            raise e

    def breaker_enabled(self, enabled):
        self.enabled = enabled

    def get_policy(self):
        start_time = time.time()
        while (time.time() - start_time) < self.time_limit:
            with self.policies.transact():
                try:
                    return self.policies.popleft()
                except IndexError:
                    time.sleep(0.200)
        return "OFF"

    def count_error(self):
        with self.policies.transact():
            if len(self.policies) == 0:
                self.policies += ["OFF"] * self.release
                self.policies += ["ON"] * self.trigger

    def call_off(self, *args, **kwargs):
        if self.off_func is not None:
            return self.off_func(*args, **kwargs)
        else:
            raise CircuitBreakerOffException(self.name)


class CircuitBreakerOffException(RuntimeError):
    def __init__(self, name):
        msg = f"CircuitBreaker '{name}' is currently off"
        super().__init__(self, msg)
        self.message = msg
        self.name = name


class CircuitBreakerTooLongException(RuntimeError):
    def __init__(self, name):
        msg = f"CircuitBreaker '{name}' execution took too long"
        super().__init__(self, msg)
        self.message = msg
        self.name = name
