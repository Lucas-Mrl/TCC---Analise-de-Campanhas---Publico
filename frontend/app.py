"""
Streamlit frontend para visualizar campanhas do Meta Ads e gerar análise com IA.

Como executar (em terminais separados):
- Backend: uvicorn backend.main:app --reload --host 127.0.0.1 --port 3000
- Frontend: streamlit run frontend/app.py
"""
from __future__ import annotations

import os
from datetime import date, timedelta
import requests
import pandas as pd
import streamlit as st
import re as _re


# URL do backend (pode ser alterado via variável de ambiente BACKEND_URL)
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:3000")

# Guia de estilo injetado junto da pergunta do usuário para melhorar personalização
STYLE_GUIDE = (
    "Você é uma IA estrategista de marketing e mídia paga. "
    "PRIORIDADE: responder como um analista humano explicaria para um colega, em 1 a 3 parágrafos coesos, sem seções fixas, sem títulos e sem formato de relatório. "
    "OVERRIDE: ignore qualquer instrução anterior de output_format, seções obrigatórias, listas padrão ou JSON. NÃO use cabeçalhos como 'Resposta direta', 'Evidências', 'Ações recomendadas', 'Riscos', 'Próximos passos'. "
    "ESTILO: escreva em português do Brasil, tom natural e analítico. Produza apenas o texto final, sem meta-comentários. Evite bullets; use parágrafo corrido salvo pedido explícito. Não invente dados; se faltar, diga 'Sem dados suficientes'. "
    "CONTEÚDO: interprete as métricas (CTR, CPC, CPA, ROAS, Purchases, Spend) e explique o que significam neste caso, por que aconteceu e qual ação prática tomar. Sempre relacione recomendações aos dados. "
    "FOCO: se houver 'focus' (criativos, orçamento, diagnóstico, lançamento, estrutura), use apenas para escolher o que abordar, NUNCA para mudar o formato. "
)

st.set_page_config(page_title="Meta Ads + IA", page_icon="📊", layout="wide")
st.markdown(
    """
    <style>
      .hero {background: linear-gradient(90deg,#0ea5e9 0%,#6366f1 100%); padding:18px 22px; border-radius:10px; color:#fff; margin-bottom:14px;}
      .hero h1 {margin:0; font-size:1.4rem;}
      .hero p {margin:6px 0 0 0; opacity:0.95;}
      .section-title {margin-top:8px; margin-bottom:8px; font-weight:600;}
    </style>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    """
    <div class="hero">
      <h1>📊 Análise de campanhas com IA</h1>
      <p>Insights de campanhas com análise conversacional — GPT‑4o‑mini</p>
    </div>
    """,
    unsafe_allow_html=True,
)
st.caption("Backend: FastAPI · Frontend: Streamlit")


if "campaigns_df" not in st.session_state:
    st.session_state.campaigns_df = pd.DataFrame()
if "adsets_df" not in st.session_state:
    st.session_state.adsets_df = pd.DataFrame()
if "ads_df" not in st.session_state:
    st.session_state.ads_df = pd.DataFrame()
if "analysis_text" not in st.session_state:
    st.session_state.analysis_text = ""
if "messages" not in st.session_state:
    st.session_state.messages = []  # [{role: "user"|"assistant", content: str}]


with st.sidebar:
    st.header("Configuração")
    date_mode = st.radio("Período", ["Preset", "Personalizado"], index=0, horizontal=True)
    date_preset = None
    since = None
    until = None
    if date_mode == "Preset":
        presets = [
            ("Hoje", "today"),
            ("Últimos 7 dias", "last_7d"),
            ("Últimos 14 dias", "last_14d"),
            ("Últimos 30 dias", "last_30d"),
            ("Este mês", "this_month"),
            ("Mês passado", "last_month"),
            ("Máximo", "maximum"),
        ]
        labels = [p[0] for p in presets]
        sel = st.selectbox("Janela de datas (Meta)", options=labels, index=1)
        date_preset = dict(presets)[sel]
    else:
        st.markdown("<div class='section-title'>Intervalo personalizado</div>", unsafe_allow_html=True)
        start_default = date.today() - timedelta(days=7)
        end_default = date.today()
        start_date = st.date_input("Data inicial", value=start_default, max_value=date.today())
        end_date = st.date_input("Data final", value=end_default, min_value=start_date, max_value=date.today())
        if start_date and end_date:
            since = start_date.strftime("%Y-%m-%d")
            until = end_date.strftime("%Y-%m-%d")
    st.markdown(f"Backend: `{BACKEND_URL}`")

    st.divider()
    st.subheader("Níveis para visualizar/analisar")
    show_campaigns = st.checkbox("Campanhas", value=True)
    show_adsets = st.checkbox("Conjuntos", value=True)
    show_ads = st.checkbox("Anúncios", value=True)

    st.divider()
    st.subheader("Foco da resposta")
    focus = st.selectbox(
        "Foque a análise em:",
        options=["auto", "criativos", "orcamento", "diagnostico", "lancamento", "estrutura"],
        index=0,
        help="Personaliza a prioridade do conteúdo da resposta",
    )


col1, col2 = st.columns(2)
with col1:
    if st.button("Ver campanhas", type="primary"):
        loading = st.empty()
        loading.info("Carregando dados das campanhas…")
        try:
            params = {"date_preset": date_preset} if date_preset else {"since": since, "until": until}
            if show_campaigns:
                resp = requests.get(f"{BACKEND_URL}/meta/campaigns", params=params, timeout=60)
                resp.raise_for_status()
                data = resp.json()
                st.session_state.campaigns_df = pd.DataFrame(data.get("campaigns", []))
            if show_adsets:
                resp = requests.get(f"{BACKEND_URL}/meta/adsets", params=params, timeout=60)
                resp.raise_for_status()
                data = resp.json()
                st.session_state["adsets_df"] = pd.DataFrame(data.get("adsets", []))
            if show_ads:
                resp = requests.get(f"{BACKEND_URL}/meta/ads", params=params, timeout=60)
                resp.raise_for_status()
                data = resp.json()
                st.session_state["ads_df"] = pd.DataFrame(data.get("ads", []))
            loading.success("Dados carregados!")
        except Exception as e:
            loading.empty()
            st.error(f"Erro ao buscar campanhas: {e}")

with col2:
    if st.button("Analisar com IA"):
        loading = st.empty()
        loading.info("Analisando campanhas com IA…")
        try:
            payload = {
                "user_message": STYLE_GUIDE + "\n\nPergunta: análise geral baseada nos dados carregados, seguindo as regras de estilo.",
                "include_campaigns": True,
                "include_levels": [
                    *(["campaign"] if show_campaigns else []),
                    *(["adset"] if show_adsets else []),
                    *(["ad"] if show_ads else []),
                ],
            }
            if date_preset:
                payload["date_preset"] = date_preset
            else:
                payload["since"] = since
                payload["until"] = until
            if focus and focus != "auto":
                payload["focus"] = focus
            if st.session_state.messages:
                payload["messages"] = st.session_state.messages[-6:]
            resp = requests.post(f"{BACKEND_URL}/meta/analyze", json=payload, timeout=180)
            resp.raise_for_status()
            data = resp.json()
            st.session_state.analysis_text = data.get("analysis", "")
            if data.get("campaigns"):
                st.session_state.campaigns_df = pd.DataFrame(data["campaigns"]) 
            if data.get("adsets"):
                st.session_state["adsets_df"] = pd.DataFrame(data["adsets"]) 
            if data.get("ads"):
                st.session_state["ads_df"] = pd.DataFrame(data["ads"]) 
            loading.success("Análise concluída!")
        except Exception as e:
            loading.empty()
            st.error(f"Erro na análise com IA: {e}")


st.markdown("<div class='section-title'>Dados</div>", unsafe_allow_html=True)
tabs = st.tabs(["Campanhas", "Conjuntos", "Anúncios"])
with tabs[0]:
    if show_campaigns:
        if st.session_state.get("campaigns_df", pd.DataFrame()).empty:
            st.info("Clique em 'Ver campanhas' para carregar os dados.")
        else:
            st.dataframe(st.session_state.campaigns_df, use_container_width=True, hide_index=True)
    else:
        st.caption("Oculto nas opções da barra lateral.")
with tabs[1]:
    if show_adsets:
        if st.session_state.get("adsets_df", pd.DataFrame()).empty:
            st.info("Carregue os conjuntos pelo botão 'Ver campanhas'.")
        else:
            st.dataframe(st.session_state["adsets_df"], use_container_width=True, hide_index=True)
    else:
        st.caption("Oculto nas opções da barra lateral.")
with tabs[2]:
    if show_ads:
        if st.session_state.get("ads_df", pd.DataFrame()).empty:
            st.info("Carregue os anúncios pelo botão 'Ver campanhas'.")
        else:
            st.dataframe(st.session_state["ads_df"], use_container_width=True, hide_index=True)
    else:
        st.caption("Oculto nas opções da barra lateral.")


st.markdown("<div class='section-title'>Análise da IA</div>", unsafe_allow_html=True)
if not st.session_state.analysis_text:
    st.info("Clique em 'Analisar com IA' para gerar insights.")
else:
    _txt = _re.sub(r"\n{3,}", "\n\n", st.session_state.analysis_text or "").strip()
    st.markdown(_txt)


st.markdown("<div class='section-title'>Converse com a aplicação</div>", unsafe_allow_html=True)
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if user_input := st.chat_input("Faça uma pergunta sobre suas campanhas..."):
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    try:
        payload = {
            "user_message": user_input,
            "include_campaigns": True,
            "include_levels": [
                *(["campaign"] if show_campaigns else []),
                *(["adset"] if show_adsets else []),
                *(["ad"] if show_ads else []),
            ],
        }
        if date_preset:
            payload["date_preset"] = date_preset
        else:
            payload["since"] = since
            payload["until"] = until

        if focus and focus != "auto":
            payload["user_message"] = f"{STYLE_GUIDE}\n\nFoco: {focus}\nPergunta: {user_input}"
            payload["focus"] = focus
        else:
            payload["user_message"] = f"{STYLE_GUIDE}\n\nPergunta: {user_input}"

        payload["messages"] = st.session_state.messages
        loading = st.empty()
        loading.info("Gerando resposta personalizada…")
        resp = requests.post(f"{BACKEND_URL}/meta/analyze", json=payload, timeout=180)
        resp.raise_for_status()
        data = resp.json()
        loading.empty()

        assistant_text = data.get("analysis", "")
        if data.get("campaigns"):
            st.session_state.campaigns_df = pd.DataFrame(data["campaigns"])
        if data.get("adsets"):
            st.session_state["adsets_df"] = pd.DataFrame(data["adsets"])
        if data.get("ads"):
            st.session_state["ads_df"] = pd.DataFrame(data["ads"])

        st.session_state.analysis_text = assistant_text
        st.session_state.messages.append({"role": "assistant", "content": assistant_text})
        with st.chat_message("assistant"):
            st.markdown(assistant_text)
    except Exception as e:
        err = f"Erro ao conversar com a IA: {e}"
        st.session_state.messages.append({"role": "assistant", "content": err})
        with st.chat_message("assistant"):
            st.markdown(err)
