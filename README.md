# Monitor SEI 📂🤖

Automação em Python (RPA) para consulta, extração e acompanhamento automatizado de processos no **Sistema Eletrônico de Informações (SEI)**, com suporte a processos sigilosos, arquitetura modular plug-and-play e interface gráfica moderna.

---

## 📌 Documentação do Projeto

Toda a concepção, requisitos de negócio e especificações técnicas foram consolidados na pasta [`docs/`](file:///c:/Users/Misha/Documents/Github/monitor_SEI/docs):

1. 📄 **[Documentação Técnica e de Arquitetura](file:///c:/Users/Misha/Documents/Github/monitor_SEI/docs/DOCUMENTACAO_MONITOR_SEI.md)**:
   - Visão geral e objetivos do sistema;
   - Regras de negócio essenciais (4 unidades, seleção dinâmica de monitoramento, processos sigilosos, fontes desacopladas, convenção de exportação com nome do módulo);
   - Engenharia reversa do SEI e mapa mental de navegação nos *iframes* (`ifrVisualizacao`, `ifrArvore`, `ifrConteudoVisualizacao`);
   - Especificação das 6 camadas do sistema;
   - Estrutura completa de diretórios e contratos de código;
   - Segurança de credenciais e empacotamento em `.exe` com PyInstaller.

2. 💬 **[Transcrição da Conversa Original](file:///c:/Users/Misha/Documents/Github/monitor_SEI/docs/CONVERSA_TRANSCRICAO.md)**:
   - Cópia integral, estruturada e organizada da conversa de concepção realizada no Gemini (18/09/2026);
   - Contém todos os códigos protótipos, seletores identificados, fluxos e orientações arquiteturais discutidas.

---

## 🚀 Principais Características

- **Interface Amigável (CustomTkinter):** Permite ao usuário selecionar entre 4 unidades do órgão, escolher dinamicamente o tipo de monitoramento, inserir senha para sigilosos e visualizar o log em tempo real sem travamento de tela (multithreading).
- **Tratamento de Processos Sigilosos:** Automação de janelas pop-up e formulários de autenticação de credencial no SEI com controle de segurança contra bloqueio de conta.
- **Hierarquia de Iframes Blindada:** Transições controladas entre `ifrVisualizacao`, `ifrArvore` e `ifrConteudoVisualizacao` utilizando `WebDriverWait` e `parent_frame()`.
- **Arquitetura Plug-and-Play:** Novos tipos de monitoramento (como atas criadas, tramitações gerais ou recomendações de PAD) são adicionados estendendo a classe abstrata `BaseMonitor`.
- **Desacoplamento de Fontes:** Suporte para carregamento de processos via Excel (.xlsx), Google Planilhas ou raspagem interna de tags/marcadores do próprio SEI.
- **Convenção de Exportação:** Gera automaticamente planilhas `.xlsx` com o nome exato do módulo executado (`MonitorAtas.xlsx`, `MonitorAndamentos.xlsx`, etc.).

---

## 🛠️ Tecnologias Utilizadas

- **Linguagem:** Python 3.10+
- **Automação RPA / Navegação:** Selenium WebDriver
- **Interface Gráfica:** CustomTkinter
- **Manipulação de Dados:** Pandas / OpenPyXL
- **Versionamento:** Git & GitHub

---

## 📦 Estrutura do Projeto

```plaintext
monitor_SEI/
├── docs/
│   ├── CONVERSA_TRANSCRICAO.md        # Transcrição da conversa original
│   └── DOCUMENTACAO_MONITOR_SEI.md    # Especificação técnica detalhada
├── config/                            # Configurações de ambiente e constantes
├── core/                              # Contrato BaseMonitor e Orchestrator
├── rpa_sei/                           # Automação Selenium do SEI e iframes
├── inputs/                            # Leitores de planilhas locais, GSheets e tags
├── monitors/                          # Módulos especializados plug-and-play
├── exporters/                         # Exportação em Excel e Google Sheets
├── ui/                                # Interface visual CustomTkinter
├── requirements.txt                   # Dependências Python
└── README.md                          # Este documento
```

---

## ⚙️ Instalação e Execução

1. Clone o repositório:
   ```bash
   git clone https://github.com/ChrysthianChrisley/monitor_SEI.git
   cd monitor_SEI
   ```

2. Crie e ative um ambiente virtual (recomendado):
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure suas credenciais de acesso local (opcional, para não precisar digitar a cada execução):
   - Copie o arquivo modelo `credenciais.config.exemplo` para `data/credenciais.config`:
     ```bash
     copy credenciais.config.exemplo data\credenciais.config
     ```
   - Abra `data/credenciais.config` e insira seu usuário e senha:
     ```ini
     # Arquivo local de credenciais do SEI-RJ (Não commitado no Git)
     usuario=brpersoncpf=05089752630
     senha=SuaSenhaAqui@123
     orgao=UERJ
     ```
   > 🔒 **Nota de Segurança:** O arquivo `credenciais.config` está incluído no `.gitignore` e **nunca** será enviado para o repositório remoto.

5. Execute o aplicativo:
   ```bash
   python main.py
   # Ou execute pelo script:
   executar.bat
   ```

---

## 🤝 Contribuição

Contribuições são sempre bem-vindas!
1. Faça um fork do repositório
2. Crie uma branch para sua feature (`git checkout -b feature/minha-feature`)
3. Faça commit das suas alterações (`git commit -m 'feat: minha nova feature'`)
4. Envie para o branch (`git push origin feature/minha-feature`)
5. Abra um Pull Request

---

## 📄 Licença

Distribuído sob a licença MIT.

---

Desenvolvido por [Micheline Sanabio](https://github.com/MichelineSanabio).
