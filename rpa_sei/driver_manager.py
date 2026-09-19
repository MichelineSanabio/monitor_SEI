"""
Gerenciador do WebDriver do Selenium.
Inicializa o navegador Microsoft Edge nativo com suporte a persistência de perfil e headless.

IMPORTANTE: O fallback para Chrome foi removido intencionalmente.
O SEI-RJ pode bloquear a conexão se detectar mudança de navegador/User-Agent entre sessões.
Sempre use o Edge — o mesmo navegador utilizado no ambiente corporativo.
"""

from selenium import webdriver
from selenium.webdriver.edge.options import Options as EdgeOptions
from typing import Optional
import time
import random
import shutil
from pathlib import Path
from config.settings import PROFILES_DIR, SEI_URL


# Arquivos de lock que o Edge cria ao abrir um perfil.
# Precisam ser removidos quando o Edge crasha sem fechamento limpo.
LOCK_FILES = [
    "lockfile",
    "SingletonCookie",
    "SingletonLock",
    "SingletonSocket",
]


def _construir_options(perfil_dir: Optional[Path], headless: bool, largura: int, altura: int) -> EdgeOptions:
    """Monta as opções do Edge com flags anti-detecção e perfil opcional."""
    options = EdgeOptions()

    if headless:
        options.add_argument("--headless=new")

    # Estabilidade
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-infobars")

    # Porta de debug dinâmica — evita conflito com instâncias do Edge já abertas
    options.add_argument("--remote-debugging-port=0")

    # Tamanho de janela com variação humana
    options.add_argument(f"--window-size={largura},{altura}")

    # Anti-detecção de automação
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    options.add_experimental_option("useAutomationExtension", False)

    # Tratamento automático de alertas/popups inesperados do sistema
    options.set_capability("unhandledPromptBehavior", "accept")

    # Perfil persistente (opcional)
    if perfil_dir:
        options.add_argument(f"--user-data-dir={str(perfil_dir)}")

    return options


def _limpar_locks_perfil(perfil_dir: Path) -> None:
    """
    Remove arquivos de lock deixados pelo Edge após um crash ou fechamento abrupto.
    Sem isso, a próxima tentativa com o mesmo perfil resulta em crash imediato.
    """
    for nome in LOCK_FILES:
        lock = perfil_dir / nome
        if lock.exists():
            try:
                lock.unlink()
            except Exception:
                pass

    # Também remove a pasta 'Singleton*' se existir como diretório
    for item in perfil_dir.glob("Singleton*"):
        try:
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            else:
                item.unlink()
        except Exception:
            pass


def _aplicar_stealth(driver) -> None:
    """Oculta propriedades do WebDriver via CDP para evitar detecção pelo SEI."""
    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": """
                    // Remove a flag padrão de WebDriver que todos os bots expõem
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    // Simula plugins reais (navegador sem plugins = sinal de bot)
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                    // Simula idioma real do navegador
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['pt-BR', 'pt', 'en-US', 'en']
                    });
                """
            }
        )
    except Exception:
        pass


class DriverManager:
    """
    Gerencia a inicialização, perfil e encerramento do navegador de automação.

    Estratégia de inicialização (3 tentativas em cascata):
      1. Edge com perfil persistente (cookies e sessão SEI reutilizados)
      2. Edge com perfil persistente após limpar arquivos de lock (trata crash anterior)
      3. Edge sem perfil persistente (sessão limpa — requer novo login)
    """

    def __init__(self, headless: bool = False, perfil_persistente: bool = True):
        self.headless = headless
        self.perfil_persistente = perfil_persistente
        self.driver: Optional[webdriver.Remote] = None

    def iniciar_driver(self) -> webdriver.Remote:
        """
        Inicia o Microsoft Edge com estratégia resiliente de 3 tentativas.
        Todas as tentativas usam flags anti-detecção e simulação de comportamento humano.
        """
        largura = random.randint(1280, 1440)
        altura = random.randint(720, 900)

        perfil_dir = PROFILES_DIR if self.perfil_persistente else None
        erros = []

        # --- Tentativa 1: Edge com perfil persistente ---
        if perfil_dir:
            _limpar_locks_perfil(perfil_dir)
            try:
                options = _construir_options(perfil_dir, self.headless, largura, altura)
                self.driver = webdriver.Edge(options=options)
                self._finalizar_inicializacao()
                return self.driver
            except Exception as e1:
                erros.append(f"Tentativa 1 (com perfil): {e1}")
                try:
                    self.driver.quit()
                except Exception:
                    pass
                self.driver = None

            # --- Tentativa 2: Limpa locks e tenta novamente com perfil ---
            _limpar_locks_perfil(perfil_dir)
            try:
                options = _construir_options(perfil_dir, self.headless, largura, altura)
                self.driver = webdriver.Edge(options=options)
                self._finalizar_inicializacao()
                return self.driver
            except Exception as e2:
                erros.append(f"Tentativa 2 (perfil após limpar locks): {e2}")
                try:
                    self.driver.quit()
                except Exception:
                    pass
                self.driver = None

        # --- Tentativa 3: Edge sem perfil (sessão temporária) ---
        try:
            if erros:
                # Só loga o aviso se as tentativas anteriores falharam
                print(
                    "[DriverManager] Aviso: não foi possível usar o perfil persistente. "
                    "Abrindo Edge com sessão temporária (será necessário fazer login manualmente)."
                )
            options = _construir_options(None, self.headless, largura, altura)
            self.driver = webdriver.Edge(options=options)
            self._finalizar_inicializacao()
            return self.driver
        except Exception as e3:
            erros.append(f"Tentativa 3 (sem perfil): {e3}")

        # Todas as tentativas falharam
        detalhe = "\n".join(erros)
        raise RuntimeError(
            f"Não foi possível iniciar o Microsoft Edge após 3 tentativas:\n{detalhe}\n\n"
            "Possíveis causas:\n"
            "  • O msedgedriver.exe está desatualizado — baixe a versão correta em:\n"
            "    https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/\n"
            "  • O Edge está aberto com o mesmo perfil em outra janela — feche-o e tente novamente.\n"
            "  • O Edge não está instalado no caminho padrão."
        )

    def _finalizar_inicializacao(self) -> None:
        """Aplica stealth, maximiza e navega para o SEI com pausas humanas."""
        _aplicar_stealth(self.driver)
        self.driver.maximize_window()

        # Pausa humana: Edge precisa de um momento para carregar o perfil/extensões
        time.sleep(random.uniform(1.5, 2.5))

        self.driver.get(SEI_URL)

        # Pausa após navegar: aguarda a página carregar completamente
        time.sleep(random.uniform(2.0, 3.5))

    def fechar(self):
        """Encerra a instância ativa do WebDriver."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            finally:
                self.driver = None
