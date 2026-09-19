"""
Gerenciador do WebDriver do Selenium.
Inicializa o navegador Microsoft Edge nativo com suporte a persistência de perfil e headless.

IMPORTANTE: O fallback para Chrome foi removido intencionalmente.
O SEI-RJ pode bloquear a conexão se detectar mudança de navegador/User-Agent entre sessões.
Sempre use o Edge — o mesmo navegador utilizado no ambiente corporativo.
"""

from selenium import webdriver
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from typing import Optional
import time
import random
from config.settings import PROFILES_DIR, SEI_URL


class DriverManager:
    """
    Gerencia a inicialização, perfil e encerramento do navegador de automação.
    Utiliza exclusivamente o Microsoft Edge para manter consistência de User-Agent
    e cookies de sessão com o ambiente corporativo onde o SEI-RJ está configurado.
    """

    def __init__(self, headless: bool = False, perfil_persistente: bool = True):
        self.headless = headless
        self.perfil_persistente = perfil_persistente
        self.driver: Optional[webdriver.Remote] = None

    def iniciar_driver(self) -> webdriver.Remote:
        """
        Inicia o Microsoft Edge configurado para simular um usuário real:
        - Perfil persistente para reutilizar cookies e sessão Gov.br
        - Flags anti-detecção de automação (navigator.webdriver, AutomationControlled)
        - Tamanho de janela real (não padrão de bots)
        - Pausa inicial para o navegador terminar de carregar antes de interagir
        """
        options = EdgeOptions()

        if self.headless:
            options.add_argument("--headless=new")

        # --- Configurações básicas de estabilidade ---
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-popup-blocking")

        # --- Janela com tamanho humano (evita fingerprint de bot) ---
        # Pequena variação aleatória para não ter sempre exatamente o mesmo tamanho
        largura = random.randint(1280, 1440)
        altura = random.randint(720, 900)
        options.add_argument(f"--window-size={largura},{altura}")

        # --- Flags anti-detecção de automação ---
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        options.add_experimental_option("useAutomationExtension", False)

        # --- Desabilita banners e avisos do Chrome/Edge que revelam automação ---
        options.add_argument("--disable-infobars")

        # --- Perfil persistente para reutilizar cookies e sessão autenticada ---
        if self.perfil_persistente:
            options.add_argument(f"--user-data-dir={str(PROFILES_DIR)}")

        # Inicia o Edge — SEM fallback para Chrome
        # Se o Edge não estiver instalado ou o driver for incompatível,
        # o erro é propagado ao usuário com mensagem clara.
        try:
            self.driver = webdriver.Edge(options=options)
        except Exception as e:
            raise RuntimeError(
                f"Não foi possível iniciar o Microsoft Edge: {e}\n"
                "Verifique se o msedgedriver.exe está atualizado e compatível com a versão do Edge instalada.\n"
                "Acesse: https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/"
            ) from e

        # --- Remove a propriedade navigator.webdriver via CDP ---
        # Isso impede que o SEI detecte o Selenium pela flag padrão de automação
        try:
            self.driver.execute_cdp_cmd(
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

        self.driver.maximize_window()

        # Pausa humana antes de navegar: o Edge precisa de um momento para
        # inicializar extensões e o perfil antes de receber comandos
        time.sleep(random.uniform(1.5, 2.5))

        self.driver.get(SEI_URL)

        # Pausa após navegar: aguarda a página carregar completamente
        # antes de o código tentar interagir com elementos
        time.sleep(random.uniform(2.0, 3.5))

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
