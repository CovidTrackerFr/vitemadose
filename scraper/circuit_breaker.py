from collections import deque
from diskcache import Deque
import os

def ShortCircuit(name, trigger=3, release=10):
    def decorator(fn):
        breaker = CircuitBreaker(on=fn, name=name, trigger=trigger, release=release)
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
    def __init__(self, name, on, off=None, trigger=3, release=10):
        self.policies = Deque(["ON" for _ in range(trigger)], f'/tmp/breaker/{name}')
        self.on_func = on
        self.off_func = off
        self.release = release
        self.trigger = trigger
        self.name = name
    def clear(self):
        with self.policies.transact():
            self.policies.clear()
            self.policies += ['ON' for _ in range(self.trigger)]

    def __str__(self):
        return f"[{self.name}:{os.getpid():5}] {[x for x in self.policies]}"

    def __call__(self, *args, **kwargs):
        return self.call(*args, **kwargs)

    def call(self, *args, **kwargs):
        with self.policies.transact():
            policy = self.policies.popleft()

        if policy == 'OFF':
            return self.call_off(*args, **kwargs)

        try:
            value = self.on_func(*args, **kwargs)

            with self.policies.transact():
                self.policies.append('ON')
                if len(self.policies) < self.trigger:
                    self.policies.append('ON')
            return value

        except Exception as e:
            with self.policies.transact():
                if len(self.policies) == 0:
                    self.policies += ['OFF' for _ in range(self.release)]
                    self.policies += ['ON' for _ in range(self.trigger)]
            raise e


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
