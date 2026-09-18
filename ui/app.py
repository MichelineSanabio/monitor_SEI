"""
Interface Gráfica com o Usuário (UI) para o Monitor SEI.
Desenvolvida em CustomTkinter, com suporte a temas modernos e multithreading para não congelar a janela.
"""

import customtkinter as ctk
import threading
import time
from tkinter import filedialog
from pathlib import Path
from typing import List
from config.settings import UNIDADES_PADRAO, INPUTS_DIR
from core.base_monitor import BaseMonitor
from core.orchestrator import Orchestrator

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class AppMonitorSEI(ctk.CTk):
    """
    Janela Principal da aplicação desktop Monitor SEI.
    """

    def __init__(self, unidades: List[str], monitores: List[BaseMonitor]):
        super().__init__()

        self.unidades = unidades
        self.monitores = {m.descricao: m for m in monitores}
        self.caminho_arquivo_selecionado = ""

        # Configurações da Janela
        self.title("Monitor SEI - Painel de Automação e Controle")
        self.geometry("580x780")
        self.minsize(540, 740)

        self._construir_interface()

    def _construir_interface(self):
        # 1. Cabeçalho
        self.lbl_titulo = ctk.CTkLabel(
            self, 
            text="Automação & Monitoramento SEI", 
            font=ctk.CTkFont(size=22, weight="bold")
        )
        self.lbl_titulo.pack(pady=(20, 5))

        self.lbl_subtitulo = ctk.CTkLabel(
            self, 
            text="Acompanhamento automatizado de processos em lote", 
            font=ctk.CTkFont(size=12)
        )
        self.lbl_subtitulo.pack(pady=(0, 15))

        # Container Principal com margens
        self.frame_conteudo = ctk.CTkFrame(self)
        self.frame_conteudo.pack(padx=30, pady=5, fill="both", expand=True)

        # 2. Seletor de Unidade (RN01)
        self.lbl_unidade = ctk.CTkLabel(
            self.frame_conteudo, 
            text="1. Selecione a Unidade de Lotação:", 
            font=ctk.CTkFont(weight="bold")
        )
        self.lbl_unidade.pack(anchor="w", padx=20, pady=(15, 2))
        
        self.combo_unidade = ctk.CTkComboBox(
            self.frame_conteudo, 
            values=self.unidades,
            width=480
        )
        if "CINQA" in self.unidades:
            self.combo_unidade.set("CINQA")
        self.combo_unidade.pack(padx=20, pady=(2, 10))

        # 3. Seletor Dinâmico de Módulo (RN02)
        self.lbl_modulo = ctk.CTkLabel(
            self.frame_conteudo, 
            text="2. Tipo de Monitoramento:", 
            font=ctk.CTkFont(weight="bold")
        )
        self.lbl_modulo.pack(anchor="w", padx=20, pady=(5, 2))

        opcoes_monitores = list(self.monitores.keys())
        self.combo_modulo = ctk.CTkComboBox(
            self.frame_conteudo, 
            values=opcoes_monitores,
            width=480
        )
        if "Monitoramento atas feitas" in opcoes_monitores:
            self.combo_modulo.set("Monitoramento atas feitas")
        self.combo_modulo.pack(padx=20, pady=(2, 10))

        # 4. Seleção da Planilha de Processos (RN03)
        self.lbl_arquivo = ctk.CTkLabel(
            self.frame_conteudo, 
            text="3. Planilha de Origem dos Processos (opcional):", 
            font=ctk.CTkFont(weight="bold")
        )
        self.lbl_arquivo.pack(anchor="w", padx=20, pady=(5, 2))

        self.frame_arquivo = ctk.CTkFrame(self.frame_conteudo, fg_color="transparent")
        self.frame_arquivo.pack(padx=20, pady=(2, 10), fill="x")

        self.txt_arquivo = ctk.CTkEntry(
            self.frame_arquivo, 
            placeholder_text="Padrão: data/inputs/origem_atas.xlsx",
            width=360
        )
        self.txt_arquivo.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.btn_procurar = ctk.CTkButton(
            self.frame_arquivo, 
            text="Procurar...", 
            width=100,
            command=self._selecionar_arquivo
        )
        self.btn_procurar.pack(side="right")

        # 5. Credenciais de Acesso ao SEI-RJ (Usuário, Senha e Órgão UERJ)
        self.lbl_credenciais = ctk.CTkLabel(
            self.frame_conteudo, 
            text="4. Credenciais de Acesso ao SEI-RJ:", 
            font=ctk.CTkFont(weight="bold")
        )
        self.lbl_credenciais.pack(anchor="w", padx=20, pady=(6, 2))

        # Linha com Usuário e Senha lado a lado
        self.frame_login = ctk.CTkFrame(self.frame_conteudo, fg_color="transparent")
        self.frame_login.pack(padx=20, pady=(2, 4), fill="x")

        # Campo 1: Usuário
        self.lbl_user = ctk.CTkLabel(self.frame_login, text="Usuário:", font=ctk.CTkFont(size=12))
        self.lbl_user.grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.txt_usuario = ctk.CTkEntry(
            self.frame_login, 
            placeholder_text="Usuário (ex: nome.sobrenome)",
            width=230
        )
        self.txt_usuario.grid(row=1, column=0, sticky="ew", padx=(0, 10))

        # Campo 2: Senha
        self.lbl_pwd = ctk.CTkLabel(self.frame_login, text="Senha:", font=ctk.CTkFont(size=12))
        self.lbl_pwd.grid(row=0, column=1, sticky="w")
        self.txt_senha = ctk.CTkEntry(
            self.frame_login, 
            placeholder_text="Senha de acesso", 
            show="*", 
            width=230
        )
        self.txt_senha.grid(row=1, column=1, sticky="ew")
        self.frame_login.grid_columnconfigure(0, weight=1)
        self.frame_login.grid_columnconfigure(1, weight=1)

        # Campo 3: Órgão (Sempre UERJ)
        self.frame_orgao = ctk.CTkFrame(self.frame_conteudo, fg_color="transparent")
        self.frame_orgao.pack(padx=20, pady=(4, 10), fill="x")

        self.lbl_orgao = ctk.CTkLabel(self.frame_orgao, text="Órgão:", font=ctk.CTkFont(size=12))
        self.lbl_orgao.pack(side="left", padx=(0, 10))
        
        self.combo_orgao = ctk.CTkComboBox(
            self.frame_orgao, 
            values=["UERJ"],
            width=160,
            state="readonly"
        )
        self.combo_orgao.set("UERJ")
        self.combo_orgao.pack(side="left")

        self.lbl_orgao_info = ctk.CTkLabel(
            self.frame_orgao, 
            text="(preenchido automaticamente com UERJ)", 
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.lbl_orgao_info.pack(side="left", padx=(10, 0))

        # Checkbox Navegador Visível ou Headless
        self.chk_headless = ctk.CTkCheckBox(
            self.frame_conteudo, 
            text="Executar navegador em segundo plano (Modo Invisível / Headless)"
        )
        self.chk_headless.pack(anchor="w", padx=20, pady=(2, 12))

        # 6. Botão de Iniciar
        self.btn_iniciar = ctk.CTkButton(
            self.frame_conteudo, 
            text="Iniciar Monitoramento", 
            command=self._disparar_execucao, 
            height=42, 
            width=480, 
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.btn_iniciar.pack(padx=20, pady=(5, 15))

        # 7. Console de Log em Tempo Real
        self.lbl_logs = ctk.CTkLabel(
            self.frame_conteudo, 
            text="Logs de Execução:", 
            font=ctk.CTkFont(weight="bold")
        )
        self.lbl_logs.pack(anchor="w", padx=20, pady=(5, 2))

        self.caixa_logs = ctk.CTkTextbox(self.frame_conteudo, width=480, height=140)
        self.caixa_logs.pack(padx=20, pady=(2, 15), fill="both", expand=True)

    def log(self, mensagem: str):
        """Atualiza a caixa de log de forma thread-safe."""
        horario = time.strftime("%H:%M:%S")
        self.after(0, self._inserir_texto_log, f"[{horario}] {mensagem}\n")

    def _inserir_texto_log(self, texto: str):
        self.caixa_logs.insert("end", texto)
        self.caixa_logs.see("end")

    def _selecionar_arquivo(self):
        caminho = filedialog.askopenfilename(
            title="Selecione a Planilha de Processos",
            filetypes=[("Planilhas Excel ou CSV", "*.xlsx *.xls *.csv"), ("Todos os Arquivos", "*.*")]
        )
        if caminho:
            self.caminho_arquivo_selecionado = caminho
            self.txt_arquivo.delete(0, "end")
            self.txt_arquivo.insert(0, caminho)

    def _disparar_execucao(self):
        """Inicia o Orchestrator em uma thread secundária isolada."""
        self.btn_iniciar.configure(state="disabled", text="Executando Automação...")
        thread = threading.Thread(target=self._rotina_automacao_thread, daemon=True)
        thread.start()

    def _rotina_automacao_thread(self):
        try:
            unidade = self.combo_unidade.get()
            desc_modulo = self.combo_modulo.get()
            monitor = self.monitores.get(desc_modulo)
            usuario = self.txt_usuario.get().strip()
            senha = self.txt_senha.get().strip()
            orgao = self.combo_orgao.get().strip() or "UERJ"
            headless = bool(self.chk_headless.get())

            caminho_planilha = self.txt_arquivo.get().strip()

            if not monitor:
                self.log("Erro: Nenhum monitor selecionado.")
                return

            orquestrador = Orchestrator(callback_log=self.log)
            
            # Se o usuário indicou uma planilha específica, repassa no carregamento
            if caminho_planilha:
                monitor.caminho_arquivo_customizado = caminho_planilha

            arquivo_gerado = orquestrador.executar(
                unidade=unidade,
                monitor=monitor,
                usuario=usuario,
                senha=senha,
                orgao=orgao,
                headless=headless
            )

            if arquivo_gerado:
                self.log(">>> ROTINA CONCLUÍDA COM SUCESSO! <<<")
                self.log(f">>> Arquivo gerado em: {arquivo_gerado}")

        except Exception as e:
            self.log(f"ERRO FATAL NA EXECUÇÃO: {e}")

        finally:
            self.after(0, lambda: self.btn_iniciar.configure(state="normal", text="Iniciar Monitoramento"))
