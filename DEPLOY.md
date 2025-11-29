# 🚀 Deploy no Streamlit Community Cloud

Guia passo a passo para publicar a aplicação no Streamlit Community Cloud.

## 📋 Pré-requisitos

- ✅ Repositório GitHub criado e atualizado
- ✅ Conta no GitHub (edson-mppe)
- ⚠️ Service Account do Google Cloud (necessário configurar)

## 🔧 Preparação

### 1. Service Account do Google Cloud

Se ainda não tiver, crie um Service Account:

1. Acesse [Google Cloud Console](https://console.cloud.google.com/)
2. Vá em **IAM & Admin** → **Service Accounts**
3. Clique em **Create Service Account**
4. Preencha:
   - **Name**: `streamlit-app-service-account`
   - **Description**: `Service account para app Streamlit`
5. Clique em **Create and Continue**
6. **Grant permissions**: Adicione o papel **Editor** (ou apenas Google Sheets API)
7. Clique em **Done**
8. Na lista de Service Accounts, clique nos 3 pontos → **Manage keys**
9. **Add Key** → **Create new key** → **JSON**
10. Salve o arquivo JSON (você precisará do conteúdo dele)

### 2. Habilitar Google Sheets API

1. No Google Cloud Console, vá em **APIs & Services** → **Library**
2. Procure por "Google Sheets API"
3. Clique em **Enable**

### 3. Compartilhar a Planilha com o Service Account

1. Abra sua planilha do Google Sheets
2. Clique em **Share**
3. Adicione o email do Service Account (algo como `streamlit-app-service-account@seu-projeto.iam.gserviceaccount.com`)
4. Dê permissão de **Editor**

## 🌐 Deploy no Streamlit Cloud

### Passo 1: Acessar Streamlit Community Cloud

1. Acesse: [https://share.streamlit.io/](https://share.streamlit.io/)
2. Clique em **Sign in with GitHub**
3. Autorize o Streamlit a acessar sua conta GitHub

### Passo 2: Criar Novo App

1. Clique em **New app** (botão no canto superior direito)
2. Preencha:
   - **Repository**: `edson-mppe/sistema-gestao-alugueis`
   - **Branch**: `master`
   - **Main file path**: `app.py`
3. **Não clique em Deploy ainda!** Primeiro configure os secrets.

### Passo 3: Configurar Secrets

1. Clique em **Advanced settings**
2. Na seção **Secrets**, cole o seguinte (substitua com seus valores reais):

```toml
[gcp_service_account]
type = "service_account"
project_id = "seu-projeto-id-aqui"
private_key_id = "sua-private-key-id-aqui"
private_key = "-----BEGIN PRIVATE KEY-----\nSUA_CHAVE_PRIVADA_COMPLETA_AQUI\n-----END PRIVATE KEY-----\n"
client_email = "streamlit-app-service-account@seu-projeto.iam.gserviceaccount.com"
client_id = "seu-client-id-aqui"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/seu-service-account"
```

**Como preencher**: Abra o arquivo JSON do Service Account que você baixou e copie os valores correspondentes.

**⚠️ IMPORTANTE**: 
- A `private_key` deve incluir `\n` para quebras de linha
- Mantenha as aspas duplas
- Não compartilhe esses valores com ninguém!

### Passo 4: Deploy!

1. Clique em **Deploy**
2. Aguarde o build (2-5 minutos)
3. Acompanhe os logs para verificar se há erros

### Passo 5: Testar o App

1. Quando o deploy terminar, você verá a URL do app: `https://edson-mppe-sistema-gestao-alugueis.streamlit.app`
2. Acesse a URL
3. Teste:
   - Clique em "Sincronizar Dados Agora"
   - Verifique se o gráfico carrega
   - Teste a verificação de disponibilidade

## 🐛 Troubleshooting

### Erro: "No module named 'src'"

**Solução**: Verifique se a estrutura de pastas está correta no repositório.

### Erro: "Authentication failed"

**Solução**: 
1. Verifique se os secrets estão configurados corretamente
2. Confirme que a planilha foi compartilhada com o Service Account
3. Verifique se a Google Sheets API está habilitada

### Erro: "App is sleeping"

**Solução**: Apps no plano gratuito "dormem" após inatividade. Basta acessar a URL novamente que o app reinicia automaticamente.

### Erro: "Memory limit exceeded"

**Solução**: 
1. Reduza o número de dados carregados
2. Otimize o código
3. Considere upgrade para plano pago

## 🔄 Atualizações Futuras

Sempre que fizer mudanças no código:

```bash
git add .
git commit -m "Descrição das mudanças"
git push
```

O Streamlit Cloud detecta automaticamente o push e faz redeploy do app!

## 📊 Monitoramento

### Ver Logs

1. Acesse [https://share.streamlit.io/](https://share.streamlit.io/)
2. Clique no seu app
3. Clique em **Manage app** → **Logs**

### Reiniciar App

Se o app travar:
1. **Manage app** → **Reboot app**

### Deletar App

Se quiser remover:
1. **Manage app** → **Settings** → **Delete app**

## 🎉 Pronto!

Seu app está no ar! Compartilhe a URL com quem precisar acessar.

**URL do App**: `https://edson-mppe-sistema-gestao-alugueis.streamlit.app`

---

**Dica**: Salve a URL nos favoritos do navegador para acesso rápido!
