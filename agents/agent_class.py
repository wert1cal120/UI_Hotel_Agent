from abc import ABC, abstractmethod

class Agent(ABC):
    @abstractmethod
    def decide(self, percept):
        pass