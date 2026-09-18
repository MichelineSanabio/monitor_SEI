"""
Gerenciador do WebDriver do Selenium.
Inicializa o navegador Microsoft Edge nativo com suporte a persistência de perfil e headless.
"""

from selenium import webdriver
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from typing import Optional
from config.settings import PROFILES_DIR, SEI_URL

class DriverManager:
    """
    Gerencia a inicialização, perfil e encerramento do navegador de automação.
    """

    def __init__(self, headless: bool = False, perfil_persistente: bool = True):
        self.headless = headless
        self.perfil_persistente = perfil_persistente
        self.driver: Optional[webdriver.Remote] = None

    def iniciar_driver(self) -> webdriver.Remote:
        """
        Inicia o Edge (padrão no Windows corporativo) ou Chrome como alternativa.
        Configura pasta de perfil para reutilização de cookies e login Gov.br.
        """
        options = EdgeOptions()
        
        if self.headless:
            options.add_argument("--headless=new")
        
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-notifications")
        options.add_argument("--window-size=1366,768")

        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        if self.perfil_persistente:
            # Reutiliza diretório de perfil para salvar cookies de sessão
            options.add_argument(f"--user-data-dir={str(PROFILES_DIR)}")

        try:
            self.driver = webdriver.Edge(options=options)
        except Exception:
            # Fallback para Chrome caso o EdgeDriver apresente incompatibilidade
            chrome_opts = ChromeOptions()
            if self.headless:
                chrome_opts.add_argument("--headless=new")
            chrome_opts.add_argument("--disable-blink-features=AutomationControlled")
            chrome_opts.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_opts.add_experimental_option("useAutomationExtension", False)
            self.driver = webdriver.Chrome(options=chrome_opts)

        # Oculta sinalizador navigator.webdriver via CDP para evitar bloqueios por WAF/Anti-bot
        try:
            self.driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {
                    "source": """
                        Object.defineProperty(navigator, 'webdriver', {
                            get: () => undefined
                        });
                    """
                }
            )
        except Exception:
            pass

        self.driver.maximize_window()
        self.driver.get(SEI_URL)
        return self.driver

    def fechar(self):
        """Encerra a instância ativa do WebDriver."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            finally:
                self.driver = None
