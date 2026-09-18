"""
Navegador de Ações do SEI.
Isola a interação com elementos do DOM e o gerenciamento de iframes (ifrVisualizacao, ifrArvore, ifrConteudoVisualizacao).
"""

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
import time
import re
from typing import Callable, List, Optional
from config.settings import SELETORES_SEI, DEFAULT_TIMEOUT, SHORT_TIMEOUT
from .auth import AuthHandler

class SeiNavigator:
    """
    Controla ações atômicas dentro do SEI e a navegação controlada por iframes.
    """

    def __init__(self, driver, logger: Optional[Callable[[str], None]] = None):
        self.driver = driver
        self.logger = logger or (lambda msg: None)
        self.auth_handler = AuthHandler(driver, logger=self.logger)

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
        """Retorna o foco para o contexto raiz da página (fora de todos os iframes)."""
        self.driver.switch_to.default_content()

    def entrar_frame_visualizacao(self):
        """Entra no iframe pai 'ifrVisualizacao' onde o processo é montado."""
        self.voltar_para_raiz()
        WebDriverWait(self.driver, DEFAULT_TIMEOUT).until(
            EC.frame_to_be_available_and_switch_to_it((By.ID, SELETORES_SEI["iframe_visualizacao"]))
        )

    def entrar_frame_arvore(self):
        """Entra no iframe 'ifrArvore' (lado esquerdo com a lista de documentos)."""
        self.entrar_frame_visualizacao()
        WebDriverWait(self.driver, DEFAULT_TIMEOUT).until(
            EC.frame_to_be_available_and_switch_to_it((By.ID, SELETORES_SEI["iframe_arvore"]))
        )

    def entrar_frame_conteudo(self):
        """Entra no iframe 'ifrConteudoVisualizacao' (lado direito com documentos e histórico)."""
        self.entrar_frame_visualizacao()
        WebDriverWait(self.driver, DEFAULT_TIMEOUT).until(
            EC.frame_to_be_available_and_switch_to_it((By.ID, SELETORES_SEI["iframe_conteudo"]))
        )

    def voltar_frame_pai(self):
        """Sobe um nível na hierarquia de iframes (ex: de ifrArvore para ifrVisualizacao)."""
        self.driver.switch_to.parent_frame()

    # -------------------------------------------------------------
    # Ações Principais no SEI
    # -------------------------------------------------------------

    def trocar_unidade(self, sigla_unidade: str):
        """
        Altera a lotação ativa no menu superior do SEI.
        """
        self.voltar_para_raiz()
        try:
            select_elem = WebDriverWait(self.driver, DEFAULT_TIMEOUT).until(
                EC.presence_of_element_located((By.ID, SELETORES_SEI["combo_unidade"]))
            )
            select = Select(select_elem)
            
            # Tenta selecionar por texto visível exato ou parcial
            opcoes = [opt.text for opt in select.options]
            opcao_correspondente = next((opt for opt in opcoes if sigla_unidade.lower() in opt.lower()), None)
            
            if opcao_correspondente:
                try:
                    if select.first_selected_option.text.strip() == opcao_correspondente.strip():
                        self.logger(f"Unidade já está definida como: {opcao_correspondente}")
                        return
                except Exception:
                    pass

                select.select_by_visible_text(opcao_correspondente)
                self.logger(f"Unidade alterada para: {opcao_correspondente}")
                time.sleep(2)
            else:
                self.logger(f"Aviso: Unidade '{sigla_unidade}' não encontrada no combo. Mantendo a atual.")
        except Exception as e:
            self.logger(f"Não foi possível alternar unidade pelo seletor padrão: {e}")

    def abrir_processo(self, numero_processo: str, link: str = "", senha: str = "", usuario: str = "") -> bool:
        """
        Abre o processo no SEI.
        1. Se houver 'link' direto informado na planilha: tenta abrir navegando diretamente para a URL.
        2. Se não houver link (ou se a tentativa por link falhar): recorre à digitação do número
           do processo no campo de busca rápida da janela (canto superior direito).
        """
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

                # Aguarda renderização do frame pai de visualização
                self.entrar_frame_visualizacao()
                self.logger(f"Processo {proc_limpo} aberto com sucesso pelo link direto!")
                return True
            except Exception as e_link:
                self.logger(f"Aviso: Não foi possível abrir pelo link direto ({e_link}). Recorrendo ao campo de busca...")

        # Tentativa 2: Busca digitando o número no campo de pesquisa (janela da direita)
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
            self.voltar_para_raiz()
            try:
                campo_busca = WebDriverWait(self.driver, DEFAULT_TIMEOUT).until(
                    EC.presence_of_element_located((By.ID, SELETORES_SEI["campo_pesquisa"]))
                )
                campo_busca.clear()
                campo_busca.send_keys(termo)
                time.sleep(0.3)
                campo_busca.send_keys(Keys.RETURN)

                # Fallback: clica no botão de pesquisa caso a tecla Enter não tenha submetido
                time.sleep(0.6)
                botoes = self.driver.find_elements(
                    By.XPATH, 
                    "//*[@id='btnPesquisaRapida' or @name='btnPesquisaRapida' or @id='lnkPesquisaRapida' or contains(@title, 'Pesquisa Rápida')]"
                )
                if botoes and botoes[0].is_displayed():
                    try:
                        botoes[0].click()
                    except Exception:
                        pass

                time.sleep(1.5)

                # 1. Se abriu em nova janela ou aba (pop-up), muda para a mais recente
                if len(self.driver.window_handles) > 1:
                    self.driver.switch_to.window(self.driver.window_handles[-1])

                # 2. Trata eventual janela/modal de senha para processos sigilosos
                self.auth_handler.tratar_processo_sigiloso(senha=senha, usuario=usuario)

                # 3. Verifica se caiu em tela de resultado de busca (pesquisa_rapida com links)
                self.voltar_para_raiz()
                if not self.driver.find_elements(By.ID, SELETORES_SEI["iframe_visualizacao"]):
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

                # 4. Aguarda renderização do frame pai de visualização
                self.entrar_frame_visualizacao()
                return True

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

    def listar_elementos_nos_arvore(self) -> List[dict]:
        """
        Retorna a lista de nós visíveis da árvore acompanhados de seus elementos Selenium,
        permitindo clicar em cada documento individualmente.
        """
        self.entrar_frame_arvore()
        try:
            WebDriverWait(self.driver, DEFAULT_TIMEOUT).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, SELETORES_SEI["nos_arvore"]))
            )
            elementos = self.driver.find_elements(By.CSS_SELECTOR, SELETORES_SEI["nos_arvore"])
            lista = []
            for el in elementos:
                texto = el.text.strip()
                if texto:
                    lista.append({"texto": texto, "elemento": el})
            return lista
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
            time.sleep(0.5)
            self.driver.execute_script("arguments[0].click();", elemento_no)
            time.sleep(1.5)

            # 2. Entra no iframe da direita onde o texto do documento é renderizado
            self.entrar_frame_conteudo()
            corpo_doc = WebDriverWait(self.driver, SHORT_TIMEOUT + 2).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            texto_doc = corpo_doc.text

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

