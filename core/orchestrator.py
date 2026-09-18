"""
Orquestrador central do Monitor SEI.
Coordena a esteira de execução: Entrada -> Automação RPA -> Inspeção -> Exportação.
"""

from typing import Callable, Optional
import time
from .base_monitor import BaseMonitor
from rpa_sei.driver_manager import DriverManager
from rpa_sei.sei_navigator import SeiNavigator
from exporters.excel_exporter import ExcelExporter

class Orchestrator:
    """
    Gerenciador do ciclo de vida de uma execução do Monitor SEI.
    Garante resiliência a falhas pontuais (RN06) e notificação contínua via logs.
    """

    def __init__(self, callback_log: Optional[Callable[[str], None]] = None):
        self.logger = callback_log or (lambda msg: print(f"[LOG] {msg}"))

    def executar(
        self,
        unidade: str,
        monitor: BaseMonitor,
        usuario: str = "",
        senha: str = "",
        orgao: str = "UERJ",
        headless: bool = False
    ) -> str:
        """
        Executa o fluxo completo do monitoramento.
        Retorna o caminho do arquivo de saída gerado.
        """
        self.logger(f"Iniciando esteira para módulo: {monitor.descricao}")
        self.logger(f"Unidade de lotação selecionada: {unidade}")

        # 1. Carregamento de Processos Alvos
        self.logger("Carregando lista de processos alvos...")
        processos = monitor.carregar_alvos({"unidade": unidade})
        
        if not processos:
            self.logger("Nenhum processo encontrado para monitorar. Finalizando rotina.")
            return ""

        total = len(processos)
        self.logger(f"{total} processo(s) localizado(s) para inspeção.")

        # 2. Inicialização do Navegador e RPA
        self.logger("Iniciando navegador web (Microsoft Edge / Selenium)...")
        driver_mgr = DriverManager(headless=headless)
        driver = driver_mgr.iniciar_driver()
        navigator = SeiNavigator(driver, logger=self.logger)

        resultados = []

        try:
            # 2.1 Garante que a sessão está autenticada no SEI (automático ou manual via Gov.br / 2FA)
            self.logger("Verificando autenticação no SEI...")
            autenticado = navigator.garantir_login_ativo(
                timeout=90,
                usuario=usuario,
                senha=senha,
                orgao=orgao
            )
            if not autenticado:
                self.logger("ERRO: Autenticação no SEI não foi confirmada dentro do prazo. Monitoramento cancelado.")
                return ""

            # 3. Troca e Persistência de Unidade (RN01)
            self.logger(f"Alternando contexto no SEI para a unidade '{unidade}'...")
            navigator.trocar_unidade(unidade)

            # 4. Iteração nos Processos com Resiliência (RN06)
            for idx, proc in enumerate(processos, start=1):
                self.logger(f"[{idx}/{total}] Inspecionando processo: {proc}")
                
                try:
                    # Abre o processo e trata eventual credencial de sigiloso (RN04)
                    abriu_com_sucesso = navigator.abrir_processo(proc, senha=senha, usuario=usuario)
                    
                    if not abriu_com_sucesso:
                        self.logger(f"Aviso: Falha ao abrir o processo {proc} (não localizado ou restrito).")
                        resultados.append({
                            "processo": proc,
                            "status": "ERRO_ABERTURA",
                            "detalhe": "Não foi possível carregar a tela do processo"
                        })
                        continue

                    # Executa a inspeção especializada definida pelo módulo
                    dados_processo = monitor.inspecionar_processo(navigator, proc)
                    dados_processo["processo"] = proc
                    dados_processo["status"] = "SUCESSO"
                    resultados.append(dados_processo)

                except Exception as erro_processo:
                    self.logger(f"Erro ao inspecionar {proc}: {erro_processo}")
                    resultados.append({
                        "processo": proc,
                        "status": "ERRO_EXECUCAO",
                        "detalhe": str(erro_processo)
                    })
                    # Garante que volta para a raiz antes de tentar o próximo processo
                    navigator.voltar_para_raiz()

                time.sleep(1)

        finally:
            # 5. Fechamento seguro do WebDriver
            self.logger("Encerrando sessão do navegador...")
            driver_mgr.fechar()

        # 6. Estruturação e Exportação (RN05)
        self.logger("Formatando dados para exportação...")
        linhas_formatadas = monitor.estruturar_linhas_exportacao(resultados)
        
        self.logger(f"Gravando arquivo {monitor.nome_identificador}.xlsx...")
        caminho_arquivo = ExcelExporter.exportar(
            nome_modulo=monitor.nome_identificador,
            linhas=linhas_formatadas
        )

        self.logger(f"Exportação concluída com sucesso em: {caminho_arquivo}")
        return caminho_arquivo
