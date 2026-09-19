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

# Timeout maior para aguardar o modal do processo sigiloso (pode demorar para renderizar)
SIGILOSO_TIMEOUT = 6


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

            # 5. Aguarda resposta e verifica se houve mensagem de erro de autenticação
            time.sleep(2)

            # O SEI-RJ possui uma div estática #divInfraNavegadorAviso com 'alert alert-danger' que NÃO é erro de login.
            # Filtramos especificamente mensagens reais de erro de autenticação:
            erros = driver.find_elements(
                By.XPATH, 
                "//*[(contains(text(), 'Usuário ou senha inválidos') or contains(text(), 'Dados inválidos') or contains(text(), 'Senha inválida') or contains(text(), 'Órgão inválido')) and not(@id='divInfraNavegadorAviso') and not(ancestor-or-self::*[@id='divInfraNavegadorAviso'])]"
            )
            for err in erros:
                if err.is_displayed() and err.text.strip():
                    msg_erro = err.text.strip()
                    self.falhas_consecutivas += 1
                    self.logger(f"Falha no login SEI-RJ: {msg_erro}")
                    if self.falhas_consecutivas >= self.LIMITE_FALHAS:
                        raise PermissionError(f"Bloqueio preventivo: {msg_erro}")
                    return False

            # Verifica se já saiu da tela de login (txtUsuario sumiu ou URL mudou)
            if "login.php" not in driver.current_url.lower() or not driver.find_elements(By.ID, SELETORES_SEI["campo_usuario_login"]):
                self.logger("Login no SEI-RJ realizado com sucesso!")
                self.falhas_consecutivas = 0
                return True

            return True

        except PermissionError:
            raise
        except Exception as e:
            self.logger(f"Aviso durante tentativa de login inicial: {e}")
            return False

    def _janela_e_de_sigiloso(self) -> bool:
        """
        Verifica se a janela/aba atual corresponde à tela de credencial de processo sigiloso.
        Distingue do login inicial verificando a URL e o título da página.
        """
        try:
            url_atual = self.driver.current_url.lower()
            titulo = self.driver.title.lower()
            # A tela de credencial do sigiloso é uma página separada do login inicial.
            # Indicadores: URL não é login.php, ou contém 'sigiloso', 'acessar_processo', 'credencial'
            if "sigiloso" in url_atual or "credencial" in url_atual or "acessar_processo" in url_atual:
                return True
            # Se o título da janela mencionar sigilo
            if "sigiloso" in titulo or "credencial" in titulo or "acesso restrito" in titulo:
                return True
            # Se não é a tela de login principal e tem campo de senha e NÃO tem selOrgao
            # (login principal sempre tem o combo de órgão)
            tem_campo_senha = bool(self.driver.find_elements(By.XPATH, "//input[@type='password']"))
            tem_combo_orgao = bool(self.driver.find_elements(By.ID, SELETORES_SEI["combo_orgao_login"]))
            if tem_campo_senha and not tem_combo_orgao and "login.php" not in url_atual:
                return True
        except Exception:
            pass
        return False

    def tratar_processo_sigiloso(self, senha: str, usuario: str = "") -> bool:
        """
        Detecta se houve solicitação de credencial para processo sigiloso
        (em nova janela pop-up ou modal sobreposto na página atual).
        Preenche a senha se fornecida e valida o desbloqueio.

        Distingue corretamente a tela de credencial sigilosa do login inicial do SEI
        verificando a URL, o título da janela e a ausência do combo de órgão.
        """
        driver = self.driver
        janela_principal = driver.current_window_handle
        janela_sigiloso = None

        # 1. Verifica se abriu uma nova janela pop-up para credencial do sigiloso
        if len(driver.window_handles) > 1:
            for handle in driver.window_handles:
                if handle != janela_principal:
                    driver.switch_to.window(handle)
                    time.sleep(1)  # Aguarda a janela pop-up renderizar
                    if self._janela_e_de_sigiloso():
                        janela_sigiloso = handle
                        break
                    else:
                        # Não é uma janela de sigiloso — retorna para a principal
                        driver.switch_to.window(janela_principal)

        # 2. Se não achou em janela separada, verifica se é modal na janela atual
        if not janela_sigiloso:
            driver.switch_to.window(janela_principal)
            if not self._janela_e_de_sigiloso():
                # Não há tela de credencial do sigiloso — processo é público ou já desbloqueado
                return True

        # 3. Busca o campo de senha com timeout configurável
        try:
            campo_senha = WebDriverWait(driver, SIGILOSO_TIMEOUT).until(
                EC.presence_of_element_located((By.XPATH, SELETORES_SEI["campo_senha_sigiloso"]))
            )

            self.logger("Identificado processo com restrição de sigilo. Solicitando credencial...")

            if not senha:
                self.logger("Aviso: Nenhuma senha foi informada para desbloquear processo sigiloso.")
                # Fecha a janela pop-up e retorna para a principal
                if janela_sigiloso:
                    try:
                        driver.close()
                    except Exception:
                        pass
                    driver.switch_to.window(janela_principal)
                return False

            if self.falhas_consecutivas >= self.LIMITE_FALHAS:
                self.logger("ALERTA DE SEGURANÇA: Limite de falhas de autenticação atingido. Interrompendo para evitar bloqueio.")
                if janela_sigiloso:
                    try:
                        driver.close()
                    except Exception:
                        pass
                    driver.switch_to.window(janela_principal)
                raise PermissionError("Autenticação interrompida por segurança (prevenção de bloqueio de conta).")

            # 4. Preenche o campo de usuário se solicitado pelo modal
            campos_user = driver.find_elements(By.XPATH, SELETORES_SEI["campo_usuario_sigiloso"])
            if campos_user and campos_user[0].is_displayed() and usuario:
                campos_user[0].clear()
                campos_user[0].send_keys(usuario)

            # 5. Preenche a senha
            campo_senha.clear()
            campo_senha.send_keys(senha)

            # 6. Clica no botão de confirmação/liberação
            btn_confirmar = driver.find_element(By.XPATH, SELETORES_SEI["btn_confirmar_sigiloso"])
            btn_confirmar.click()
            time.sleep(2)

            # 7. Valida se ainda há campo de erro ou se a senha foi aceita
            erros = driver.find_elements(
                By.XPATH,
                "//*[contains(text(), 'Senha inválida') or contains(text(), 'Credencial incorreta') or contains(text(), 'Acesso negado')]"
            )
            erros_visiveis = [e for e in erros if e.is_displayed() and e.text.strip()]
            if erros_visiveis:
                self.falhas_consecutivas += 1
                self.logger(f"Falha de autenticação: Senha incorreta ({self.falhas_consecutivas}/{self.LIMITE_FALHAS}).")
                if janela_sigiloso:
                    try:
                        driver.close()
                    except Exception:
                        pass
                    driver.switch_to.window(janela_principal)
                return False

            self.falhas_consecutivas = 0
            self.logger("Credencial de sigilo confirmada com sucesso.")

            # 8. Se era janela pop-up, aguarda redirecionamento ou fecha a janela
            if janela_sigiloso:
                # Aguarda a janela pop-up fechar (o SEI pode fechá-la automaticamente após login)
                for _ in range(10):
                    time.sleep(0.5)
                    handles_atuais = driver.window_handles
                    if janela_sigiloso not in handles_atuais:
                        break  # A janela foi fechada automaticamente pelo SEI
                else:
                    # Se ainda aberta, fecha manualmente e retorna à principal
                    try:
                        if janela_sigiloso in driver.window_handles:
                            driver.close()
                    except Exception:
                        pass

                # Garante retorno para a janela principal
                try:
                    driver.switch_to.window(janela_principal)
                except Exception:
                    # Se a janela principal também mudou, vai para a última disponível
                    if driver.window_handles:
                        driver.switch_to.window(driver.window_handles[-1])

        except PermissionError:
            raise
        except Exception:
            # Não solicitou senha (processo já liberado na sessão ou processo público)
            # Garante retorno para a janela principal em qualquer caso
            try:
                if janela_sigiloso and janela_sigiloso in driver.window_handles:
                    driver.switch_to.window(janela_sigiloso)
                    driver.close()
            except Exception:
                pass
            try:
                driver.switch_to.window(janela_principal)
            except Exception:
                if driver.window_handles:
                    driver.switch_to.window(driver.window_handles[-1])

        return True
