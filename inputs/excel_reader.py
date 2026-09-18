"""
Leitor de Processos via Planilhas Locais (Excel .xlsx / .csv).
Identifica colunas de processos automaticamente ou lê a primeira coluna útil.
"""

from pathlib import Path
from typing import List, Union
import pandas as pd
from .base_reader import BaseReader
from config.settings import INPUTS_DIR

class ExcelReader(BaseReader):
    """
    Carrega números de processo a partir de arquivos Excel ou CSV locais.
    """

    COLUNAS_PADRAO = ["processo", "processos", "numero", "n_processo", "sei", "num_processo"]

    def ler_processos(self, caminho_arquivo: Union[str, Path] = "") -> List[str]:
        """
        Lê a planilha informada ou busca automaticamente na pasta 'data/inputs/'.
        """
        caminho = Path(caminho_arquivo) if caminho_arquivo else (INPUTS_DIR / "processos.xlsx")

        if not caminho.exists():
            # Se não existir, tenta procurar qualquer arquivo .xlsx ou .csv na pasta data/inputs
            arquivos = list(INPUTS_DIR.glob("*.xlsx")) + list(INPUTS_DIR.glob("*.csv"))
            if arquivos:
                caminho = arquivos[0]
            else:
                return []

        try:
            if caminho.suffix.lower() == ".csv":
                df = pd.read_csv(caminho, dtype=str)
            else:
                df = pd.read_excel(caminho, dtype=str)

            # Localiza a coluna que contém os números de processo
            coluna_alvo = None
            for col in df.columns:
                if str(col).strip().lower() in self.COLUNAS_PADRAO:
                    coluna_alvo = col
                    break

            # Se não encontrou pelo nome do cabeçalho, utiliza a primeira coluna
            if not coluna_alvo and len(df.columns) > 0:
                coluna_alvo = df.columns[0]

            if not coluna_alvo:
                return []

            processos_brutos = df[coluna_alvo].dropna().tolist()
            
            # Limpeza e formatação de strings
            processos_limpos = [
                str(p).strip() for p in processos_brutos 
                if str(p).strip() and not str(p).strip().lower().startswith("processo")
            ]

            return processos_limpos

        except Exception as e:
            print(f"Erro ao ler arquivo de processos {caminho}: {e}")
            return []
