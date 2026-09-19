"""
Exportador de Resultados para Planilhas Excel (.xlsx).
Cumpre a regra RN05 (Convenção sobre Configuração: nome do arquivo igual ao nome do módulo).
"""

from pathlib import Path
from typing import Any, Dict, List
import pandas as pd
from datetime import datetime
from .base_exporter import BaseExporter
from config.settings import OUTPUTS_DIR

class ExcelExporter(BaseExporter):
    """
    Gera ou atualiza planilha Excel nomeada conforme o identificador do módulo.
    """

    @staticmethod
    def exportar(nome_modulo: str, linhas: List[Dict[str, Any]]) -> str:
        """
        Salva as linhas fornecidas em 'data/outputs/<nome_modulo>.xlsx'.
        Adiciona timestamp de execução para auditoria.
        """
        if not linhas:
            return ""

        # Garante nome padronizado (RN05)
        nome_arquivo = f"{nome_modulo}.xlsx"
        caminho_saida = OUTPUTS_DIR / nome_arquivo

        df_novos = pd.DataFrame(linhas)

        # Adiciona coluna de data/hora da verificação se não existir
        if "data_consulta" not in df_novos.columns:
            df_novos["data_consulta"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        # Salva o arquivo Excel com formatação básica
        try:
            with pd.ExcelWriter(caminho_saida, engine="openpyxl") as writer:
                df_novos.to_excel(writer, sheet_name=nome_modulo[:31], index=False)
            return str(caminho_saida)
        except PermissionError:
            # Caso o arquivo esteja aberto no Excel pelo usuário, salva com timestamp alternativo
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            caminho_alternativo = OUTPUTS_DIR / f"{nome_modulo}_{ts}.xlsx"
            with pd.ExcelWriter(caminho_alternativo, engine="openpyxl") as writer:
                df_novos.to_excel(writer, sheet_name=nome_modulo[:31], index=False)
            print(f"[AVISO] '{caminho_saida.name}' estava aberto no Excel. Dados salvos como '{caminho_alternativo.name}'.")
            return str(caminho_alternativo)
