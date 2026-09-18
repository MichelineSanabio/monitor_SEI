"""
Módulo de Monitoramento de Andamentos Gerais (MonitorAndamentos).
Verifica a árvore de documentos e a linha mais recente da tabela de histórico de tramitação.
"""

from typing import Any, Dict, List
from core.base_monitor import BaseMonitor
from inputs.excel_reader import ExcelReader

class MonitorAndamentos(BaseMonitor):
    """
    Inspeciona processos para coletar o último nó da árvore e a última movimentação registrada.
    """

    @property
    def nome_identificador(self) -> str:
        return "MonitorAndamentos"

    @property
    def descricao(self) -> str:
        return "Monitoramento de Andamentos Gerais"

    def carregar_alvos(self, params: Dict[str, Any]) -> List[str]:
        """Carrega os processos a partir da planilha Excel padrão ou caminho informado."""
        leitor = ExcelReader()
        caminho_customizado = params.get("caminho_arquivo", "")
        return leitor.ler_processos(caminho_customizado)

    def inspecionar_processo(self, navigator: Any, numero_processo: str) -> Dict[str, Any]:
        """
        Navega nos iframes do processo e extrai o último documento e a tramitação do histórico.
        """
        ultimo_doc = navigator.obter_ultimo_documento_arvore()
        ultimo_andamento = navigator.extrair_ultimo_andamento_historico()

        return {
            "ultimo_documento": ultimo_doc,
            "ultimo_andamento": ultimo_andamento
        }

    def estruturar_linhas_exportacao(self, resultados: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Formata os dados para a planilha 'MonitorAndamentos.xlsx'.
        """
        linhas = []
        for r in resultados:
            linhas.append({
                "Processo": r.get("processo", ""),
                "Último Documento Juntado": r.get("ultimo_documento", "N/D"),
                "Último Andamento no Histórico": r.get("ultimo_andamento", "N/D"),
                "Status da Inspeção": r.get("status", "CONCLUÍDO"),
                "Observações": r.get("detalhe", "")
            })
        return linhas
