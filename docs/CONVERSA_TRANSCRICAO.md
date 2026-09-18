# Transcrição da Conversa Original: Automação de Processos no SEI com Python

> **Fonte Original:** [Gemini Share - Automação de Processos no SEI com Python](https://share.gemini.google/tZYNons54wzX)  
> **Data:** 18 de setembro de 2026  
> **Modelo Utilizado na Conversa:** Gemini 3.8 Flash  

---

## Índice da Conversa

1. [Consulta 1: Viabilidade de automação no SEI com Python](#consulta-1-viabilidade-de-automação-no-sei-com-python)
2. [Consulta 2: Tratamento de processos sigilosos e autenticação](#consulta-2-tratamento-de-processos-sigilosos-e-autenticação)
3. [Consulta 3: Navegação na hierarquia de Iframes (Árvore e Histórico de Andamentos)](#consulta-3-navegação-na-hierarquia-de-iframes-árvore-e-histórico-de-andamentos)
4. [Consulta 4: Arquitetura, Regras de Negócio e Modularidade do Projeto](#consulta-4-arquitetura-regras-de-negócio-e-modularidade-do-projeto)
5. [Consulta 5: Escolha de Framework para Interface Gráfica (UI) e Protótipo](#consulta-5-escolha-de-framework-para-interface-gráfica-ui-e-protótipo)

---

### Consulta 1: Viabilidade de automação no SEI com Python

#### Pergunta do Usuário:
> *Existe alguma forma de usar python para fazer um programa que abra o sei e procure nas unidades que eu tenho acesso uma lista de processos para procurar se houve andamentos?*

#### Resposta do Assistente:

Sim, é perfeitamente viável automatizar essa rotina em Python. Como o SEI geralmente não disponibiliza APIs públicas abertas diretamente ao usuário final em muitas instalações públicas, a abordagem padrão mais eficiente é via automação de navegador (Web Scraping / RPA) ou chamadas de sessão via requests.

O fluxo clássico mais robusto utiliza **Selenium** ou **Playwright**.

#### Arquitetura da Solução

1. **Autenticação e Sessão:** O script realiza o login ou reutiliza cookies/sessão ativa de um perfil já autenticado (útil caso haja 2FA ou autenticação unificada como Gov.br).
2. **Iteração por Unidade:** No SEI, o topo da interface exibe o seletor/combo de unidades de lotação. O robô altera a unidade ativa via DOM/URL.
3. **Consulta de Processos:**
   - **Modo A (Pesquisa Rápida):** Inserir o número do processo no campo de busca global/pesquisa rápida do SEI.
   - **Modo B (Acesso Direto):** Navegar diretamente pela URL de visualização do processo caso você tenha o ID do procedimento.
4. **Extração e Comparação:**
   - Ler a árvore de documentos ou a tabela de histórico de andamentos (janela/aba "Consultar Andamento").
   - Comparar o último andamento ou hash do documento mais recente com um banco local (SQLite, JSON ou planilha).
   - Alertar caso a data/hora ou o texto da última tramitação seja diferente do registro anterior.

#### Exemplo Base com Selenium

```python
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

# Lista de unidades e processos para monitorar
PROCESSOS_ALVO = ["SEI-000000/000000/2026", "SEI-111111/222222/2026"]
UNIDADES = ["UNIDADE_A", "UNIDADE_B"]

driver = webdriver.Edge() # ou webdriver.Chrome()
driver.get("https://seu-portal-sei.gov.br")

# 1. Etapa de Login (insira credenciais ou pause para login manual)
# WebDriverWait(driver, 10).until(...)

def trocar_unidade(sigla_unidade):
    # O SEI costuma usar um <select id="selInfraUnidades"> ou link similar no topo
    select_elem = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "selInfraUnidades"))
    )
    select = Select(select_elem)
    select.select_by_visible_text(sigla_unidade)
    time.sleep(2)

def checar_andamento(numero_processo):
    # Localiza o campo de pesquisa rápida
    campo_busca = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "txtPesquisaRapida"))
    )
    campo_busca.clear()
    campo_busca.send_keys(numero_processo)
    driver.find_element(By.ID, "btnPesquisaRapida").click()
    
    # Entra no iframe principal do SEI se necessário (o SEI usa frames como 'ifrConteudoVisualizacao')
    driver.switch_to.default_content()
    WebDriverWait(driver, 10).until(
        EC.frame_to_be_available_and_switch_to_it("ifrVisualizacao")
    )
    
    # Captura itens da árvore ou clica no ícone de "Consultar Andamento"
    ultimo_registro = driver.find_element(By.CSS_SELECTOR, ".infraArvoreNoSelecionado, .arvoreItem").text
    return ultimo_registro

# Execução do loop
for unidade in UNIDADES:
    trocar_unidade(unidade)
    for processo in PROCESSOS_ALVO:
        ultimo_status = checar_andamento(processo)
        print(f"[{unidade}] Processo {processo} -> Último nó: {ultimo_status}")

driver.quit()
```

#### Cuidados Técnicos Importantes no SEI

- **Estrutura de iframes:** O SEI faz uso intenso de frames internos (`ifrVisualizacao`, `ifrArvore`, `ifrConteudoVisualizacao`). Sempre utilize `driver.switch_to.frame()` para interagir com elementos internos da árvore e do conteúdo.
- **Persistência de Estado:** Salve o último andamento identificado em um arquivo local (`andamentos.json` ou SQLite). Assim, a cada execução, o script compara apenas `novo_andamento != ultimo_andamento_salvo` e avisa apenas sobre o que realmente mudou.
- **Perfis Persistentes:** Para não precisar preencher usuário/senha toda vez, inicie o navegador apontando para o diretório de dados do usuário (`user-data-dir`), mantendo a sessão aberta.

---

### Consulta 2: Tratamento de processos sigilosos e autenticação

#### Pergunta do Usuário:
> *Eu tenho uma lista de processos sigilosos, que eu preciso monitorar, o programa conseguiria digitar login e senha nas janelas de cada processo?*

#### Resposta do Assistente:

Sim, o Python consegue lidar com isso perfeitamente.

No SEI, quando você clica em um processo com nível de acesso sigiloso (ou com credencial de acesso restrita à sua credencial pessoal), o sistema costuma abrir uma janela/modal pop-up exigindo a confirmação das credenciais (geralmente usuário, senha e às vezes órgão).

Para automatizar essa etapa com Selenium, você precisa tratar dois comportamentos fundamentais do SEI: **troca de contexto (janela ou iframe)** e **esperas explícitas**.

#### Como o Selenium lida com a janela de credencial

Dependendo da versão ou customização do SEI no seu órgão, a tela de credencial pode surgir de duas formas:
1. **Janela Pop-up (`window.open`):** O navegador cria uma nova aba/janela separada. O Selenium precisa alternar o foco (`switch_to.window`).
2. **Modal/Iframe interno:** O pop-up aparece dentro da própria página em um iframe ou div sobreposto. O Selenium precisa alternar o frame (`switch_to.frame`).

#### Exemplo de Implementação

```python
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# IMPORTANTE: Nunca deixe a senha exposta no código.
# Use variáveis de ambiente ou getpass:
USUARIO_SEI = os.getenv("SEI_USER", "seu_usuario")
SENHA_SEI = os.getenv("SEI_PASSWORD", "sua_senha")

def abrir_e_autenticar_processo_sigiloso(driver, numero_processo):
    janela_principal = driver.current_window_handle

    # 1. Busca o processo no campo de pesquisa rápida
    driver.switch_to.default_content()
    campo_busca = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "txtPesquisaRapida"))
    )
    campo_busca.clear()
    campo_busca.send_keys(numero_processo)
    driver.find_element(By.ID, "btnPesquisaRapida").click()

    # 2. Caso abra em NOVA JANELA/POP-UP:
    # Aguarda o surgimento de uma nova janela além da principal
    try:
        WebDriverWait(driver, 5).until(lambda d: len(d.window_handles) > 1)
        for janela in driver.window_handles:
            if janela != janela_principal:
                driver.switch_to.window(janela)
                break
    except Exception:
        # Se não abriu nova janela, o diálogo pode ser um modal interno na mesma página
        pass

    # 3. Trata o formulário de credencial/senha
    try:
        # Verifica se o campo de senha do sigiloso está presente
        # No SEI costuma ser 'pwdSenha', 'txtSenha' ou seletor por tipo
        campo_senha = WebDriverWait(driver, 4).until(
            EC.presence_of_element_located((
                By.XPATH, 
                "//input[@type='password' or @id='pwdSenha' or @id='txtSenha']"
            ))
        )
        
        # Se houver campo de usuário na janela (alguns modais exigem usuário + senha)
        campos_usuario = driver.find_elements(
            By.XPATH, "//input[@id='txtUsuario' or @id='txtLogin']"
        )
        if campos_usuario and campos_usuario[0].is_displayed():
            campos_usuario[0].clear()
            campos_usuario[0].send_keys(USUARIO_SEI)

        # Preenche a senha
        campo_senha.clear()
        campo_senha.send_keys(SENHA_SEI)

        # Clica no botão de confirmação/liberação
        btn_confirmar = driver.find_element(
            By.XPATH, 
            "//button[@id='sbmAcessar' or @id='btnConfirmar' or @type='submit' or contains(text(), 'Confirmar') or contains(text(), 'Acessar')]"
        )
        btn_confirmar.click()

        print(f"Credencial confirmada para o processo: {numero_processo}")

    except Exception:
        # Se não pediu senha, o processo já estava aberto ou não demandou credencial nesta sessão
        pass

    # 4. Retorna o foco para o fluxo de leitura
    # (Se tiver aberto nova janela e você precisar ler nela, mantenha o foco;
    # se o SEI fechar o pop-up e recarregar a janela principal, volte para ela):
    if len(driver.window_handles) == 1:
        driver.switch_to.window(janela_principal)
```

#### Recomendações de Boas Práticas e Segurança

- **Gerenciamento de Senha:** Como processos sigilosos envolvem informações sensíveis e responsabilidade funcional, evite salvar a senha em texto puro no script. Use `getpass.getpass("Digite sua senha para iniciar: ")` no início da execução ou carregue de uma variável de ambiente segura.
- **Persistência de Credencial na Sessão:** No SEI, depois que você autentica a credencial de um processo sigiloso dentro da mesma sessão ativa do navegador, a consulta subsequente ou recarregamento daquele mesmo processo frequentemente dispensa nova digitação de senha até o logout ou expiração da sessão.
- **Detecção de Bloqueio por Tentativas:** Certifique-se de validar se o login inicial foi bem-sucedido antes de iterar pela lista. Se a senha estiver incorreta e o script rodar em lote para 20 processos, ele pode bloquear sua credencial no sistema por excesso de tentativas inválidas.

---

### Consulta 3: Navegação na hierarquia de Iframes (Árvore e Histórico de Andamentos)

#### Pergunta do Usuário:
> *Mostre como estruturar a navegação dentro dos iframes do SEI após digitar a credencial para ler a árvore e o último andamento.*

#### Resposta do Assistente:

Para ler a árvore de documentos e os andamentos de um processo no SEI, a regra de ouro é entender a arquitetura de frames aninhados do sistema.

Ao abrir qualquer processo (inclusive os sigilosos logo após confirmar a credencial), a página carrega uma hierarquia com frames dedicados:
- **`ifrVisualizacao`**: O frame principal onde o processo é renderizado.
- **`ifrArvore`** (dentro do `ifrVisualizacao`): Onde fica a árvore de documentos (lado esquerdo).
- **`ifrConteudoVisualizacao`** (dentro do `ifrVisualizacao`): Onde os documentos, despachos e telas de histórico/andamento são exibidos (lado direito).

#### Estrutura Completa de Navegação

```python
import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

USUARIO_SEI = os.getenv("SEI_USER", "seu_usuario")
SENHA_SEI = os.getenv("SEI_PASSWORD", "sua_senha")

def lidar_com_credencial_sigiloso(driver):
    """Detecta pop-up/modal de processo sigiloso e insere credenciais se solicitado."""
    # Se abriu uma nova janela pop-up, muda o foco
    if len(driver.window_handles) > 1:
        driver.switch_to.window(driver.window_handles[-1])

    try:
        # Aguarda seletor de senha curto para não atrasar se o processo não for sigiloso
        campo_senha = WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((
                By.XPATH, "//input[@type='password' or @id='pwdSenha' or @id='txtSenha']"
            ))
        )
        
        # Preenche login se solicitado
        campos_user = driver.find_elements(By.XPATH, "//input[@id='txtUsuario' or @id='txtLogin']")
        if campos_user and campos_user[0].is_displayed():
            campos_user[0].clear()
            campos_user[0].send_keys(USUARIO_SEI)

        campo_senha.clear()
        campo_senha.send_keys(SENHA_SEI)

        btn_ok = driver.find_element(
            By.XPATH, 
            "//button[@id='sbmAcessar' or @id='btnConfirmar' or @type='submit' or contains(text(), 'Confirmar') or contains(text(), 'Acessar')]"
        )
        btn_ok.click()
        time.sleep(1.5)
    except Exception:
        # Se não encontrou campo de senha, o acesso já está liberado
        pass

    # Garante que voltou para a janela de trabalho
    if len(driver.window_handles) > 1:
        driver.switch_to.window(driver.window_handles[0])


def extrair_dados_processo(driver, numero_processo):
    """
    Navega pelos iframes internos do SEI e extrai:
    1. O último nó/documento da árvore à esquerda.
    2. O último andamento registrado no histórico oficial.
    """
    dados = {
        "processo": numero_processo,
        "ultimo_documento_arvore": None,
        "ultimo_andamento_historico": None
    }

    # 1. Busca o processo no topo da página
    driver.switch_to.default_content()
    campo_busca = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "txtPesquisaRapida"))
    )
    campo_busca.clear()
    campo_busca.send_keys(numero_processo)
    driver.find_element(By.ID, "btnPesquisaRapida").click()

    # Trata tela de autenticação caso seja sigiloso
    lidar_com_credencial_sigiloso(driver)

    # -------------------------------------------------------------
    # PASSO A: Entrar no iframe pai de visualização
    # -------------------------------------------------------------
    driver.switch_to.default_content()
    WebDriverWait(driver, 10).until(
        EC.frame_to_be_available_and_switch_to_it((By.ID, "ifrVisualizacao"))
    )

    # -------------------------------------------------------------
    # PASSO B: Entrar no iframe da Árvore (ifrArvore)
    # -------------------------------------------------------------
    WebDriverWait(driver, 10).until(
        EC.frame_to_be_available_and_switch_to_it((By.ID, "ifrArvore"))
    )

    # Coleta todos os itens visíveis da árvore
    nos_arvore = WebDriverWait(driver, 10).until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a.infraArvoreNo, span.infraArvoreNo"))
    )
    if nos_arvore:
        # O último nó geralmente é o documento/termo mais recente juntado
        dados["ultimo_documento_arvore"] = nos_arvore[-1].text.strip()

    # Clica no ícone "Consultar Andamento" localizado na barra superior da árvore
    try:
        btn_historico = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((
                By.XPATH, 
                "//a[contains(@href, 'andamento_consultar') or @title='Consultar Andamento' or contains(@title, 'Andamento')]"
            ))
        )
        btn_historico.click()
    except Exception:
        print("Botão de histórico direto não localizado via barra da árvore.")

    # -------------------------------------------------------------
    # PASSO C: Sair da Árvore e ir para o Painel de Conteúdo
    # -------------------------------------------------------------
    # Volta um nível para o ifrVisualizacao
    driver.switch_to.parent_frame()

    # Entra no iframe da direita onde o histórico carregou
    WebDriverWait(driver, 10).until(
        EC.frame_to_be_available_and_switch_to_it((By.ID, "ifrConteudoVisualizacao"))
    )

    # Extrai o primeiro registro da tabela de andamentos
    # No SEI, a tabela de histórico tem a classe .infraTable e os andamentos mais recentes ficam no topo
    try:
        primeira_linha = WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((
                By.XPATH, 
                "//table[contains(@class, 'infraTable')]//tbody/tr[2] | //table[@id='tblHistorico']//tr[2]"
            ))
        )
        dados["ultimo_andamento_historico"] = " | ".join([
            col.text.strip() for col in primeira_linha.find_elements(By.TAG_NAME, "td") if col.text.strip()
        ])
    except Exception:
        dados["ultimo_andamento_historico"] = "Não foi possível carregar a tabela de histórico."

    # Volta o foco para o contexto raiz para a próxima busca
    driver.switch_to.default_content()
    return dados
```

#### Mapa Mental dos `switch_to`

```plaintext
[ default_content ] (Página raiz / barra de pesquisa rápida)
       │
       ▼
   switch_to.frame("ifrVisualizacao")
       ├──► switch_to.frame("ifrArvore") ----------> Ler nós e clicar no ícone de andamento
       │           │
       │           ▼
       │     switch_to.parent_frame() (Volta para ifrVisualizacao)
       │           │
       └──► switch_to.frame("ifrConteudoVisualizacao") -> Ler tabela de andamentos
                   │
                   ▼
             switch_to.default_content() (Volta para a raiz para buscar o próximo processo)
```

#### Pontos de Atenção na Prática

1. **`switch_to.parent_frame()`:** Sempre utilize `parent_frame()` ao sair de `ifrArvore` antes de tentar entrar em `ifrConteudoVisualizacao`, pois eles são irmãos dentro do `ifrVisualizacao`. Se tentar ir direto de um para o outro sem subir um nível, o Selenium lançará `NoSuchFrameException`.
2. **Tempo de renderização do Histórico:** A tela de "Consultar Andamento" costuma ser pesada em processos volumosos. Usar `WebDriverWait` na primeira linha da tabela (`//table[contains(@class, 'infraTable')]//tr[2]`) garante que o script só avance quando o servidor do SEI tiver terminado de montar a listagem.

---

### Consulta 4: Arquitetura, Regras de Negócio e Modularidade do Projeto

#### Pergunta do Usuário:
> *Antes de testar o código eu gostaria de ajuda para criar o projeto do programa com as regras de negócio, dividas por funções ou módulos específico que o programa rodaria. A documentação com os objetivos do programa tem que ser estruturada de uma forma fácil de ser entendida pra somente depois começarmos a pensar nos códigos de forma otimizada. Vou dar alguns detalhes do que preciso que seja feito e depois vamos aperfeiçoando a documentação. Eu preciso que a cara do programa ou a parte de entrada dos dados pelo usuário seja amigável. Eu preciso que na janela inicial do programa o usuário possa escolher entre 4 unidades possíveis. Ao escolher a unidade o usuário deverá escolher qual tipo de monitoramento ele deseja. Esses tipos de monitoramento, por exemplo, monitorar atas criadas ou monitorar andamento do processo ou monitorar recomendações de PAD, etc serão criadas a medida da necessidade então o projeto precisa prever que o código seja criado desde o início para ser modular ou seja um código pensado para aceitar novos módulos de tipos de monitoramento, os processos a serem monitorados em casa módulo podem vir de uma planilha de Excel ou Google planilhas dentro de uma pasta física ou de uma planilha Google ou de marcações dentro do próprio sei (exemplo processos tipo correição ou processos marcados com tag "secretário: fulano". Os dados exportados devem ir para planilhas específicas cujos nomes devem devem ser iguais aos módulos escolhidos.*

#### Resposta do Assistente:

Aqui está uma proposta de **Documento de Arquitetura e Regras de Negócio** para o seu projeto. Ele foi estruturado para ser modular, desacoplado e escalável, garantindo que novas unidades, novas fontes de dados ou novos tipos de monitoramento possam ser adicionados sem quebrar o núcleo do sistema.

#### Visão Geral do Sistema

O sistema é uma ferramenta de automação e monitoramento processual no SEI, orientada a tarefas modulares. O fluxo central obedece ao seguinte ciclo:

```plaintext
[ Interface do Usuário ] 
       │ (Unidade + Módulo + Parâmetros)
       ▼
[ Gerenciador de Fontes ] ──► [ Módulo de Monitoramento ] ──► [ Driver SEI ]
                                         │
                                         ▼
                               [ Gerenciador de Exportação ]
```

#### Módulos e Responsabilidades (6 Camadas)

1. **Módulo de Interface do Usuário (`ui/`):**
   - Responsável pela coleta amigável de parâmetros e controle de execução.
   - Tela Inicial: Seletor de Unidade (drop-down contendo as 4 unidades iniciais pré-configuradas), Seletor de Tipo de Monitoramento (carregado dinamicamente com base nos módulos instalados), Campo para credenciais/senha (caso haja processos sigilosos), Botão de Iniciar e painel de log/progresso em tempo real.
2. **Módulo Orquestrador e Contrato Base (`core/`):**
   - Define as regras que todo novo monitoramento deve respeitar.
   - Classe Abstrata / Interface (`BaseMonitor`):
     - `carregar_alvos()`: Como este monitor obtém a lista de processos.
     - `executar_inspecao(driver, processo)`: Lógica específica do que buscar no SEI para cada processo.
     - `estruturar_dados(resultado)`: Converte o resultado bruto do scraping em formato tabular.
     - `exportar()`: Grava o resultado na saída correspondente.
3. **Módulo Provedor de Dados / Input (`inputs/`):**
   - Isola a origem da lista de processos:
     - Excel / CSV Local (lê pastas de trabalho em diretório local).
     - Google Planilhas (conecta via API do Google Sheets).
     - Coletor Interno SEI (navega na unidade ativa do SEI e raspa processos com base em filtros/tags como `secretário: Fulano` ou tipo `Correição`).
4. **Motor de Automação do SEI (`rpa_sei/`):**
   - Isola a navegação, seletores e tratamento de frames, sem regras de negócio específicas:
     - `autenticar_sessao()`
     - `trocar_unidade(sigla)`
     - `abrir_processo(numero)` (trata credenciais de processos sigilosos)
     - `extrair_arvore()`
     - `extrair_historico()`
5. **Módulos Específicos de Monitoramento (`monitors/`):**
   - Plug-and-play. Novos monitores são criados apenas adicionando uma nova classe nesta pasta.
   - Exemplos:
     - `MonitorAtas`: Verifica documentos do tipo "Ata" gerados após data X -> Gera `MonitorAtas.xlsx`.
     - `MonitorAndamentoGeral`: Compara última linha do histórico -> Gera `MonitorAndamentoGeral.xlsx`.
     - `MonitorRecomendacoesPAD`: Busca termos em despachos de PAD -> Gera `MonitorRecomendacoesPAD.xlsx`.
6. **Módulo Exportador (`exporters/`):**
   - Garante a padronização de nomenclatura e gravação dos dados. O nome do arquivo/aba é vinculado automaticamente ao identificador do módulo executado (ex: `MonitorRecomendacoesPAD.xlsx`). Trata append e update sem sobrescrever histórico anterior.

#### Estrutura de Pastas Sugerida

```plaintext
projeto_monitor_sei/
│
├── config/
│   └── settings.py          # Unidades pré-definidas, credenciais, timeouts
│
├── core/
│   ├── base_monitor.py      # Modelo que todo novo módulo deve herdar
│   └── orchestrator.py      # Executa a esteira (Input -> SEI -> Export)
│
├── rpa_sei/
│   ├── driver.py            # Inicialização e persistência do navegador
│   └── sei_actions.py       # Ações atômicas (troca unidade, busca, frames)
│
├── inputs/
│   ├── excel_reader.py      # Leitor local
│   ├── gsheets_reader.py    # Leitor Google Planilhas
│   └── sei_tag_crawler.py   # Coletor via marcadores/tipos do próprio SEI
│
├── monitors/                # <-- NOVOS MÓDULOS ENTRAM AQUI
│   ├── monitor_atas.py
│   ├── monitor_andamentos.py
│   └── monitor_pad.py
│
├── exporters/
│   ├── excel_exporter.py    # Grava na planilha local com nome do módulo
│   └── gsheets_exporter.py  # Grava no Google Sheets na aba do módulo
│
├── ui/
│   └── app.py               # Interface gráfica (ex: CustomTkinter / Flet / Streamlit)
│
└── main.py                  # Ponto de entrada do executável/script
```

#### Regras de Negócio e Comportamentos-Chave

- **Desacoplamento de Fontes:** O módulo de monitoramento recebe apenas uma lista limpa de strings com os números dos processos.
- **Resiliência a Erros Individuais:** Se um processo sigiloso falhar por falta de permissão ou não for encontrado, o robô registra a pendência no log e passa imediatamente para o próximo processo, sem abortar a esteira.
- **Persistência de Unidade:** O robô só troca de unidade uma vez por lote.
- **Convenção sobre Configuração:** O nome da saída (planilha/aba) é inferido a partir da classe do monitor, eliminando o risco de salvar em arquivos trocados.

---

### Consulta 5: Escolha de Framework para Interface Gráfica (UI) e Protótipo

#### Pergunta do Usuário:
> *Quais são as melhores opções de bibliotecas em Python para criar a interface amigável desse programa e qual se encaixa melhor nesse projeto?*

#### Resposta do Assistente:

Para este projeto de automação no SEI, a escolha da interface deve considerar três fatores críticos: **facilidade de empacotar como executável (.exe)**, **suporte nativo a execução assíncrona/threads** (para o robô não congelar a janela enquanto raspa o SEI) e uma **aparência moderna sem complexidade excessiva de código**.

#### Comparativo de Bibliotecas

| Biblioteca | Estilo Visual | Facilidade de Código | Empacotamento (.exe) | Bloqueio de Thread (Robô rodando) |
| :--- | :--- | :--- | :--- | :--- |
| **CustomTkinter** | Moderno / Nativo Dark & Light | Alta | Muito simples (PyInstaller) | Requer `threading.Thread` simples |
| **Flet** (Flutter) | Extremamente moderno / Web/App | Média | Simples | Suporta assíncrono nativo |
| **PyQt6 / PySide6** | Corporativo avançado | Baixa / Complexa | Média a Complexa | Requer `QThread` / Slots & Signals |
| **Streamlit** | Painel Web / Dashboard | Altíssima | Ruim para distribuição local | Reexecuta o script a cada clique |

#### A Escolha Recomendada: CustomTkinter

1. **Janela Desktop Pura:** Não abre abas extras no navegador (o Selenium já abrirá o navegador do SEI; ter a UI também no navegador causaria confusão de janelas).
2. **Integração com Threads:** Isolar o Selenium em uma thread secundária enquanto a UI exibe uma barra de progresso ou logs de execução em tempo real é feito em poucas linhas com a biblioteca padrão `threading`.
3. **Distribuição Sem Atrito:** Permite compilar a ferramenta em um executável único com `pyinstaller --noconsole --onefile main.py` para rodar diretamente na máquina sem exigir instalação de interpretadores para outros colegas de equipe.

#### Exemplo do Protótipo Funcional da Janela com CustomTkinter

```python
import customtkinter as ctk
import threading
import time

# Configuração de tema
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class AppMonitorSEI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Painel de Monitoramento SEI")
        self.geometry("520x620")
        self.resizable(False, False)

        # 1. Cabeçalho
        self.lbl_titulo = ctk.CTkLabel(
            self, text="Automação & Monitoramento SEI", 
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.lbl_titulo.pack(pady=(20, 10))

        # 2. Seletor de Unidade (As 4 unidades do órgão)
        self.lbl_unidade = ctk.CTkLabel(self, text="Selecione a Unidade:")
        self.lbl_unidade.pack(anchor="w", padx=40, pady=(10, 0))
        
        self.combo_unidade = ctk.CTkComboBox(
            self, values=["UNIDADE-PAD", "UNIDADE-CORREICAO", "UNIDADE-GABINETE", "UNIDADE-AUDITORIA"],
            width=440
        )
        self.combo_unidade.pack(padx=40, pady=(5, 10))

        # 3. Seletor Dinâmico de Módulo
        self.lbl_modulo = ctk.CTkLabel(self, text="Tipo de Monitoramento:")
        self.lbl_modulo.pack(anchor="w", padx=40, pady=(5, 0))

        self.modulos_disponiveis = [
            "Monitoramento de Atas Criadas",
            "Monitoramento de Andamentos Gerais",
            "Monitoramento de Recomendações de PAD"
        ]
        self.combo_modulo = ctk.CTkComboBox(self, values=self.modulos_disponiveis, width=440)
        self.combo_modulo.pack(padx=40, pady=(5, 10))

        # 4. Campo Opcional para Senha de Processos Sigilosos
        self.lbl_senha = ctk.CTkLabel(self, text="Senha de Acesso (para processos sigilosos):")
        self.lbl_senha.pack(anchor="w", padx=40, pady=(5, 0))

        self.txt_senha = ctk.CTkEntry(self, placeholder_text="Digite se houver sigilosos", show="*", width=440)
        self.txt_senha.pack(padx=40, pady=(5, 15))

        # 5. Botão de Disparo
        self.btn_executar = ctk.CTkButton(
            self, text="Iniciar Monitoramento", 
            command=self.iniciar_thread_execucao, 
            height=40, width=440, font=ctk.CTkFont(weight="bold")
        )
        self.btn_executar.pack(padx=40, pady=(10, 15))

        # 6. Painel de Log em Tempo Real
        self.lbl_log = ctk.CTkLabel(self, text="Progresso da Execução:")
        self.lbl_log.pack(anchor="w", padx=40, pady=(5, 0))

        self.caixa_logs = ctk.CTkTextbox(self, width=440, height=180)
        self.caixa_logs.pack(padx=40, pady=(5, 20))

    def log(self, mensagem):
        """Atualiza a caixa de texto na interface."""
        self.caixa_logs.insert("end", f"> {mensagem}\n")
        self.caixa_logs.see("end")

    def iniciar_thread_execucao(self):
        """Inicia a esteira em thread separada para não travar a janela."""
        self.btn_executar.configure(state="disabled")
        thread = threading.Thread(target=self.rotina_automacao, daemon=True)
        thread.start()

    def rotina_automacao(self):
        unidade = self.combo_unidade.get()
        modulo = self.combo_modulo.get()
        
        self.log(f"Iniciando: {modulo}")
        self.log(f"Unidade selecionada: {unidade}")
        
        # Simulação da orquestração com o robô
        time.sleep(1.5)
        self.log("Conectando ao SEI...")
        time.sleep(2)
        self.log("Varrendo processos alvos...")
        time.sleep(2)
        self.log(f"Exportando resultados para: {modulo.replace(' ', '_')}.xlsx")
        self.log("Execução finalizada com sucesso!")
        
        self.btn_executar.configure(state="normal")

if __name__ == "__main__":
    app = AppMonitorSEI()
    app.mainloop()
```
