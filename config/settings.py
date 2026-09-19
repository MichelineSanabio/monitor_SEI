"""
Módulo de Configurações Gerais do Monitor SEI.
Centraliza unidades do órgão, timeouts, seletores do DOM e diretórios.
"""

from pathlib import Path
import os

# Diretórios base do projeto
BASE_DIR = Path(__file__).resolve().parent.parent
INPUTS_DIR = BASE_DIR / "data" / "inputs"
OUTPUTS_DIR = BASE_DIR / "data" / "outputs"
PROFILES_DIR = BASE_DIR / "data" / "browser_profile"

# Criação automática de diretórios necessários
INPUTS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
PROFILES_DIR.mkdir(parents=True, exist_ok=True)

# 1. Unidades pré-configuradas do órgão (RN01)
# O usuário pode alterar esses nomes conforme as siglas reais de lotação no seu órgão
UNIDADES_PADRAO = [
    "CGUERJ",
    "SCGUERJ",
    "CINQA",
    "COMISTS"
]

# 2. Configurações de Acesso ao SEI
SEI_URL = os.getenv(
    "SEI_URL", 
    "https://sei.rj.gov.br/sip/login.php?sigla_orgao_sistema=ERJ&sigla_sistema=SEI"
)

# 3. Parâmetros de Espera e Timeout (em segundos)
DEFAULT_TIMEOUT = 12
SHORT_TIMEOUT = 3
LONG_TIMEOUT = 25

# 4. Mapeamento de Seletores Críticos do DOM do SEI (SEI-RJ / SIP)
SELETORES_SEI = {
    # Tela de Login Inicial (SIP / SEI-RJ)
    "campo_usuario_login": "txtUsuario",
    "campo_senha_login": "pwdSenha",
    "combo_orgao_login": "selOrgao",
    "btn_acessar_login": "sbmAcessar",
    "orgao_padrao": "UERJ",

    # Troca de unidade ativa
    "combo_unidade": "selInfraUnidades",
    
    # Pesquisa rápida de processo
    "campo_pesquisa": "txtPesquisaRapida",
    "btn_pesquisa": "btnPesquisaRapida",
    
    # Processos sigilosos / tela de credencial
    "container_sigiloso": "divIdentificacao",
    "campo_senha_sigiloso": "//input[(@id='pwdSenha' or @id='txtSenha' or @name='pwdSenha' or @type='password') and not(contains(@style, 'display: none')) and not(contains(@style, 'display:none'))]",
    "campo_usuario_sigiloso": "//input[@id='txtUsuario' or @id='txtLogin']",
    "btn_confirmar_sigiloso": "//*[@id='btnAcessar' or @id='sbmAcessar' or @id='btnConfirmar' or @type='submit' or contains(@value, 'Acessar') or contains(@value, 'Confirmar') or contains(text(), 'Confirmar') or contains(text(), 'Acessar')]",
    
    # Iframes e Containers da Tela do Processo (SEI 3.x / 4.x / 5.x)
    "iframe_visualizacao": "ifrVisualizacao",
    "div_visualizacao": "divIframeVisualizacao",
    "iframe_arvore": "ifrArvore",
    "div_arvore": "divIframeArvore",
    "iframe_conteudo": "ifrConteudoVisualizacao",
    
    # Nós da árvore de documentos
    "nos_arvore": "a.infraArvoreNo, span.infraArvoreNo, a[id^='anc'], a[href*='arvore_visualizar']",
    "btn_consultar_andamento": "//a[contains(@href, 'andamento_consultar') or @title='Consultar Andamento' or contains(@title, 'Andamento')]",
    
    # Tabela de histórico de andamentos
    "primeira_linha_historico": "//table[contains(@class, 'infraTable')]//tbody/tr[2] | //table[@id='tblHistorico']//tr[2]"
}

# 5. Parâmetros de Simulação de Comportamento Humano (Anti-bloqueio / Proteção de Conexão)
# Estes tempos são calibrados para imitar um usuário real navegando no SEI.
# ATENÇÃO: reduzir esses valores pode fazer o SEI bloquear a conexão por uso indevido.
SIMULAR_HUMANO = True
PAUSA_ENTRE_PROCESSOS_MIN = 5.0   # segundos mínimos entre cada processo inspecionado
PAUSA_ENTRE_PROCESSOS_MAX = 9.0   # segundos máximos entre cada processo inspecionado
PAUSA_ENTRE_ACOES_MIN = 1.5       # segundos mínimos entre ações/cliques na tela
PAUSA_ENTRE_ACOES_MAX = 3.5       # segundos máximos entre ações/cliques na tela
DIGITACAO_CADENCIA_MIN = 0.08     # segundos por caractere (digitação humana: ~80ms/char)
DIGITACAO_CADENCIA_MAX = 0.18     # segundos máximos por caractere (variação natural)

# 6. Gerenciamento de Credenciais Locais (descartadas do Git)
CREDENCIAIS_FILE = BASE_DIR / "data" / "credenciais.config"
CREDENCIAIS_ROOT_FILE = BASE_DIR / "credenciais.config"
CREDENCIAIS_EXEMPLO = BASE_DIR / "credenciais.config.exemplo"

def obter_credenciais_salvas() -> dict:
    """
    Lê o arquivo local data/credenciais.config (ou credenciais.config na raiz)
    e retorna dicionário com 'usuario', 'senha' e 'orgao'.
    Se não existir, cria a partir do modelo credenciais.config.exemplo.
    """
    credenciais = {"usuario": "", "senha": "", "orgao": "UERJ"}
    
    arquivo_alvo = None
    if CREDENCIAIS_FILE.exists():
        arquivo_alvo = CREDENCIAIS_FILE
    elif CREDENCIAIS_ROOT_FILE.exists():
        arquivo_alvo = CREDENCIAIS_ROOT_FILE
    elif CREDENCIAIS_EXEMPLO.exists():
        # Inicializa data/credenciais.config a partir do modelo
        try:
            with open(CREDENCIAIS_EXEMPLO, "r", encoding="utf-8") as f_ex:
                modelo = f_ex.read()
            with open(CREDENCIAIS_FILE, "w", encoding="utf-8") as f_dst:
                f_dst.write(modelo)
            arquivo_alvo = CREDENCIAIS_FILE
        except Exception:
            pass

    if arquivo_alvo and arquivo_alvo.exists():
        try:
            with open(arquivo_alvo, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip().lower()
                        v = v.strip()
                        # Não carrega o placeholder 'xxxxxxxx' como credencial válida
                        if "xxxxxxxx" in v.lower():
                            continue
                        if k in credenciais:
                            credenciais[k] = v
        except Exception:
            pass
    return credenciais

def salvar_credenciais_locais(usuario: str, senha: str, orgao: str = "UERJ"):
    """
    Salva as credenciais do usuário em data/credenciais.config localmente.
    """
    try:
        conteudo = f"# Arquivo local de credenciais do SEI-RJ (Não commitado no Git)\nusuario={usuario}\nsenha={senha}\norgao={orgao}\n"
        with open(CREDENCIAIS_FILE, "w", encoding="utf-8") as f:
            f.write(conteudo)
    except Exception:
        pass

