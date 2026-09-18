"""
Módulo de Monitoramento de Atas Criadas (MonitorAtas).
Identifica se novos documentos do tipo 'Ata' ou 'Termo' foram anexados aos processos.
"""

from typing import Any, Dict, List
from core.base_monitor import BaseMonitor
from inputs.excel_reader import ExcelReader

class MonitorAtas(BaseMonitor):
    """
    Varre a árvore de documentos do processo procurando por Atas de Reunião, Deliberação ou Oitiva.
    """

    @property
    def nome_identificador(self) -> str:
        return "MonitorAtas"

    @property
    def descricao(self) -> str:
        return "Monitoramento de Atas Criadas"

    def carregar_alvos(self, params: Dict[str, Any]) -> List[str]:
        leitor = ExcelReader()
        return leitor.ler_processos(params.get("caminho_arquivo", ""))

    def inspecionar_processo(self, navigator: Any, numero_processo: str) -> Dict[str, Any]:
        """
        Lê todos os nós da árvore e filtra documentos contendo a palavra 'Ata'.
        """
        todos_docs = navigator.extrair_nos_arvore()
        atas_encontradas = [doc for doc in todos_docs if "ata" in doc.lower()]

        return {
            "total_atas": len(atas_encontradas),
            "ultima_ata": atas_encontradas[-1] if atas_encontradas else "Nenhuma ata localizada",
            "todas_atas": " ; ".join(atas_encontradas) if atas_encontradas else ""
        }

    def estruturar_linhas_exportacao(self, resultados: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Formata os dados para a planilha 'MonitorAtas.xlsx'.
        """
        linhas = []
        for r in resultados:
            linhas.append({
                "Processo": r.get("processo", ""),
                "Quantidade de Atas": r.get("total_atas", 0),
                "Última Ata Localizada": r.get("ultima_ata", "N/D"),
                "Relação de Atas": r.get("todas_atas", ""),
                "Status": r.get("status", "CONCLUÍDO"),
                "Observações": r.get("detalhe", "")
            })
        return linhas
