"""
Interface base para módulos exportadores de resultados.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

class BaseExporter(ABC):
    @staticmethod
    @abstractmethod
    def exportar(nome_modulo: str, linhas: List[Dict[str, Any]]) -> str:
        """
        Exporta a lista de registros estruturados e retorna o caminho de saída gerado.
        """
        pass
