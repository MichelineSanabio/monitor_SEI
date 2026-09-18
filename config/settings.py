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
    "campo_senha_sigiloso": "//input[@type='password' or @id='pwdSenha' or @id='txtSenha']",
    "campo_usuario_sigiloso": "//input[@id='txtUsuario' or @id='txtLogin']",
    "btn_confirmar_sigiloso": "//button[@id='sbmAcessar' or @id='btnConfirmar' or @type='submit' or contains(text(), 'Confirmar') or contains(text(), 'Acessar')]",
    
    # Iframes
    "iframe_visualizacao": "ifrVisualizacao",
    "iframe_arvore": "ifrArvore",
    "iframe_conteudo": "ifrConteudoVisualizacao",
    
    # Nós da árvore de documentos
    "nos_arvore": "a.infraArvoreNo, span.infraArvoreNo",
    "btn_consultar_andamento": "//a[contains(@href, 'andamento_consultar') or @title='Consultar Andamento' or contains(@title, 'Andamento')]",
    
    # Tabela de histórico de andamentos
    "primeira_linha_historico": "//table[contains(@class, 'infraTable')]//tbody/tr[2] | //table[@id='tblHistorico']//tr[2]"
}
