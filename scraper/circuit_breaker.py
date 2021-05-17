from collections import deque

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
    def __init__(self, on, off=None, trigger=3, release=10, name=None):
        self.policies = deque(["ON" for _ in range(trigger)])
        self.on_func = on
        self.off_func = off
        self.release = release
        self.trigger = trigger
        self.name = name
        if name is None and off is None:
            raise Exception("You must specify a name if you don't specify a `off` for CircuitBreaker")

    def clear(self):
        pass

    def __call__(self, *args, **kwargs):
        return self.call(*args, **kwargs)

    def call(self, *args, **kwargs):
        policy = self.policies.popleft()
        if policy == 'OFF':
            return self.call_off(*args, **kwargs)

        try:
            value = self.on_func(*args, **kwargs)

            self.policies.append('ON')
            if len(self.policies) < self.trigger:
                self.policies.append('ON')
            return value

        except Exception as e:
            if len(self.policies) == 0:
                for _ in range(self.release):
                    self.policies.append('OFF')
                for _ in range(self.trigger):
                    self.policies.append('ON')

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
