"""
Módulo de Autenticação e Desbloqueio de Processos Sigilosos no SEI (RN04).
Controla janelas pop-up, modais de credencial e prevenção contra bloqueio de conta.
"""

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
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
        Verifica se a janela/iframe atual possui o modal 'Identificação de Acesso' de processo sigiloso.
        """
        try:
            url_atual = self.driver.current_url.lower()
            titulo = self.driver.title.lower()

            # Indicadores diretos no título da janela
            if any(t in titulo for t in [
                "identificação de acesso",
                "identificacao de acesso",
                "sigiloso",
                "credencial",
                "acesso restrito",
            ]):
                return True

            # Indicadores na URL
            if any(t in url_atual for t in ["sigiloso", "credencial", "acessar_processo"]):
                return True

            # Checa presença explícita do container divIdentificacao
            if self.driver.find_elements(By.ID, "divIdentificacao"):
                return True

            # Heurística: tem campo de senha visível, NÃO tem combo de órgão (login inicial sempre tem)
            # e não é a página de login do SIP
            if "login.php" not in url_atual:
                candidatos = self.driver.find_elements(By.XPATH, SELETORES_SEI["campo_senha_sigiloso"])
                senhas_visiveis = [s for s in candidatos if s.is_displayed()]
                tem_combo_orgao = bool(self.driver.find_elements(By.ID, SELETORES_SEI["combo_orgao_login"]))
                if senhas_visiveis and not tem_combo_orgao:
                    return True
        except Exception:
            pass
        return False

    def _localizar_elementos_sigiloso(self):
        """
        Localiza o campo de senha visível (#pwdSenha / #txtSenha) e o botão de confirmação (#btnAcessar).
        Varre a janela principal, janelas pop-up e sub-iframes da página.
        Retorna (campo_senha, btn_confirmar) e deixa o driver posicionado no contexto onde os elementos foram encontrados.
        """
        driver = self.driver
        janela_principal = driver.current_window_handle

        def _buscar_no_contexto_atual():
            botoes_cand = driver.find_elements(By.XPATH, SELETORES_SEI["btn_confirmar_sigiloso"])
            botoes_visiveis = [b for b in botoes_cand if b.is_displayed()]

            # Seletores para o campo de senha (prioriza IDs exatos e descarta style display:none)
            candidatos_senha = driver.find_elements(By.ID, "pwdSenha")
            if not candidatos_senha:
                candidatos_senha = driver.find_elements(By.ID, "txtSenha")
            if not candidatos_senha:
                candidatos_senha = driver.find_elements(By.XPATH, SELETORES_SEI["campo_senha_sigiloso"])

            senhas_visiveis = [s for s in candidatos_senha if s.is_displayed()]
            if senhas_visiveis:
                btn = botoes_visiveis[0] if botoes_visiveis else None
                return senhas_visiveis[0], btn
            return None, None

        def _buscar_recursivo_iframes(profundidade=0, profundidade_max=3):
            campo, btn = _buscar_no_contexto_atual()
            if campo:
                return campo, btn
            if profundidade >= profundidade_max:
                return None, None

            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            for iframe in iframes:
                try:
                    driver.switch_to.frame(iframe)
                    c, b = _buscar_recursivo_iframes(profundidade + 1, profundidade_max)
                    if c:
                        return c, b
                    driver.switch_to.parent_frame()
                except Exception:
                    try:
                        driver.switch_to.parent_frame()
                    except Exception:
                        driver.switch_to.default_content()
            return None, None

        # A) Verifica janelas pop-up (se houver mais de uma janela aberta)
        if len(driver.window_handles) > 1:
            for handle in driver.window_handles:
                if handle != janela_principal:
                    try:
                        driver.switch_to.window(handle)
                        c, b = _buscar_recursivo_iframes()
                        if c:
                            return c, b
                    except Exception:
                        pass
            try:
                driver.switch_to.window(janela_principal)
            except Exception:
                pass

        # B) Verifica na janela principal (raiz e sub-iframes)
        try:
            driver.switch_to.window(janela_principal)
            driver.switch_to.default_content()
        except Exception:
            pass

        c, b = _buscar_recursivo_iframes()
        if c:
            return c, b

        return None, None

    def tratar_processo_sigiloso(self, senha: str, usuario: str = "") -> bool:
        """
        Detecta se houve solicitação de credencial para processo sigiloso
        (em janela pop-up, modal #divIdentificacao ou iframe sobreposto).
        Preenche a senha se fornecida e valida o desbloqueio.
        """
        driver = self.driver
        janela_principal = driver.current_window_handle
        janela_pop_up = None

        if len(driver.window_handles) > 1:
            for handle in driver.window_handles:
                if handle != janela_principal:
                    janela_pop_up = handle
                    break

        # Localiza o campo de senha visível e o botão correspondente
        campo_senha, btn_confirmar = self._localizar_elementos_sigiloso()

        if not campo_senha:
            # Não localizou modal de sigilo — processo é público ou já desbloqueado
            try:
                driver.switch_to.window(janela_principal)
            except Exception:
                pass
            return True

        self.logger("Identificado modal de identificação de processo sigiloso (#divIdentificacao). Solicitando credencial...")
        self.logger(f"  → Usuário: '{usuario or '(pré-preenchido pelo SEI)'}'")
        self.logger(f"  → Senha: {'informada (preenchendo...)' if senha else 'NÃO informada'}")

        if not senha:
            self.logger("Aviso: Nenhuma senha foi informada para desbloquear processo sigiloso.")
            return False

        if self.falhas_consecutivas >= self.LIMITE_FALHAS:
            self.logger("ALERTA DE SEGURANÇA: Limite de falhas de autenticação atingido. Interrompendo para evitar bloqueio.")
            raise PermissionError("Autenticação interrompida por segurança (prevenção de bloqueio de conta).")

        try:
            # 1. Limpa e foca no campo visível (#pwdSenha)
            try:
                campo_senha.click()
            except Exception:
                driver.execute_script("arguments[0].focus();", campo_senha)

            try:
                campo_senha.clear()
            except Exception:
                pass

            campo_senha.send_keys(Keys.CONTROL + "a")
            campo_senha.send_keys(Keys.BACKSPACE)

            # 2. Digita a senha no elemento visível
            campo_senha.send_keys(senha)

            # Fallback via JS: atualiza value e despacha eventos de input/change/keyup
            driver.execute_script("""
                var el = arguments[0];
                var val = arguments[1];
                if (el.value !== val) {
                    el.value = val;
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    el.dispatchEvent(new Event('keyup', { bubbles: true }));
                }
            """, campo_senha, senha)

            # Sincroniza também qualquer <input type="password"> oculto se existente no formulário
            try:
                inputs_ocultos = driver.find_elements(By.XPATH, "//input[@type='password']")
                for pwd_oculto in inputs_ocultos:
                    driver.execute_script("arguments[0].value = arguments[1];", pwd_oculto, senha)
            except Exception:
                pass

            self.logger("Senha preenchida no modal de identificação de processo sigiloso.")

            # 3. Clica no botão de confirmação (#btnAcessar / #sbmAcessar)
            sucesso_clique = False
            if btn_confirmar:
                try:
                    btn_confirmar.click()
                    sucesso_clique = True
                except Exception:
                    try:
                        driver.execute_script("arguments[0].click();", btn_confirmar)
                        sucesso_clique = True
                    except Exception:
                        pass

            if not sucesso_clique:
                try:
                    driver.execute_script("if (typeof acessar === 'function') { acessar(); }")
                    sucesso_clique = True
                except Exception:
                    campo_senha.send_keys(Keys.RETURN)

            time.sleep(2)

            # 4. Valida erros de autenticação
            erros = driver.find_elements(
                By.XPATH,
                "//*[contains(text(), 'Senha inválida') or contains(text(), 'Credencial incorreta') or contains(text(), 'Acesso negado') or contains(text(), 'Usuário ou senha inválidos')]"
            )
            erros_visiveis = [e for e in erros if e.is_displayed() and e.text.strip()]
            if erros_visiveis:
                self.falhas_consecutivas += 1
                self.logger(f"Falha de autenticação: Senha incorreta ({self.falhas_consecutivas}/{self.LIMITE_FALHAS}).")
                return False

            self.falhas_consecutivas = 0
            self.logger("Credencial de sigilo confirmada com sucesso.")

            # 4.5. Aguarda a submissão do formulário e o redirecionamento do SEI (desaparecimento de #divIdentificacao)
            time.sleep(1.5)
            for _ in range(12):
                try:
                    candidatos = driver.find_elements(By.ID, "divIdentificacao")
                    if not candidatos or not any(c.is_displayed() for c in candidatos):
                        break
                except Exception:
                    break
                time.sleep(0.5)

            time.sleep(1.0)

            # 5. Garante foco na janela do processo e volta para a raiz (default_content)
            try:
                if driver.window_handles:
                    driver.switch_to.window(driver.window_handles[-1])
                    driver.switch_to.default_content()
            except Exception:
                pass

        except PermissionError:
            raise
        except Exception as e:
            self.logger(f"Aviso durante desbloqueio de processo sigiloso: {e}")
            try:
                if driver.window_handles:
                    driver.switch_to.window(driver.window_handles[-1])
                    driver.switch_to.default_content()
            except Exception:
                pass

        return True
