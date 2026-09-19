"""
Navegador de Ações do SEI.
Isola a interação com elementos do DOM e o gerenciamento de iframes (ifrVisualizacao, ifrArvore, ifrConteudoVisualizacao).
"""

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    WebDriverException,
    InvalidSessionIdException,
    NoSuchWindowException,
    UnexpectedAlertPresentException,
)
import time
import re
import random
from typing import Callable, List, Optional
from config.settings import (
    SELETORES_SEI, 
    DEFAULT_TIMEOUT, 
    SHORT_TIMEOUT,
    SIMULAR_HUMANO,
    PAUSA_ENTRE_ACOES_MIN,
    PAUSA_ENTRE_ACOES_MAX,
    DIGITACAO_CADENCIA_MIN,
    DIGITACAO_CADENCIA_MAX
)
from .auth import AuthHandler

class SeiNavigator:
    """
    Controla ações atômicas dentro do SEI e a navegação controlada por iframes.
    """

    def __init__(self, driver, logger: Optional[Callable[[str], None]] = None, simular_humano: bool = SIMULAR_HUMANO):
        self.driver = driver
        self.logger = logger or (lambda msg: None)
        self.auth_handler = AuthHandler(driver, logger=self.logger)
        self.simular_humano = simular_humano

    def pausa_humana(self, min_s: float = PAUSA_ENTRE_ACOES_MIN, max_s: float = PAUSA_ENTRE_ACOES_MAX):
        """Pausa com tempo variável e jitter aleatório para emular comportamento humano."""
        if self.simular_humano:
            time.sleep(random.uniform(min_s, max_s))

    def digitar_como_humano(self, elemento, texto: str):
        """Digita texto caractere por caractere simulando a cadência natural de digitação humana."""
        elemento.clear()
        if self.simular_humano:
            time.sleep(random.uniform(0.2, 0.4))
            for char in texto:
                elemento.send_keys(char)
                time.sleep(random.uniform(DIGITACAO_CADENCIA_MIN, DIGITACAO_CADENCIA_MAX))
            time.sleep(random.uniform(0.3, 0.6))
        else:
            elemento.send_keys(texto)

    def realizar_login_inicial(self, usuario: str, senha: str, orgao: str = "UERJ") -> bool:
        """Executa a rotina de login no SEI-RJ caso a tela de autenticação esteja aberta."""
        return self.auth_handler.realizar_login_inicial(usuario=usuario, senha=senha, orgao=orgao)

    def _esta_autenticado(self) -> bool:
        """Checa presença de elementos típicos do SEI após login (pesquisa rápida, combo de unidades ou menu)."""
        try:
            self.voltar_para_raiz()
            # Se encontrar campo de pesquisa rápida ou combo de unidades, está autenticado
            if self.driver.find_elements(By.ID, SELETORES_SEI["campo_pesquisa"]):
                return True
            if self.driver.find_elements(By.ID, SELETORES_SEI["combo_unidade"]):
                return True
            # Se a barra de sistema estiver presente e não for a página de login
            if "login.php" not in self.driver.current_url.lower():
                if self.driver.find_elements(By.ID, "navInfraBarraNavegacao") or self.driver.find_elements(By.ID, "divInfraBarraSistemaPadrao"):
                    return True
        except Exception:
            pass
        return False

    def garantir_login_ativo(self, timeout: int = 90, usuario: str = "", senha: str = "", orgao: str = "UERJ") -> bool:
        """
        Verifica se o usuário já está autenticado no SEI.
        Se estiver na tela de login, tenta realizar login inicial caso usuario/senha informados.
        Caso contrário (ou se exigir Gov.br / 2FA / validação), aguarda até `timeout` segundos
        para que o usuário finalize a autenticação na janela do navegador.
        """
        self.voltar_para_raiz()

        # 1. Verifica se já está autenticado (sessão anterior ou cookies)
        if self._esta_autenticado():
            self.logger("Sessão autenticada identificada no SEI.")
            return True

        # 2. Se informou usuário e senha na interface, tenta login automatizado
        if usuario and senha:
            self.logger(f"Tentando login automático no SEI para o órgão '{orgao}'...")
            try:
                self.realizar_login_inicial(usuario=usuario, senha=senha, orgao=orgao)
            except Exception as e:
                self.logger(f"Aviso no login automático: {e}")

            time.sleep(2)
            if self._esta_autenticado():
                self.logger("Login automático concluído com sucesso!")
                return True

        # 3. Aguarda o usuário autenticar manualmente no navegador se necessário
        self.logger(
            "Atenção: Aguardando autenticação no SEI... "
            "Por favor, conclua o acesso no navegador aberto (Gov.br, Certificado Digital ou Usuário/Senha)."
        )

        inicio = time.time()
        mensagem_intervalo = 0
        while time.time() - inicio < timeout:
            time.sleep(2)
            if self._esta_autenticado():
                self.logger("Login no SEI confirmado com sucesso! Prosseguindo...")
                return True

            mensagem_intervalo += 2
            if mensagem_intervalo >= 15:
                restante = int(timeout - (time.time() - inicio))
                self.logger(f"Ainda aguardando login no SEI... (tempo restante: {restante}s)")
                mensagem_intervalo = 0

        self.logger(f"Tempo limite ({timeout}s) esgotado aguardando login no SEI.")
        return False

    # -------------------------------------------------------------
    # Gestão de Contexto e Iframes
    # -------------------------------------------------------------

    def voltar_para_raiz(self):
        """Retorna o foco do Selenium para o contexto raiz da página (fora de qualquer iframe)."""
        self.driver.switch_to.default_content()

    def _esta_no_processo(self) -> bool:
        """
        Verifica se alguma janela aberta do navegador está na tela de visualização do processo.
        Percorre todas as abas/janelas abertas para localizar a tela do processo (SEI 5.x, 4.x e 3.x).
        Ao encontrar, deixa o driver posicionado nessa janela e na raiz do documento.
        """
        try:
            janelas = list(self.driver.window_handles)
        except Exception:
            return False

        # Prioriza a janela atual
        try:
            cur = self.driver.current_window_handle
            if cur in janelas:
                janelas.remove(cur)
                janelas.insert(0, cur)
        except Exception:
            pass

        for handle in janelas:
            try:
                self.driver.switch_to.window(handle)
                self.voltar_para_raiz()

                # 1. Checa elementos característicos da tela do processo no SEI
                if (
                    self.driver.find_elements(By.ID, "ifrArvore")
                    or self.driver.find_elements(By.ID, "divIframeArvore")
                    or self.driver.find_elements(By.ID, "divInfraBarraLocalizacao")
                    or self.driver.find_elements(By.ID, "ifrConteudoVisualizacao")
                    or self.driver.find_elements(By.XPATH, "//*[contains(@class, 'infraBarraLocalizacao')]")
                ):
                    return True

                # 2. Checa se a URL é de procedimento aberto e não está no modal de senha
                url = self.driver.current_url.lower()
                if (
                    "procedimento_trabalhar" in url
                    or "procedimento_visualizar" in url
                    or "arvore_visualizar" in url
                ):
                    if not self.driver.find_elements(By.ID, "divIdentificacao"):
                        return True
            except Exception:
                continue

        return False

    def aguardar_estar_no_processo(self, timeout: int = 15) -> bool:
        """
        Aguarda em loop até que a interface do processo esteja totalmente carregada no navegador.
        Útil para aguardar a navegação/redirecionamento pós-autenticação de processo sigiloso.
        """
        fim = time.time() + timeout
        while time.time() < fim:
            if self._esta_no_processo():
                return True
            time.sleep(0.5)
        return False

    def entrar_frame_visualizacao(self, timeout: int = DEFAULT_TIMEOUT, tentativas: int = 2):
        """
        Alterna o foco para o iframe pai 'ifrVisualizacao' caso exista (SEI 3.x).
        No SEI 5.x, a área principal do processo é no contexto raiz (com divIframeVisualizacao / ifrArvore).
        """
        self.voltar_para_raiz()
        iframes_vis = self.driver.find_elements(By.ID, SELETORES_SEI["iframe_visualizacao"])
        if iframes_vis and iframes_vis[0].tag_name.lower() == "iframe":
            try:
                WebDriverWait(self.driver, timeout).until(
                    EC.frame_to_be_available_and_switch_to_it((By.ID, SELETORES_SEI["iframe_visualizacao"]))
                )
            except Exception:
                self.voltar_para_raiz()

    def entrar_frame_arvore(self, timeout: int = DEFAULT_TIMEOUT):
        """
        Entra no iframe 'ifrArvore' (lado esquerdo com a lista de documentos).
        Compatível com SEI 5.x (ifrArvore direto na raiz) e SEI 3.x (aninhado em ifrVisualizacao).
        """
        self.voltar_para_raiz()
        # 1. Tenta entrar diretamente em ifrArvore (SEI 5.x / 4.x)
        try:
            WebDriverWait(self.driver, 4).until(
                EC.frame_to_be_available_and_switch_to_it((By.ID, SELETORES_SEI["iframe_arvore"]))
            )
            return True
        except Exception:
            pass

        # 2. Se não encontrou direto na raiz, tenta via ifrVisualizacao (SEI 3.x)
        try:
            self.voltar_para_raiz()
            self.entrar_frame_visualizacao(timeout=5)
            WebDriverWait(self.driver, timeout).until(
                EC.frame_to_be_available_and_switch_to_it((By.ID, SELETORES_SEI["iframe_arvore"]))
            )
            return True
        except Exception as e:
            raise e

    def entrar_frame_conteudo(self, timeout: int = DEFAULT_TIMEOUT):
        """
        Entra no iframe do conteúdo do documento (lado direito).
        No SEI 5.x:
          1. Entra em <iframe id="ifrConteudoVisualizacao">.
          2. Se houver o sub-iframe interno <iframe id="ifrVisualizacao"> (onde o texto do documento é montado),
             entra nele para acesso direto ao corpo e assinaturas.
        No SEI 3.x:
          Entra via ifrVisualizacao -> ifrConteudoVisualizacao.
        """
        self.voltar_para_raiz()
        # 1. Tenta entrar em ifrConteudoVisualizacao (SEI 5.x / 4.x)
        try:
            WebDriverWait(self.driver, 4).until(
                EC.frame_to_be_available_and_switch_to_it((By.ID, SELETORES_SEI["iframe_conteudo"]))
            )
            # No SEI 5.x, o documento selecionado fica dentro de ifrVisualizacao (sub-iframe de ifrConteudoVisualizacao)
            try:
                sub_ifrs = self.driver.find_elements(By.ID, "ifrVisualizacao")
                if sub_ifrs and sub_ifrs[0].tag_name.lower() == "iframe":
                    WebDriverWait(self.driver, 3).until(
                        EC.frame_to_be_available_and_switch_to_it((By.ID, "ifrVisualizacao"))
                    )
            except Exception:
                pass
            return True
        except Exception:
            pass

        # 2. Se não encontrou direto, tenta via ifrVisualizacao (SEI 3.x)
        try:
            self.voltar_para_raiz()
            self.entrar_frame_visualizacao(timeout=5)
            WebDriverWait(self.driver, timeout).until(
                EC.frame_to_be_available_and_switch_to_it((By.ID, SELETORES_SEI["iframe_conteudo"]))
            )
            return True
        except Exception as e:
            raise e

    def voltar_frame_pai(self):
        """Sobe um nível na hierarquia de iframes."""
        self.driver.switch_to.parent_frame()

    # -------------------------------------------------------------
    # Ações Principais no SEI
    # -------------------------------------------------------------

    def _buscar_elemento_em_frames(self, seletores_by_value: list, profundidade_max: int = 3):
        """
        Busca um elemento percorrendo recursivamente todos os iframes da página.
        Aceita uma lista de (By, valor) para tentar múltiplos seletores.
        Retorna (elemento, frame_handle) ou (None, None) se não encontrar.

        A função deixa o driver posicionado no frame onde o elemento foi encontrado.
        """
        def _buscar_no_contexto_atual(profundidade):
            # Tenta cada seletor no contexto atual
            for by, valor in seletores_by_value:
                try:
                    elems = self.driver.find_elements(by, valor)
                    visiveis = [e for e in elems if e.is_displayed()]
                    if visiveis:
                        return visiveis[0]
                except Exception:
                    pass

            if profundidade >= profundidade_max:
                return None

            # Busca em sub-iframes
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            for frame in iframes:
                try:
                    self.driver.switch_to.frame(frame)
                    resultado = _buscar_no_contexto_atual(profundidade + 1)
                    if resultado:
                        return resultado
                    self.driver.switch_to.parent_frame()
                except Exception:
                    try:
                        self.driver.switch_to.parent_frame()
                    except Exception:
                        self.voltar_para_raiz()
            return None

        self.voltar_para_raiz()
        return _buscar_no_contexto_atual(0)

    def trocar_unidade(self, sigla_unidade: str):
        """
        Altera a lotação ativa no menu superior do SEI.
        Procura o combo de unidades em todos os iframes da página,
        pois no SEI-RJ a barra de navegação pode estar dentro de ifrTopo ou similar.
        """
        seletores = [
            (By.ID, SELETORES_SEI["combo_unidade"]),
            (By.NAME, "selInfraUnidades"),
            (By.CSS_SELECTOR, "select[id*='nidade']"),
            (By.CSS_SELECTOR, "select[name*='nidade']"),
        ]
        elem = self._buscar_elemento_em_frames(seletores)

        if not elem:
            self.logger(f"Aviso: Combo de unidades não localizado. Unidade atual mantida.")
            self.voltar_para_raiz()
            return

        try:
            select = Select(elem)
            opcoes = [opt.text for opt in select.options]
            opcao_correspondente = next(
                (opt for opt in opcoes if sigla_unidade.lower() in opt.lower()), None
            )

            if not opcao_correspondente:
                self.logger(f"Aviso: Unidade '{sigla_unidade}' não encontrada no combo. Mantendo a atual.")
                self.voltar_para_raiz()
                return

            try:
                atual = select.first_selected_option.text.strip()
                if atual == opcao_correspondente.strip():
                    self.logger(f"Unidade já está definida como: {opcao_correspondente}")
                    self.voltar_para_raiz()
                    return
            except Exception:
                pass

            select.select_by_visible_text(opcao_correspondente)
            self.logger(f"Unidade alterada para: {opcao_correspondente}")
            time.sleep(2)
        except Exception as e:
            self.logger(f"Não foi possível alternar unidade: {e}")

        self.voltar_para_raiz()

    def _localizar_campo_pesquisa(self):
        """
        Localiza o campo de busca rápida do SEI usando múltiplos seletores.
        Percorre todos os iframes da página (incluindo ifrTopo e similares).
        Retorna o elemento encontrado e deixa o driver posicionado no frame correto.
        """
        self.tratar_alerta_se_houver()
        seletores = [
            (By.ID, "txtPesquisaRapida"),
            (By.NAME, "txtPesquisaRapida"),
            (By.CSS_SELECTOR, "input[id*='esquisa']"),
            (By.CSS_SELECTOR, "input[name*='esquisa']"),
            (By.CSS_SELECTOR, "input[placeholder*='esquisar']"),
            (By.CSS_SELECTOR, "input[type='search']"),
            (By.XPATH, "//input[contains(@placeholder, 'esquisar') or contains(@id, 'esquisa') or contains(@name, 'esquisa')]"),
        ]
        elem = self._buscar_elemento_em_frames(seletores)
        if elem:
            return elem

        # Último recurso: WebDriverWait no contexto raiz com timeout
        self.voltar_para_raiz()
        return WebDriverWait(self.driver, DEFAULT_TIMEOUT).until(
            EC.presence_of_element_located((By.ID, SELETORES_SEI["campo_pesquisa"]))
        )

    def abrir_processo(self, numero_processo: str, link: str = "", senha: str = "", usuario: str = "") -> bool:
        """
        Abre o processo no SEI.
        1. Se houver 'link' direto informado na planilha: tenta abrir navegando diretamente para a URL.
        2. Se não houver link (ou se a tentativa por link falhar): recorre à digitação do número
           do processo no campo de busca rápida da janela (canto superior direito).

        Tratamentos adicionais:
        - Localiza o campo de busca dentro de iframes caso não exista no contexto raiz.
        - Detecta e recupera erro 'target frame detached' com refresh + renavegação.
        - Propaga InvalidSessionIdException para que o orquestrador possa reiniciar o driver.
        """
        self.tratar_alerta_se_houver()
        proc_limpo = str(numero_processo).strip()
        link_limpo = str(link).strip() if link else ""

        # Tentativa 1: Abrir diretamente pelo link caso fornecido
        if link_limpo and ("http" in link_limpo.lower() or "controlador.php" in link_limpo.lower()):
            self.logger(f"Processo {proc_limpo} possui link direto na planilha. Acessando URL...")
            self.voltar_para_raiz()
            try:
                self.driver.get(link_limpo)
                time.sleep(1.5)

                # Se abriu em nova janela ou aba, alterna o foco
                if len(self.driver.window_handles) > 1:
                    self.driver.switch_to.window(self.driver.window_handles[-1])

                # Trata credenciais se for processo sigiloso
                self.auth_handler.tratar_processo_sigiloso(senha=senha, usuario=usuario)

                # Valida se a tela do processo carregou (SEI 5.x / 4.x / 3.x)
                if self.aguardar_estar_no_processo(timeout=15):
                    self.logger(f"Processo {proc_limpo} aberto com sucesso pelo link direto!")
                    return True
                else:
                    self.logger(f"Aviso: Processo não carregou imediatamente pelo link direto. Recorrendo ao campo de busca...")
            except InvalidSessionIdException:
                # Sessão inválida — propaga para o orquestrador tentar reconectar
                raise
            except Exception as e_link:
                self.logger(f"Aviso: Não foi possível abrir pelo link direto ({e_link}). Recorrendo ao campo de busca...")

        # Tentativa 2: Busca digitando o número no campo de pesquisa
        self.logger(f"Digitando processo {proc_limpo} no campo de busca da janela...")
        if not proc_limpo:
            return False

        # Formatos alternativos: exato e sem prefixo SEI- (ou vice-versa)
        formatos_busca = [proc_limpo]
        if proc_limpo.upper().startswith("SEI-"):
            formatos_busca.append(proc_limpo[4:].strip())
        else:
            formatos_busca.append(f"SEI-{proc_limpo}")

        for termo in formatos_busca:
            try:
                # --- Localiza o campo de pesquisa (raiz ou iframe) ---
                campo_busca = self._localizar_campo_pesquisa()
                self.digitar_como_humano(campo_busca, termo)
                self.pausa_humana(0.4, 0.8)
                campo_busca.send_keys(Keys.RETURN)

                # Fallback: clica no botão de pesquisa caso a tecla Enter não tenha submetido
                time.sleep(0.6)
                try:
                    self.voltar_para_raiz()
                    botoes = self.driver.find_elements(
                        By.XPATH,
                        "//*[@id='btnPesquisaRapida' or @name='btnPesquisaRapida' or @id='lnkPesquisaRapida' or contains(@title, 'Pesquisa Rápida')]"
                    )
                    if botoes and botoes[0].is_displayed():
                        botoes[0].click()
                except Exception:
                    pass

                time.sleep(1.5)

                # 1. Se abriu em nova janela ou aba (pop-up), muda para a mais recente
                try:
                    if len(self.driver.window_handles) > 1:
                        self.driver.switch_to.window(self.driver.window_handles[-1])
                except NoSuchWindowException:
                    pass

                # 2. Trata eventual janela/modal de senha para processos sigilosos
                self.auth_handler.tratar_processo_sigiloso(senha=senha, usuario=usuario)

                # 3. Verifica se caiu em tela de resultado de busca (pesquisa_rapida com links)
                self.voltar_para_raiz()
                if not self._esta_no_processo():
                    # Procura por link do processo na tabela de resultados
                    apenas_digitos = "".join(re.findall(r"\d+", termo))
                    xpath_link = (
                        f"//a[contains(text(), '{termo}') "
                        f"or contains(@href, 'procedimento_trabalhar') "
                        f"or contains(@href, '{apenas_digitos}')]"
                    )
                    links = self.driver.find_elements(By.XPATH, xpath_link)
                    for lk in links:
                        if lk.is_displayed():
                            lk.click()
                            time.sleep(1.5)
                            break

                # 4. Aguarda renderização e confirma se o processo está aberto
                if self.aguardar_estar_no_processo(timeout=15):
                    self.logger(f"Processo {proc_limpo} aberto com sucesso!")
                    return True

            except InvalidSessionIdException:
                # Sessão inválida — propaga para o orquestrador tentar reconectar
                raise
            except WebDriverException as e:
                msg = str(e).lower()
                if "target frame detached" in msg or "disconnected" in msg:
                    # Frame desconectado após redirecionamento do SEI — tenta recuperar
                    self.logger(f"Frame desconectado ao buscar '{termo}'. Tentando recuperar a sessão...")
                    try:
                        self.voltar_para_raiz()
                        self.driver.refresh()
                        time.sleep(2)
                    except Exception:
                        pass
                    # Não tenta o próximo formato — aborta a busca para este processo
                    break
                self.logger(f"Aviso na tentativa de busca por '{termo}': {e}")
                continue
            except Exception as e:
                self.logger(f"Aviso na tentativa de busca por '{termo}': {e}")
                continue

        self.logger(f"Falha ao pesquisar/abrir o processo {numero_processo} após tentar formatos alternativos.")
        return False

    # -------------------------------------------------------------
    # Extração de Dados da Árvore e Histórico
    # -------------------------------------------------------------

    def extrair_nos_arvore(self) -> List[str]:
        """
        Coleta os nomes de todos os documentos e nós visíveis na árvore do processo.
        """
        self.entrar_frame_arvore()
        try:
            WebDriverWait(self.driver, DEFAULT_TIMEOUT).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, SELETORES_SEI["nos_arvore"]))
            )
            elementos = self.driver.find_elements(By.CSS_SELECTOR, SELETORES_SEI["nos_arvore"])
            return [elem.text.strip() for elem in elementos if elem.text.strip()]
        except Exception:
            return []

    def obter_ultimo_documento_arvore(self) -> str:
        """Retorna o nome do último documento juntado na árvore."""
        nos = self.extrair_nos_arvore()
        return nos[-1] if nos else "Nenhum documento localizado"

    def tratar_alerta_se_houver(self) -> bool:
        """Verifica e aceita alertas pendentes na tela para não travar a esteira."""
        try:
            alerta = self.driver.switch_to.alert
            texto = alerta.text
            alerta.accept()
            self.logger(f"Alerta do sistema interceptado e fechado: {texto}")
            return True
        except Exception:
            return False

    def expandir_todas_pastas_arvore(self):
        """
        No SEI, a cada 10 documentos é criada uma pasta.
        Utiliza o botão nativo do SEI 'Abrir todas as Pastas' (ícone mais.svg / iconAP*)
        para expandir todas as pastas de uma só vez, aguardando 3 segundos.
        """
        try:
            self.entrar_frame_arvore()
            self.tratar_alerta_se_houver()

            # 1. Procura o botão nativo do SEI para abrir todas as pastas (ícone mais.svg / iconAP)
            seletores_botao = [
                "//img[contains(@title, 'Abrir todas as Pastas') or contains(@id, 'iconAP') or contains(@alt, 'Abrir todas as Pastas')]",
                "//a[contains(@title, 'Abrir todas as Pastas') or contains(@href, 'abrirTodasPastas') or contains(@onclick, 'abrirTodasPastas')]",
                "//*[@id[starts-with(., 'iconAP')]]",
                "//img[contains(@src, 'mais.svg')]"
            ]

            botao_abrir_todas = None
            for sel in seletores_botao:
                elems = self.driver.find_elements(By.XPATH, sel)
                visiveis = [e for e in elems if e.is_displayed()]
                if visiveis:
                    botao_abrir_todas = visiveis[0]
                    break

            if not botao_abrir_todas:
                # Checa se o elemento está no contexto raiz caso não esteja no frame
                self.voltar_para_raiz()
                for sel in seletores_botao:
                    elems = self.driver.find_elements(By.XPATH, sel)
                    visiveis = [e for e in elems if e.is_displayed()]
                    if visiveis:
                        botao_abrir_todas = visiveis[0]
                        break

            if botao_abrir_todas:
                try:
                    link_pai = botao_abrir_todas.find_elements(By.XPATH, "./ancestor::a")
                    alvo = link_pai[0] if link_pai else botao_abrir_todas
                    alvo.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", botao_abrir_todas)
                self.logger("Botão 'Abrir todas as Pastas' acionado. Aguardando 3s para expansão dos documentos...")
                time.sleep(3.0)
                self.tratar_alerta_se_houver()
                self.entrar_frame_arvore()
                return

            # 1.1 Tenta acionar via JS nativo caso o elemento exista no DOM do ifrArvore
            self.entrar_frame_arvore()
            try:
                tem_icone = self.driver.execute_script(
                    "return !!(document.querySelector(\"[id^='iconAP']\") || document.querySelector(\"img[title*='Abrir todas'], img[src*='mais.svg']\"));"
                )
                if tem_icone:
                    self.driver.execute_script("""
                        if (typeof abrirTodasPastas === 'function') {
                            abrirTodasPastas();
                        } else {
                            var el = document.querySelector("[id^='iconAP']") || document.querySelector("img[title*='Abrir todas']");
                            if (el) el.click();
                        }
                    """)
                    self.logger("Função 'abrirTodasPastas()' executada. Aguardando 3s para expansão dos documentos...")
                    time.sleep(3.0)
                    self.tratar_alerta_se_houver()
            except Exception:
                pass

        except Exception as e:
            self.logger(f"Aviso ao expandir pastas da árvore: {e}")
            self.tratar_alerta_se_houver()

    def listar_elementos_nos_arvore(self) -> List[dict]:
        """
        Retorna a lista de nós visíveis da árvore acompanhados de seus elementos Selenium,
        expandindo pastas automaticamente e ignorando entradas duplicadas.
        """
        self.tratar_alerta_se_houver()
        self.entrar_frame_arvore()
        self.expandir_todas_pastas_arvore()

        def _coletar_elementos():
            WebDriverWait(self.driver, DEFAULT_TIMEOUT).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, SELETORES_SEI["nos_arvore"]))
            )
            elementos = self.driver.find_elements(By.CSS_SELECTOR, SELETORES_SEI["nos_arvore"])
            lista = []
            vistos = set()
            for el in elementos:
                try:
                    if not el.is_displayed():
                        continue
                    texto = el.text.strip()
                    if texto and texto not in vistos:
                        vistos.add(texto)
                        lista.append({"texto": texto, "elemento": el})
                except Exception:
                    pass
            return lista

        try:
            return _coletar_elementos()
        except UnexpectedAlertPresentException:
            self.tratar_alerta_se_houver()
            time.sleep(1.0)
            try:
                return _coletar_elementos()
            except Exception as e:
                self.logger(f"Não foi possível listar elementos da árvore após alerta: {e}")
                return []
        except Exception as e:
            self.logger(f"Não foi possível listar elementos da árvore: {e}")
            return []

    def extrair_detalhes_assinatura_documento(self, elemento_no, nome_documento: str = "") -> dict:
        """
        Clica no nó do documento na árvore e extrai:
        - data_assinatura: data da primeira assinatura eletrônica (DD/MM/AAAA)
        - secretario: nome do Secretário(a) identificado na assinatura (ou '' se não houver)
        """
        import re
        resultado = {
            "data_assinatura": "",
            "secretario": ""
        }

        try:
            # 1. Clica no documento na árvore via JavaScript para garantir clique mesmo com scroll
            self.entrar_frame_arvore()
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elemento_no)
            self.pausa_humana(0.5, 1.2)
            self.driver.execute_script("arguments[0].click();", elemento_no)
            self.pausa_humana(1.5, 3.0)

            # 2. Entra no iframe da direita onde o texto do documento é renderizado
            self.entrar_frame_conteudo()
            corpo_doc = WebDriverWait(self.driver, SHORT_TIMEOUT + 2).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            texto_doc = corpo_doc.text

            # Se o texto for pequeno ou não contiver termo de assinatura, varre sub-iframes internos
            if "assinado" not in texto_doc.lower():
                sub_frames = self.driver.find_elements(By.TAG_NAME, "iframe")
                for sf in sub_frames:
                    try:
                        self.driver.switch_to.frame(sf)
                        s_body = self.driver.find_element(By.TAG_NAME, "body")
                        if s_body and s_body.text:
                            texto_doc += "\n" + s_body.text
                        self.driver.switch_to.parent_frame()
                    except Exception:
                        pass

            # Extração da data da primeira assinatura:
            # Padrão: "Documento assinado eletronicamente por [Nome] em DD/MM/AAAA"
            padrao_data = r"assinado\s+eletronicamente\s+por[^\n\r]*?em\s+(\d{2}/\d{2}/\d{4})"
            matches_data = re.findall(padrao_data, texto_doc, re.IGNORECASE)
            
            if matches_data:
                resultado["data_assinatura"] = matches_data[0]
            else:
                padrao_secundario = r"assinado[^\n\r]*?(\d{2}/\d{2}/\d{4})"
                matches_sec = re.findall(padrao_secundario, texto_doc, re.IGNORECASE)
                if matches_sec:
                    resultado["data_assinatura"] = matches_sec[0]

            # Extração dinâmica do nome de QUALQUER secretário(a):
            # Captura qualquer nome antes de "Secretário (a)", "Secretária", "Secretário ad hoc", etc.
            padrao_secretario = re.compile(
                r"assinado\s+eletronicamente\s+por\s+([A-Za-zÀ-ÖØ-öø-ÿ\s.\'-]+?)(?:,|\s+-\s+|\n|\r\n|\s{2,})\s*(?:o\s+|a\s+)?Secret[áa]ri[oa](?:\s*\([a-zA-Z/ ]*\)|[a-zA-ZÀ-ÿ\s-]*)?",
                re.IGNORECASE
            )
            match_secretario = padrao_secretario.search(texto_doc)
            if match_secretario:
                resultado["secretario"] = match_secretario.group(1).strip()

        except Exception as e:
            self.logger(f"Aviso ao ler assinatura do documento no conteúdo: {e}")

        # 3. Fallback: Se não localizou no corpo do documento, verifica no Histórico
        if not resultado["data_assinatura"] and nome_documento:
            resultado["data_assinatura"] = self._buscar_assinatura_no_historico(nome_documento)

        # Retorna o contexto para a árvore
        self.entrar_frame_arvore()
        return resultado

    def obter_primeira_assinatura_documento(self, elemento_no, nome_documento: str = "") -> str:
        """Mantido para compatibilidade: retorna apenas a data da primeira assinatura."""
        detalhes = self.extrair_detalhes_assinatura_documento(elemento_no, nome_documento)
        return detalhes.get("data_assinatura", "")

    def _buscar_assinatura_no_historico(self, nome_documento: str) -> str:
        """Busca data de assinatura na tabela de histórico de andamentos."""
        import re
        try:
            self.entrar_frame_arvore()
            btn_historico = WebDriverWait(self.driver, SHORT_TIMEOUT).until(
                EC.element_to_be_clickable((By.XPATH, SELETORES_SEI["btn_consultar_andamento"]))
            )
            btn_historico.click()
            time.sleep(1)

            self.entrar_frame_conteudo()
            linhas = self.driver.find_elements(By.XPATH, "//table[contains(@class, 'infraTable')]//tbody/tr")
            
            for linha in reversed(linhas):  # Do mais antigo para o mais recente para pegar a 1ª assinatura
                cols = linha.find_elements(By.TAG_NAME, "td")
                if len(cols) >= 4:
                    data_hora = cols[0].text.strip()
                    descricao = cols[3].text.strip()
                    if "assinado" in descricao.lower() and nome_documento.lower() in descricao.lower():
                        match = re.search(r"(\d{2}/\d{2}/\d{4})", data_hora)
                        if match:
                            return match.group(1)
        except Exception:
            pass
        return ""

    def extrair_ultimo_andamento_historico(self) -> str:
        """
        Clica no botão 'Consultar Andamento' e extrai a linha mais recente da tabela de histórico.
        """
        self.entrar_frame_arvore()
        try:
            btn_historico = WebDriverWait(self.driver, SHORT_TIMEOUT).until(
                EC.element_to_be_clickable((By.XPATH, SELETORES_SEI["btn_consultar_andamento"]))
            )
            btn_historico.click()
        except Exception:
            self.logger("Botão de histórico direto não localizado via barra da árvore.")

        self.entrar_frame_conteudo()
        try:
            primeira_linha = WebDriverWait(self.driver, DEFAULT_TIMEOUT).until(
                EC.presence_of_element_located((By.XPATH, SELETORES_SEI["primeira_linha_historico"]))
            )
            colunas = primeira_linha.find_elements(By.TAG_NAME, "td")
            andamento_texto = " | ".join([col.text.strip() for col in colunas if col.text.strip()])
            return andamento_texto or "Linha de andamento vazia"
        except Exception:
            return "Não foi possível carregar a tabela de histórico"
        finally:
            self.voltar_para_raiz()

