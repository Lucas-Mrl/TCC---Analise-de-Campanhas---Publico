# Meta Ads Analyzer com IA (FastAPI + Streamlit)

Aplicação completa para analisar campanhas do Meta Ads (Graph API v24.0) e gerar insights com a API da OpenAI (modelo `gpt-4o-mini`).

- Backend: FastAPI (`/meta/campaigns`, `/meta/analyze`)
- Frontend: Streamlit (tabela de campanhas + análise com IA)
- Normalização: pandas (CTR, CPC, CPM, compras, ROAS)
- Níveis suportados: Campanha, Conjunto (ad set) e Anúncio

## Requisitos
- Python 3.9+
- Acesso à Graph API do Meta (token com permissões de ads insights)
- Chave da OpenAI (`OPENAI_API_KEY`)

## Instalação
1) Clone o repositório e acesse a pasta.
2) (Opcional) Crie e ative um ambiente virtual.
3) Instale as dependências:
```
pip install -r requirements.txt
```

Ou, no Windows, rode o script:
```
scripts\setup_venv.bat
```

No Linux/macOS:
```
bash scripts/setup_venv.sh
```

## Configuração (.env)
Copie o arquivo `.env.example` para `.env` e preencha:
```
META_ACCESS_TOKEN=SEU_TOKEN_DA_META
META_AD_ACCOUNT_ID=SEU_AD_ACCOUNT_ID_SOMENTE_NUMEROS   # Ex.: 123456789012345
OPENAI_API_KEY=SEU_TOKEN_DA_OPENAI
# Opcional para o frontend (padrão: http://127.0.0.1:3000)
# BACKEND_URL=http://127.0.0.1:3000
```
Importante: use apenas números em `META_AD_ACCOUNT_ID` (sem o prefixo `act_`).

## Execução
- Backend (porta 3000):
```
uvicorn backend.main:app --reload --host 127.0.0.1 --port 3000
```
Ou use o script:
- Windows: `scripts\run_backend.bat`
- Linux/macOS: `bash scripts/run_backend.sh`

- Frontend (Streamlit):
```
streamlit run frontend/app.py
```
Ou use o script:
- Windows: `scripts\run_frontend.bat`
- Linux/macOS: `bash scripts/run_frontend.sh`

Abra o Streamlit e use:
- Botão “Ver campanhas” para carregar os dados.
- Botão “Analisar com IA” para um resumo rápido.
- Seção de chat para conversar com a aplicação (envie uma pergunta no campo de entrada). Você pode ajustar o período por:
  - Preset: `last_7d`, `last_14d`, `last_30d`, `this_month`, `last_month`, `maximum`.
  - Personalizado: datas `since` e `until` (YYYY-MM-DD). Há uma opção de “Incluir hoje” para usar a data atual como limite final.
  - Escolha também os níveis que deseja visualizar/analisar: Campanhas, Conjuntos e Anúncios.

## Endpoints principais
- `GET /health` — status do serviço
- `GET /meta/campaigns?date_preset=last_7d` — métricas normalizadas por campanha (também aceita `since` e `until`)
- `GET /meta/adsets?...` — métricas normalizadas por conjunto
- `GET /meta/ads?...` — métricas normalizadas por anúncio
- `GET /meta/analyze?date_preset=last_7d&include_campaigns=true&user_message=...` — análise com IA (também aceita `since`/`until`)
- `POST /meta/analyze` — análise com IA via JSON:
  ```json
  {
    "user_message": "Quais campanhas devo pausar?",
    "date_preset": "maximum",
    "include_campaigns": true,
    "include_levels": ["campaign", "adset", "ad"]
  }
  ```

Campos utilizados: `impressions, clicks, spend, cpm, cpc, ctr, actions, action_values`.

## Como funciona (resumo)
- `backend/meta_client.py` busca insights no nível de campanha com paginação.
- Normaliza métricas: converte strings para números, recalcula CTR (clicks/impressions*100) quando aplicável, soma compras e valores em qualquer `action_type` contendo “purchase”, calcula ROAS.
- `backend/ai_client.py` monta um prompt com heurísticas (CTR baixo, CPC alto vs mediana, ROAS baixo) e chama `gpt-4o-mini`.
- `frontend/app.py` chama o backend, mostra as campanhas e o texto de análise.

## Troubleshooting
- 401/403 da Graph API: verifique permissões do token e escopos (ads_read/ads_management) e se a conta possui acesso.
- `META_AD_ACCOUNT_ID` inválido: use apenas números (sem `act_`).
- Sem dados/zero impressões: campanhas podem estar pausadas ou fora do período; ajuste `date_preset`.
- Limite de taxa/Rate limiting: reduza frequência de chamadas, use janelas de tempo maiores.
- OpenAI erro de autenticação: confira `OPENAI_API_KEY` e se o projeto tem acesso ao modelo `gpt-4o-mini`.

## Segurança
- Não commitar `.env` com credenciais reais.
- Tokens devem ter escopo mínimo necessário.

## Desenvolvimento
- Backend: `backend/main.py`, `backend/meta_client.py`, `backend/ai_client.py`, `backend/schemas.py`.
- Frontend: `frontend/app.py`.
