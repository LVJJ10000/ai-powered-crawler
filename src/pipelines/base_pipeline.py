from abc import ABC, abstractmethod


class BasePipeline(ABC):
    @abstractmethod
    async def run(self, *args, **kwargs):
        raise NotImplementedError

