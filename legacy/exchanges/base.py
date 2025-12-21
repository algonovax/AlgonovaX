from abc import ABC, abstractmethod

class BaseExchange(ABC):
    @abstractmethod
    def execute_trade(self, symbol: str, side: str, amount: float, price: float = None):
        pass
