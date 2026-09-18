"""
Interface base para provedores de entrada (leitores de processos).
Desacopla o robô da origem física dos dados (RN03).
"""

from abc import ABC, abstractmethod
from typing import Any, List

class BaseReader(ABC):
    @abstractmethod
    def ler_processos(self, fonte: Any) -> List[str]:
        """
        Lê e retorna uma lista limpa de números de processo em formato string.
        """
        pass
