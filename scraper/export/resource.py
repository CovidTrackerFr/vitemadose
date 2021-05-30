from abc import ABC, abstractmethod

class Resource(ABC):
    @abstractmethod
    def asdict():
        return {}
