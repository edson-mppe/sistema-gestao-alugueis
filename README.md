# 🏢 Sistema de Gestão de Aluguéis

Sistema web desenvolvido em Streamlit para gerenciar reservas de apartamentos de aluguel, integrando calendários de múltiplas plataformas (OTAs) e Google Sheets.

## 📋 Funcionalidades

- **Sincronização Automática**: Importa calendários de Booking, Airbnb e outras OTAs via iCal
- **Consolidação de Dados**: Mescla reservas de diferentes fontes em uma única visualização
- **Gráfico de Gantt Interativo**: Visualização temporal das ocupações com:
  - Cores por origem da reserva (Booking, Airbnb, Direto)
  - Marcação de feriados brasileiros
  - Linha "Agora" indicando o momento atual
  - Fundo alternado (fins de semana e feriados destacados)
- **Verificação de Disponibilidade**: Consulta rápida de apartamentos livres em período específico
- **Detecção de Inconsistências**: Identifica conflitos e sobreposições de reservas
- **Integração Google Sheets**: Salva e lê dados consolidados da planilha

## 🛠️ Tecnologias

- **Python 3.8+**
- **Streamlit**: Interface web
- **Plotly**: Gráficos interativos
- **Pandas**: Manipulação de dados
- **gspread**: API Google Sheets
- **icalendar**: Leitura de calendários .ics
- **holidays**: Feriados brasileiros

## 📦 Instalação

### 1. Clone o repositório

```bash
git clone https://github.com/seu-usuario/sistema-gestao-alugueis.git
cd sistema-gestao-alugueis
```

### 2. Crie um ambiente virtual

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

### 4. Configure as credenciais

#### Google Cloud Credentials

1. Acesse o [Google Cloud Console](https://console.cloud.google.com/)
2. Crie um novo projeto ou selecione um existente
3. Ative a **Google Sheets API**
4. Crie credenciais:
   - **Service Account** (recomendado para produção)
   - **OAuth 2.0** (para desenvolvimento local)
5. Baixe o arquivo JSON de credenciais

#### Streamlit Secrets

1. Copie o arquivo de exemplo:
   ```bash
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   ```

2. Edite `.streamlit/secrets.toml` e preencha:
   - Credenciais do Google (cole o conteúdo do JSON)
   - ID da sua planilha Google Sheets
   - Mapeamento de apartamentos para abas

### 5. Configure a planilha Google Sheets

Sua planilha deve ter:
- Uma aba para cada apartamento com colunas: `Início`, `Fim`, `Quem`, `Origem`, `Status`
- Uma aba `Reservas Consolidadas` (será criada automaticamente)
- Uma aba `Inconsistências` (opcional, para logs de conflitos)

## 🚀 Como Usar

### Executar localmente

```bash
streamlit run app.py
```

O aplicativo abrirá em `http://localhost:8501`

### Fluxo de uso

1. **Sincronizar Dados**: Clique em "🔄 Sincronizar Dados Agora" na barra lateral
   - Baixa calendários das OTAs
   - Mescla com dados do Google Sheets
   - Atualiza a planilha consolidada

2. **Visualizar Ocupação**: O gráfico de Gantt mostra todas as reservas
   - Filtre apartamentos específicos usando o multiselect
   - Navegue pelo tempo usando o range slider

3. **Verificar Disponibilidade**:
   - Selecione datas de Check-in e Check-out
   - Clique em "Verificar Disponibilidade"
   - Veja quais apartamentos estão livres (destacados em amarelo no gráfico)

## 📁 Estrutura do Projeto

```
sistema_gestao_alugueis/
├── app.py                  # Aplicação principal Streamlit
├── requirements.txt        # Dependências Python
├── .gitignore             # Arquivos ignorados pelo Git
├── .streamlit/
│   ├── secrets.toml       # Credenciais (não versionado)
│   └── secrets.toml.example
├── src/
│   ├── config.py          # Configurações e constantes
│   ├── ui.py              # Componentes de interface
│   ├── logic.py           # Lógica de negócio e gráficos
│   ├── services.py        # Orquestração de serviços
│   ├── gsheets_api.py     # Integração Google Sheets
│   ├── data_loader.py     # Carregamento de calendários
│   └── utils.py           # Funções auxiliares
├── calendars/             # Arquivos .ics baixados (não versionado)
└── notebooks/             # Jupyter notebooks de desenvolvimento
    ├── 1_Baixar_calendarios_OTAs.ipynb
    ├── 2_Baixar_calendarios_google_sheet.ipynb
    ├── 3_juntar_calendarios.ipynb
    ├── 4_verificar_inconsistencias.ipynb
    ├── 5_atualizar_planilha_google.ipynb
    ├── 6_consolidar_reservas_apartamentos_google_sheet.ipynb
    └── 8_criar_grafico_html.ipynb
```

## 🔐 Segurança

⚠️ **IMPORTANTE**: Nunca commite arquivos com credenciais!

Arquivos protegidos pelo `.gitignore`:
- `credentials.json` / `credentials2.json`
- `.streamlit/secrets.toml`
- `token.json`

## 🤝 Contribuindo

Este é um projeto privado. Para contribuir:
1. Crie uma branch para sua feature
2. Faça commit das mudanças
3. Abra um Pull Request

## 📝 Licença

Projeto privado - Todos os direitos reservados

## 📧 Contato

Para dúvidas ou sugestões, entre em contato com o desenvolvedor.
