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
    Modo incremental: preserva linhas de verificações anteriores e adiciona novas linhas.
    """

    @staticmethod
    def exportar(nome_modulo: str, linhas: List[Dict[str, Any]]) -> str:
        """
        Salva as linhas fornecidas em 'data/outputs/<nome_modulo>.xlsx' em modo incremental.
        Se a planilha já existir, preserva os dados históricos e acrescenta as novas linhas,
        atualizando registros já existentes sem perda de histórico e sem duplicatas vazias.
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

        # Converte valores novos para string para consistência com dados lidos
        for col in df_novos.columns:
            df_novos[col] = df_novos[col].astype(str)

        # Se já existe o arquivo de saída, lê os dados existentes para acumular
        if caminho_saida.exists() and caminho_saida.stat().st_size > 0:
            try:
                df_existente = pd.read_excel(caminho_saida, dtype=str)
            except Exception:
                df_existente = pd.DataFrame()
        else:
            df_existente = pd.DataFrame()

        if not df_existente.empty:
            # Garante que todas as colunas de ambos sejam unificadas
            df_combinado = pd.concat([df_existente, df_novos], ignore_index=True)

            # Localiza colunas chave para tratamento inteligente de duplicatas
            col_proc = next((c for c in df_combinado.columns if "processo" in c.lower()), None)
            col_ata = next((c for c in df_combinado.columns if "ata" in c.lower() and "data" not in c.lower()), None)
            col_doc = next((c for c in df_combinado.columns if "documento" in c.lower()), None)
            col_status = next((c for c in df_combinado.columns if "status" in c.lower()), None)

            # Se um processo agora possui NOVA_ATA_LOCALIZADA, remove linha provisória SEM_NOVAS_ATAS ou ERRO
            if col_proc and col_status:
                processos_com_nova_ata = set(
                    df_combinado[df_combinado[col_status] == "NOVA_ATA_LOCALIZADA"][col_proc].dropna().unique()
                )
                if processos_com_nova_ata:
                    mascara_obsoleta = (
                        df_combinado[col_proc].isin(processos_com_nova_ata) &
                        (df_combinado[col_status].isin(["SEM_NOVAS_ATAS", "ERRO_ABERTURA", "ERRO_EXECUCAO"]))
                    )
                    df_combinado = df_combinado[~mascara_obsoleta]

                # Se um processo que deu erro antes agora teve verificação com sucesso (mesmo sem novas atas)
                processos_verificados = set(
                    df_combinado[df_combinado[col_status].isin(["NOVA_ATA_LOCALIZADA", "SEM_NOVAS_ATAS"])][col_proc].dropna().unique()
                )
                if processos_verificados:
                    mascara_erro_resolvido = (
                        df_combinado[col_proc].isin(processos_verificados) &
                        df_combinado[col_status].str.startswith("ERRO")
                    )
                    df_combinado = df_combinado[~mascara_erro_resolvido]

            # Define chaves para evitar duplicar a exata mesma ata/registro
            chaves_dedup = []
            if col_proc:
                chaves_dedup.append(col_proc)
            if col_ata:
                chaves_dedup.append(col_ata)
            elif col_doc:
                chaves_dedup.append(col_doc)

            if chaves_dedup:
                # Mantém o registro mais recente (keep='last') atualizando timestamps e dados complementares
                df_final = df_combinado.drop_duplicates(subset=chaves_dedup, keep="last")
            else:
                df_final = df_combinado.drop_duplicates(keep="last")
        else:
            df_final = df_novos

        # Função auxiliar de salvamento com formatação e auto-ajuste de colunas
        def _salvar_arquivo(destino: Path, df_salvar: pd.DataFrame) -> None:
            with pd.ExcelWriter(destino, engine="openpyxl") as writer:
                nome_aba = nome_modulo[:31]
                df_salvar.to_excel(writer, sheet_name=nome_aba, index=False)
                worksheet = writer.sheets[nome_aba]
                for col in worksheet.columns:
                    max_len = max(len(str(cell.value or "")) for cell in col)
                    col_letter = col[0].column_letter
                    worksheet.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 60)

        # Salva no arquivo de saída
        try:
            _salvar_arquivo(caminho_saida, df_final)
            return str(caminho_saida)
        except PermissionError:
            # Caso o arquivo esteja aberto no Excel pelo usuário, salva com timestamp alternativo
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            caminho_alternativo = OUTPUTS_DIR / f"{nome_modulo}_{ts}.xlsx"
            _salvar_arquivo(caminho_alternativo, df_final)
            print(f"[AVISO] '{caminho_saida.name}' estava aberto no Excel. Dados salvos como '{caminho_alternativo.name}'.")
            return str(caminho_alternativo)
