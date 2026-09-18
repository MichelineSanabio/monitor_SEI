"""
Módulo de Monitoramento de Atas Feitas (Monitoramento atas feitas).
Verifica a árvore do processo no SEI e identifica novas atas geradas além da maior ata já registrada na planilha de origem.
"""

from pathlib import Path
from typing import Any, Dict, List, Tuple
import re
import pandas as pd
from core.base_monitor import BaseMonitor
from config.settings import INPUTS_DIR

class MonitorAtasFeitas(BaseMonitor):
    """
    Monitor especializado em identificar novas 'Atas de Reunião' geradas após a última ata
    registrada para cada processo na planilha de origem.
    """

    def __init__(self):
        # Mapeamento do maior número de ata já conhecido por processo: { "processo": maior_numero_ata }
        self.processos_max_ata: Dict[str, int] = {}
        self.caminho_arquivo_customizado: str = ""

    @property
    def nome_identificador(self) -> str:
        # Define o nome da planilha de saída: data/outputs/MonitoramentoAtasFeitas.xlsx (RN05)
        return "MonitoramentoAtasFeitas"

    @property
    def descricao(self) -> str:
        # Nome exibido na interface gráfica do usuário
        return "Monitoramento atas feitas"

    def carregar_alvos(self, params: Dict[str, Any]) -> List[str]:
        """
        Lê a planilha de origem para obter os processos e calcular a maior ata já registrada
        para cada processo.
        Estrutura esperada da planilha origem:
          - Coluna 1: Número do Processo
          - Coluna 2: Data da Primeira Assinatura
          - Coluna 3: Número da Ata
        """
        caminho = Path(self.caminho_arquivo_customizado) if self.caminho_arquivo_customizado else (INPUTS_DIR / "origem_atas.xlsx")

        if not caminho.exists():
            # Tenta encontrar qualquer arquivo de atas ou processos na pasta de inputs
            arquivos = list(INPUTS_DIR.glob("origem_atas*.xlsx")) + list(INPUTS_DIR.glob("processos*.xlsx")) + list(INPUTS_DIR.glob("*.xlsx"))
            if arquivos:
                caminho = arquivos[0]
            else:
                return []

        try:
            df = pd.read_excel(caminho, dtype=str)
        except Exception as e:
            print(f"Erro ao ler planilha de origem {caminho}: {e}")
            return []

        if df.empty:
            return []

        # Identifica as colunas relevantes
        # Coluna 0: Processo
        # Coluna 2: Número da Ata (se houver pelo menos 3 colunas)
        col_processo = df.columns[0]
        col_ata = None

        if len(df.columns) >= 3:
            col_ata = df.columns[2]
        else:
            # Procura coluna que contenha 'ata' ou 'numero' no cabeçalho
            for c in df.columns:
                if "ata" in str(c).lower() or "numero" in str(c).lower():
                    col_ata = c
                    break

        self.processos_max_ata.clear()

        for _, linha in df.iterrows():
            proc_val = str(linha[col_processo]).strip()
            if not proc_val or proc_val.lower() == "nan" or proc_val.lower().startswith("processo"):
                continue

            num_ata = 0
            if col_ata and pd.notna(linha[col_ata]):
                val_ata = str(linha[col_ata]).strip()
                match = re.search(r"(\d+)", val_ata)
                if match:
                    num_ata = int(match.group(1))

            # Atualiza o maior número de ata já conhecido para este processo
            if proc_val not in self.processos_max_ata:
                self.processos_max_ata[proc_val] = num_ata
            else:
                if num_ata > self.processos_max_ata[proc_val]:
                    self.processos_max_ata[proc_val] = num_ata

        # Retorna a lista única e ordenada de processos a inspecionar
        return list(self.processos_max_ata.keys())

    def inspecionar_processo(self, navigator: Any, numero_processo: str) -> Dict[str, Any]:
        """
        Percorre a árvore de documentos procurando por 'Ata de Reunião [número]'.
        Filtra apenas atas com número maior que a maior ata já conhecida para aquele processo.
        Para cada nova ata localizada, extrai a data da primeira assinatura.
        """
        max_ata_conhecida = self.processos_max_ata.get(numero_processo, 0)
        
        # Obtém todos os nós da árvore com elementos Selenium para possibilitar cliques
        nos_detalhados = navigator.listar_elementos_nos_arvore()
        novas_atas_encontradas = []

        # Regex para identificar 'Ata de Reunião [número]' ou 'Ata [número]'
        padrao_ata = re.compile(r"ata(?:\s+de\s+reuni[ãa]o)?\s*(?:n[º°.]?\s*|-?\s*)(\d+)", re.IGNORECASE)

        for item in nos_detalhados:
            texto_no = item["texto"]
            elemento_no = item["elemento"]

            match = padrao_ata.search(texto_no)
            if match:
                num_ata = int(match.group(1))

                # Regra: Somente atas com número maior que a última indicada na planilha de origem
                if num_ata > max_ata_conhecida:
                    # Extrai data da primeira assinatura e nome do secretário clicando no documento
                    detalhes_ass = navigator.extrair_detalhes_assinatura_documento(
                        elemento_no=elemento_no,
                        nome_documento=texto_no
                    )
                    data_assinatura = detalhes_ass.get("data_assinatura", "")
                    nome_secretario = detalhes_ass.get("secretario", "")

                    novas_atas_encontradas.append({
                        "numero_ata": num_ata,
                        "data_primeira_assinatura": data_assinatura if data_assinatura else "Não assinada / Minuta",
                        "secretario": nome_secretario,
                        "nome_documento_sei": texto_no,
                        "assinado": bool(data_assinatura)
                    })

        # Ordena as novas atas encontradas pelo número da ata
        novas_atas_encontradas.sort(key=lambda x: x["numero_ata"])

        return {
            "max_ata_origem": max_ata_conhecida,
            "novas_atas": novas_atas_encontradas,
            "quantidade_novas_atas": len(novas_atas_encontradas)
        }

    def estruturar_linhas_exportacao(self, resultados: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Estrutura os dados para exportação com a nova 4ª coluna 'Secretário':
        1. Número do Processo
        2. Data da Primeira Assinatura
        3. Número da Ata
        4. Secretário
        """
        linhas_exportar = []

        for r in resultados:
            processo = r.get("processo", "")
            status = r.get("status", "")
            novas_atas = r.get("novas_atas", [])

            if status != "SUCESSO":
                # Registra pendência ou erro de acesso ao processo sigiloso
                linhas_exportar.append({
                    "Número do Processo": processo,
                    "Data da Primeira Assinatura": "",
                    "Número da Ata": "",
                    "Secretário": "",
                    "Nome do Documento no SEI": "",
                    "Status": status,
                    "Observações": r.get("detalhe", "Falha de acesso ao processo")
                })
                continue

            if not novas_atas:
                # Caso nenhuma ata nova (além da maior conhecida) tenha sido encontrada
                max_origem = r.get("max_ata_origem", 0)
                linhas_exportar.append({
                    "Número do Processo": processo,
                    "Data da Primeira Assinatura": "",
                    "Número da Ata": f"Sem novas atas (última: {max_origem})",
                    "Secretário": "",
                    "Nome do Documento no SEI": "",
                    "Status": "SEM_NOVAS_ATAS",
                    "Observações": f"Nenhuma ata superior à Ata {max_origem} localizada no SEI"
                })
            else:
                for ata in novas_atas:
                    linhas_exportar.append({
                        "Número do Processo": processo,
                        "Data da Primeira Assinatura": ata["data_primeira_assinatura"],
                        "Número da Ata": ata["numero_ata"],
                        "Secretário": ata.get("secretario", ""),
                        "Nome do Documento no SEI": ata["nome_documento_sei"],
                        "Status": "NOVA_ATA_LOCALIZADA",
                        "Observações": "Assinatura confirmada" if ata["assinado"] else "Minuta pendente de assinatura"
                    })

        return linhas_exportar
