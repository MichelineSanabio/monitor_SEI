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
        # Mapeamento do link direto por processo: { "processo": "https://..." }
        self.processos_links: Dict[str, str] = {}
        self.caminho_arquivo_customizado: str = ""

    @property
    def nome_identificador(self) -> str:
        # Define o nome da planilha de saída: data/outputs/MonitoramentoAtasFeitas.xlsx (RN05)
        return "MonitoramentoAtasFeitas"

    @property
    def descricao(self) -> str:
        # Nome exibido na interface gráfica do usuário
        return "Monitoramento atas feitas"

    def obter_link_processo(self, numero_processo: str) -> str:
        """Retorna o link direto do processo informado na planilha, se existir."""
        return self.processos_links.get(str(numero_processo).strip(), "")

    def _extrair_hiperlinks_openpyxl(self, caminho: Path) -> Dict[str, str]:
        """Lê hiperlinks nativos embutidos nas células do Excel via openpyxl."""
        links_map: Dict[str, str] = {}
        try:
            import openpyxl
            wb = openpyxl.load_workbook(caminho, data_only=False)
            sheet = wb.active
            headers = [str(c.value or "").strip().lower() for c in sheet[1]]
            idx_proc = 0
            idx_link = None
            for i, h in enumerate(headers):
                if any(t in h for t in ["processo", "proc", "sei"]):
                    idx_proc = i
                    break
            for i, h in enumerate(headers):
                if any(t in h for t in ["link", "url", "href"]):
                    idx_link = i
                    break
            if idx_link is None:
                if len(headers) >= 5:
                    idx_link = 4
                elif len(headers) >= 4:
                    idx_link = 3

            for row in sheet.iter_rows(min_row=2):
                if len(row) <= idx_proc:
                    continue
                proc_val = str(row[idx_proc].value or "").strip()
                if not proc_val or proc_val.lower() == "none" or proc_val.lower().startswith("processo"):
                    continue
                link_val = ""
                if idx_link is not None and len(row) > idx_link:
                    cell = row[idx_link]
                    if cell.hyperlink and cell.hyperlink.target:
                        link_val = str(cell.hyperlink.target).strip()
                    elif cell.value:
                        val_str = str(cell.value).strip()
                        if "http" in val_str or "controlador.php" in val_str:
                            link_val = val_str
                if link_val:
                    links_map[proc_val] = link_val
        except Exception:
            pass
        return links_map

    def carregar_alvos(self, params: Dict[str, Any]) -> List[str]:
        """
        Lê a planilha de origem para obter os processos, calcular a maior ata já registrada
        e capturar o link direto do processo se fornecido (4ª ou 5ª coluna).
        """
        caminho_custom = self.caminho_arquivo_customizado or params.get("caminho") or params.get("arquivo")
        if caminho_custom:
            caminho = Path(caminho_custom)
        else:
            # Procura de forma inteligente arquivos relevantes na pasta data/inputs/
            candidatos = (
                [f for f in INPUTS_DIR.glob("*controle*.xlsx")] +
                [f for f in INPUTS_DIR.glob("*ata*.xlsx") if f.name != "origem_atas.xlsx"] +
                [INPUTS_DIR / "origem_atas.xlsx"] +
                [f for f in INPUTS_DIR.glob("*.xlsx") if f.name != "processos.xlsx"] +
                list(INPUTS_DIR.glob("*.xlsx"))
            )
            arquivos_existentes = [f for f in candidatos if f.exists()]
            caminho = arquivos_existentes[0] if arquivos_existentes else (INPUTS_DIR / "origem_atas.xlsx")

        if not caminho.exists():
            return []

        try:
            df = pd.read_excel(caminho, dtype=str)
        except Exception as e:
            print(f"Erro ao ler planilha de origem {caminho}: {e}")
            return []

        if df.empty:
            return []

        # Identifica as colunas relevantes
        col_processo = None
        col_ata = None
        col_link = None

        for c in df.columns:
            nome_col = str(c).strip().lower()
            if not col_processo and any(termo in nome_col for termo in ["processo", "proc", "sei"]):
                col_processo = c
            # Evita casar a palavra "data" (d-ata) como coluna de ata
            if not col_ata and ("ata" in nome_col) and not any(ignora in nome_col for ignora in ["data", "date", "secretar"]):
                col_ata = c
            if not col_link and any(termo in nome_col for termo in ["link", "url", "href", "acesso"]):
                col_link = c

        if not col_processo and len(df.columns) > 0:
            col_processo = df.columns[0]
        if not col_ata and len(df.columns) >= 3:
            col_ata = df.columns[2]
        if not col_link:
            if len(df.columns) >= 5:
                col_link = df.columns[4]
            elif len(df.columns) >= 4:
                col_link = df.columns[3]

        # Extrai links nativos do Excel se houver
        links_nativos = self._extrair_hiperlinks_openpyxl(caminho)

        self.processos_max_ata.clear()
        self.processos_links.clear()

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

            # Captura link direto se presente
            link_val = ""
            if col_link and pd.notna(linha[col_link]):
                l_cand = str(linha[col_link]).strip()
                if "http" in l_cand.lower() or "controlador.php" in l_cand.lower():
                    link_val = l_cand

            if not link_val and proc_val in links_nativos:
                link_val = links_nativos[proc_val]

            if link_val:
                self.processos_links[proc_val] = link_val

        # Retorna a lista única e ordenada de processos a inspecionar
        return list(self.processos_max_ata.keys())

    def inspecionar_processo(self, navigator: Any, numero_processo: str) -> Dict[str, Any]:
        """
        Percorre a árvore de documentos procurando por Atas de Reunião.
        Suporta tanto números sequenciais de ata quanto IDs numéricos de documentos do SEI (ex: 140451633).
        Para cada nova ata localizada além da maior registrada na origem, extrai data da 1ª assinatura e secretário.
        """
        max_ata_conhecida = self.processos_max_ata.get(numero_processo, 0)
        
        # Obtém todos os nós da árvore com elementos Selenium para possibilitar cliques
        nos_detalhados = navigator.listar_elementos_nos_arvore()
        novas_atas_encontradas = []

        for item in nos_detalhados:
            texto_no = item["texto"]
            elemento_no = item["elemento"]

            # Verifica se o nó faz menção a ata
            if "ata" not in texto_no.lower():
                continue

            # 1. Extrai ID numérico do documento no SEI (geralmente entre parênteses, ex: (140451633))
            match_doc_id = re.search(r"\((\d{6,12})\)", texto_no)
            doc_id = int(match_doc_id.group(1)) if match_doc_id else None

            # 2. Extrai número sequencial ou identificador da ata
            match_seq = re.search(r"ata(?:\s+de\s+reuni[ãa]o)?\s*(?:n[º°.]?\s*|-?\s*)(\d+)", texto_no, re.IGNORECASE)
            seq_num = int(match_seq.group(1)) if match_seq else None

            # Se não achou doc_id em parênteses, mas o número for grande (> 1.000.000), é o próprio doc_id
            if not doc_id and seq_num and seq_num > 1000000:
                doc_id = seq_num

            # 3. Determina se é nova em relação à maior ata da planilha
            eh_nova = False
            num_exibicao = seq_num or doc_id or 0

            if max_ata_conhecida > 1000000:
                # Planilha de origem usa ID de documento SEI (ex: 140451633)
                if doc_id and doc_id > max_ata_conhecida:
                    eh_nova = True
                    num_exibicao = doc_id
            elif max_ata_conhecida > 0:
                # Planilha de origem usa número sequencial (ex: 1, 2, 3)
                if seq_num and seq_num > max_ata_conhecida:
                    eh_nova = True
                    num_exibicao = seq_num
            else:
                # Sem ata prévia na planilha de origem: qualquer ata encontrada é nova
                eh_nova = True

            if eh_nova:
                # Extrai data da primeira assinatura e nome do secretário clicando no documento
                detalhes_ass = navigator.extrair_detalhes_assinatura_documento(
                    elemento_no=elemento_no,
                    nome_documento=texto_no
                )
                data_assinatura = detalhes_ass.get("data_assinatura", "")
                nome_secretario = detalhes_ass.get("secretario", "")

                novas_atas_encontradas.append({
                    "numero_ata": num_exibicao,
                    "doc_id": doc_id or "",
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
