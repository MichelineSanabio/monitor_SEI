"""
Contrato Base (Interface Abstrata) para todos os módulos de monitoramento no SEI.
Garante a arquitetura modular plug-and-play do sistema (RN02).
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

class BaseMonitor(ABC):
    """
    Interface obrigatória para qualquer tipo de monitoramento no SEI.
    Novos monitores criados na pasta 'monitors/' devem herdar desta classe.
    """

    @property
    @abstractmethod
    def nome_identificador(self) -> str:
        """
        Identificador único e padronizado do módulo (ex: 'MonitorAndamentos').
        Regra RN05: Este nome define automaticamente o nome do arquivo exportado (ex: MonitorAndamentos.xlsx).
        """
        pass

    @property
    @abstractmethod
    def descricao(self) -> str:
        """
        Nome amigável exibido na caixa de seleção da interface gráfica com o usuário.
        Exemplo: 'Monitoramento de Andamentos Gerais'
        """
        pass

    @abstractmethod
    def carregar_alvos(self, params: Dict[str, Any]) -> List[str]:
        """
        Obtém a lista de processos que serão verificados.
        Pode ler de planilha Excel local, Google Sheets ou raspar do próprio SEI.
        Retorna uma lista limpa de strings (números de processo).
        """
        pass

    def obter_link_processo(self, numero_processo: str) -> str:
        """
        Retorna o link direto do processo (se fornecido na fonte de dados).
        Caso retorne string vazia, o sistema utilizará a busca pelo número do processo.
        """
        return ""

    @abstractmethod
    def inspecionar_processo(self, navigator: Any, numero_processo: str) -> Dict[str, Any]:
        """
        Executa a lógica específica de raspagem nos iframes do processo.
        O objeto 'navigator' já posicionou o navegador no contexto correto do processo.
        
        Retorna um dicionário contendo os dados brutos extraídos.
        """
        pass

    @abstractmethod
    def estruturar_linhas_exportacao(self, resultados: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Converte a lista de resultados brutos em registros tabulares uniformes
        prontos para serem salvos em planilha Excel.
        """
        pass
