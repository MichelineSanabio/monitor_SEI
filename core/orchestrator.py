"""
Orquestrador central do Monitor SEI.
Coordena a esteira de execução: Entrada -> Automação RPA -> Inspeção -> Exportação.
"""

from typing import Callable, Optional
import time
import random
from .base_monitor import BaseMonitor
from rpa_sei.driver_manager import DriverManager
from rpa_sei.sei_navigator import SeiNavigator
from exporters.excel_exporter import ExcelExporter
from selenium.common.exceptions import InvalidSessionIdException
from config.settings import PAUSA_ENTRE_PROCESSOS_MIN, PAUSA_ENTRE_PROCESSOS_MAX

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

            # --- DIAGNÓSTICO: Registra o estado da página após o login ---
            try:
                from config.settings import OUTPUTS_DIR
                from selenium.webdriver.common.by import By as _By
                import time as _t

                navigator.voltar_para_raiz()
                url_atual = driver.current_url
                titulo_pag = driver.title
                self.logger(f"[DIAG] URL após login: {url_atual}")
                self.logger(f"[DIAG] Título da página: {titulo_pag}")

                # Lista todos os iframes de 1º nível
                iframes = driver.find_elements(_By.TAG_NAME, "iframe")
                ids_iframes = [f.get_attribute("id") or f.get_attribute("name") or "(sem id)" for f in iframes]
                self.logger(f"[DIAG] Iframes encontrados ({len(iframes)}): {ids_iframes}")

                # Verifica elementos-chave do SEI
                tem_pesquisa = bool(driver.find_elements(_By.ID, "txtPesquisaRapida"))
                tem_unidade  = bool(driver.find_elements(_By.ID, "selInfraUnidades"))
                self.logger(f"[DIAG] txtPesquisaRapida visível: {tem_pesquisa} | selInfraUnidades visível: {tem_unidade}")
            except Exception as e_diag:
                self.logger(f"[DIAG] Erro no diagnóstico: {e_diag}")
            # --- FIM DO DIAGNÓSTICO ---

            # 3. Troca e Persistência de Unidade (RN01)
            self.logger(f"Alternando contexto no SEI para a unidade '{unidade}'...")
            navigator.trocar_unidade(unidade)


            # 4. Iteração nos Processos com Resiliência (RN06)
            idx = 0
            while idx < total:
                proc = processos[idx]
                idx += 1
                self.logger(f"[{idx}/{total}] Inspecionando processo: {proc}")

                try:
                    # Verifica se há link direto informado para o processo na planilha
                    link_proc = ""
                    if hasattr(monitor, "obter_link_processo"):
                        link_proc = monitor.obter_link_processo(proc)

                    # Abre o processo (por link ou campo de busca da janela) e trata eventual credencial (RN04)
                    abriu_com_sucesso = navigator.abrir_processo(
                        numero_processo=proc,
                        link=link_proc,
                        senha=senha,
                        usuario=usuario
                    )

                    if not abriu_com_sucesso:
                        self.logger(f"Aviso: Falha ao abrir o processo {proc} (não localizado ou restrito).")
                        resultados.append({
                            "processo": proc,
                            "status": "ERRO_ABERTURA",
                            "detalhe": "Não foi possível carregar a tela do processo"
                        })
                        time.sleep(1)
                        continue

                    # Executa a inspeção especializada definida pelo módulo
                    self.logger(f"Inspecionando documentos e atas do processo {proc}...")
                    dados_processo = monitor.inspecionar_processo(navigator, proc)
                    dados_processo["processo"] = proc
                    dados_processo["status"] = "SUCESSO"
                    novas = dados_processo.get("quantidade_novas_atas", 0)
                    self.logger(f"  → {novas} nova(s) ata(s) identificada(s) para o processo {proc}.")
                    resultados.append(dados_processo)

                except InvalidSessionIdException as e_sessao:
                    # O Edge fechou a conexão (crash, pop-up sigiloso que matou a sessão, etc.)
                    # Registra o processo atual como falha e tenta reiniciar o driver
                    self.logger(f"Sessão do navegador perdida ao processar {proc}: {e_sessao}")
                    resultados.append({
                        "processo": proc,
                        "status": "ERRO_SESSAO",
                        "detalhe": "Sessão do navegador encerrada inesperadamente"
                    })

                    # Encerra o driver corrompido
                    try:
                        driver_mgr.fechar()
                    except Exception:
                        pass

                    if idx >= total:
                        # Não há mais processos — encerra o loop
                        break

                    # Tenta reiniciar o driver e reautenticar para continuar os próximos processos
                    self.logger("Tentando reiniciar o navegador para continuar a execução...")
                    try:
                        driver_mgr = DriverManager(headless=headless)
                        driver = driver_mgr.iniciar_driver()
                        navigator = SeiNavigator(driver, logger=self.logger)

                        reautenticado = navigator.garantir_login_ativo(
                            timeout=90,
                            usuario=usuario,
                            senha=senha,
                            orgao=orgao
                        )
                        if not reautenticado:
                            self.logger("ERRO: Não foi possível reautenticar após reinicialização. Encerrando.")
                            break

                        navigator.trocar_unidade(unidade)
                        self.logger(f"Navegador reiniciado. Retomando a partir do processo {idx + 1}/{total}.")
                    except Exception as e_reinicio:
                        self.logger(f"Falha ao reiniciar o navegador: {e_reinicio}. Encerrando execução.")
                        break

                    continue

                except Exception as erro_processo:
                    self.logger(f"Erro ao inspecionar {proc}: {erro_processo}")
                    resultados.append({
                        "processo": proc,
                        "status": "ERRO_EXECUCAO",
                        "detalhe": str(erro_processo)
                    })
                    # Garante que volta para a raiz antes de tentar o próximo processo
                    try:
                        navigator.voltar_para_raiz()
                    except Exception:
                        pass

                # Pausa humana entre processos — evita que o SEI detecte cadência de bot
                pausa = random.uniform(PAUSA_ENTRE_PROCESSOS_MIN, PAUSA_ENTRE_PROCESSOS_MAX)
                self.logger(f"Aguardando {pausa:.1f}s antes do próximo processo...")
                time.sleep(pausa)

        finally:
            # 5. Fechamento seguro do WebDriver
            self.logger("Encerrando sessão do navegador...")
            try:
                driver_mgr.fechar()
            except Exception:
                pass

        # 6. Estruturação e Exportação (RN05)
        self.logger("Formatando dados para exportação...")
        linhas_formatadas = monitor.estruturar_linhas_exportacao(resultados)
        
        self.logger(f"Gravando arquivo {monitor.nome_identificador}.xlsx...")
        try:
            caminho_arquivo = ExcelExporter.exportar(
                nome_modulo=monitor.nome_identificador,
                linhas=linhas_formatadas
            )
            self.logger(f"Exportação concluída com sucesso em: {caminho_arquivo}")
            return caminho_arquivo
        except Exception as e_exp:
            self.logger(f"Aviso ao exportar relatório final: {e_exp}")
            return ""
