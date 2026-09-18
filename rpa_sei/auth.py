"""
Módulo de Autenticação e Desbloqueio de Processos Sigilosos no SEI (RN04).
Controla janelas pop-up, modais de credencial e prevenção contra bloqueio de conta.
"""

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from typing import Callable, Optional
from config.settings import SELETORES_SEI, SHORT_TIMEOUT

class AuthHandler:
    """
    Trata telas de login inicial do SEI-RJ (SIP) e solicitação de credenciais de processos sigilosos.
    """

    def __init__(self, driver, logger: Optional[Callable[[str], None]] = None):
        self.driver = driver
        self.logger = logger or (lambda msg: None)
        self.falhas_consecutivas = 0
        self.LIMITE_FALHAS = 2  # Evita bloqueio da conta do usuário no SEI

    def realizar_login_inicial(self, usuario: str, senha: str, orgao: str = "UERJ") -> bool:
        """
        Detecta se a tela de login do SEI-RJ (SIP) está aberta e preenche:
        - Usuário (txtUsuario)
        - Senha (pwdSenha)
        - Órgão (selOrgao = UERJ)
        Em seguida, clica em ACESSAR (sbmAcessar).
        """
        from selenium.webdriver.support.ui import Select
        driver = self.driver

        try:
            # Verifica se o campo de usuário da tela de login inicial está presente
            campo_user_elem = driver.find_elements(By.ID, SELETORES_SEI["campo_usuario_login"])
            if not campo_user_elem or not campo_user_elem[0].is_displayed():
                # Se não estiver na tela de login, o usuário já pode estar autenticado pela sessão
                return True

            self.logger(f"Tela de login do SEI-RJ identificada. Preenchendo credenciais para órgão '{orgao}'...")

            if not usuario or not senha:
                self.logger("Aviso: Usuário ou senha não informados na interface. Preencha na janela do navegador se necessário.")
                return False

            # 1. Preenche Usuário
            campo_user = campo_user_elem[0]
            campo_user.clear()
            campo_user.send_keys(usuario)

            # 2. Preenche Senha
            campo_pwd = driver.find_element(By.ID, SELETORES_SEI["campo_senha_login"])
            campo_pwd.clear()
            campo_pwd.send_keys(senha)

            # 3. Seleciona o Órgão (padrão UERJ)
            select_orgao_elem = driver.find_element(By.ID, SELETORES_SEI["combo_orgao_login"])
            select_orgao = Select(select_orgao_elem)
            
            # Tenta selecionar por texto visível 'UERJ' ou valor '40'
            try:
                select_orgao.select_by_visible_text(orgao)
            except Exception:
                try:
                    select_orgao.select_by_value("40")
                except Exception:
                    pass

            # 4. Clica em ACESSAR
            btn_acessar = driver.find_element(By.ID, SELETORES_SEI["btn_acessar_login"])
            btn_acessar.click()
            time.sleep(2)

            # 5. Verifica se houve mensagem de erro de autenticação
            erros = driver.find_elements(
                By.XPATH, 
                "//*[contains(text(), 'Usuário ou senha inválidos') or contains(text(), 'Dados inválidos') or contains(@class, 'alert-danger')]"
            )
            for err in erros:
                if err.is_displayed() and err.text.strip():
                    self.falhas_consecutivas += 1
                    msg_erro = err.text.strip()
                    self.logger(f"Falha no login SEI-RJ: {msg_erro}")
                    if self.falhas_consecutivas >= self.LIMITE_FALHAS:
                        raise PermissionError(f"Bloqueio preventivo: {msg_erro}")
                    return False

            self.logger("Login no SEI-RJ realizado com sucesso!")
            self.falhas_consecutivas = 0
            return True

        except PermissionError:
            raise
        except Exception as e:
            self.logger(f"Aviso durante tentativa de login inicial: {e}")
            return False

    def tratar_processo_sigiloso(self, senha: str, usuario: str = "") -> bool:
        """
        Detecta se houve solicitação de credencial (em nova janela ou modal sobreposto).
        Preenche a senha se fornecida e valida o desbloqueio.
        """
        driver = self.driver
        janela_principal = driver.current_window_handle

        # 1. Caso abra em janela pop-up separada (window.open)
        if len(driver.window_handles) > 1:
            for handle in driver.window_handles:
                if handle != janela_principal:
                    driver.switch_to.window(handle)
                    break

        # 2. Busca o campo de senha com timeout curto (para não atrasar processos públicos)
        try:
            campo_senha = WebDriverWait(driver, SHORT_TIMEOUT).until(
                EC.presence_of_element_located((By.XPATH, SELETORES_SEI["campo_senha_sigiloso"]))
            )

            self.logger("Identificado processo com restrição de sigilo. Solicitando credencial...")

            if not senha:
                self.logger("Aviso: Nenhuma senha foi informada para desbloquear processo sigiloso.")
                return False

            if self.falhas_consecutivas >= self.LIMITE_FALHAS:
                self.logger("ALERTA DE SEGURANÇA: Limite de falhas de autenticação atingido. Interrompendo para evitar bloqueio.")
                raise PermissionError("Autenticação interrompida por segurança (prevenção de bloqueio de conta).")

            # Preenche login se solicitado pelo modal
            campos_user = driver.find_elements(By.XPATH, SELETORES_SEI["campo_usuario_sigiloso"])
            if campos_user and campos_user[0].is_displayed() and usuario:
                campos_user[0].clear()
                campos_user[0].send_keys(usuario)

            # Preenche a senha
            campo_senha.clear()
            campo_senha.send_keys(senha)

            # Clica no botão de confirmação/liberação
            btn_confirmar = driver.find_element(By.XPATH, SELETORES_SEI["btn_confirmar_sigiloso"])
            btn_confirmar.click()
            time.sleep(1.5)

            # Valida se ainda há campo de erro ou se a senha foi aceita
            erros = driver.find_elements(By.XPATH, "//*[contains(text(), 'Senha inválida') or contains(text(), 'Credencial incorreta')]")
            if erros:
                self.falhas_consecutivas += 1
                self.logger(f"Falha de autenticação: Senha incorreta ({self.falhas_consecutivas}/{self.LIMITE_FALHAS}).")
                return False

            self.falhas_consecutivas = 0
            self.logger("Credencial de sigilo confirmada com sucesso.")

        except PermissionError:
            raise
        except Exception:
            # Não solicitou senha (processo já liberado na sessão ou processo público)
            pass

        # 3. Retorna foco para a janela de trabalho
        if len(driver.window_handles) == 1:
            driver.switch_to.window(janela_principal)

        return True
