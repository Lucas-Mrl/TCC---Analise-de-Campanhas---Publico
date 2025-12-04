"""
FastAPI backend para análise de campanhas do Meta Ads com IA.

Rotas principais:
- GET /health              -> verifica se o serviço está ok
- GET /meta/campaigns      -> retorna métricas normalizadas das campanhas
- GET /meta/analyze        -> retorna texto de análise usando gpt-4o-mini

Variáveis de ambiente (via .env):
- META_ACCESS_TOKEN
- META_AD_ACCOUNT_ID (sem o prefixo "act_")
- OPENAI_API_KEY

Execução local:
    uvicorn backend.main:app --reload --host 127.0.0.1 --port 3000
"""
from __future__ import annotations

import os
from typing import List
import re
import unicodedata

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import meta_client
from .ai_client import analyze_campaigns_with_gpt
from .schemas import (
    CampaignMetrics,
    CampaignsResponse,
    AnalyzeResponse,
    AnalyzeRequest,
    AdSetMetrics,
    AdSetsResponse,
    AdMetrics,
    AdsResponse,
)


# Carrega variáveis do arquivo .env
load_dotenv()

META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "")
META_AD_ACCOUNT_ID = os.getenv("META_AD_ACCOUNT_ID", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


app = FastAPI(title="Meta Ads Analyzer API", version="0.1.0")

# CORS liberado para facilitar o acesso do Streamlit local
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


def _require_env():
    if not META_ACCESS_TOKEN:
        raise HTTPException(status_code=500, detail="META_ACCESS_TOKEN ausente no .env")
    if not META_AD_ACCOUNT_ID:
        raise HTTPException(status_code=500, detail="META_AD_ACCOUNT_ID ausente no .env")


def _sanitize_analysis(text: str) -> str:
    """Normaliza o texto para ficar legível e sem formatação incorreta.

    - Remove cabeçalhos padrão indesejados
    - Remove bullets e listas numeradas no início da linha
    - Remove caracteres de formatação invisíveis e controles estranhos
    - Mantém parágrafos (duas quebras), converte quebras simples em espaço
    - Normaliza espaços antes de pontuação
    """
    if not text:
        return text

    # Normaliza quebras
    t = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove caracteres invisíveis/controle (mantém \n e espaço)
    filtered = []
    for ch in t:
        cat = unicodedata.category(ch)
        if ch == "\n" or ch == " " or ch == "\t":
            filtered.append(ch)
        elif cat.startswith("C") or cat in ("Cf",):
            # ignora controles/invisíveis
            continue
        else:
            # normaliza forma
            filtered.append(unicodedata.normalize("NFKC", ch))
    t = "".join(filtered)

    # Remove cabeçalhos indesejados (variantes)
    banned = [
        r"^\s*resposta\s+direta\s*:.*$",
        r"^\s*evid[eê]ncias\s*:.*$",
        r"^\s*a[cç][oõ]es\s+recomendadas\s*:.*$",
        r"^\s*riscos(?:/[oó]bserva[cç][oõ]es)?\s*:.*$",
        r"^\s*pr[oó]ximos\s+passos\s*:.*$",
    ]
    lines = t.split("\n")
    cleaned: List[str] = []
    for ln in lines:
        low = ln.strip().lower()
        if any(re.match(p, low) for p in banned):
            continue
        # Remove bullet/enumeração no início
        ln = re.sub(r"^\s*[\-\*•]\s+", "", ln)
        ln = re.sub(r"^\s*\d+[\.)\-]\s+", "", ln)
        cleaned.append(ln)
    t = "\n".join(cleaned)

    # Protege parágrafos duplos e trata quebras internas de palavra
    t = re.sub(r"\n{3,}", "\n\n", t)
    t = t.strip()
    t = t.replace("\t", " ")
    PARA = "<<PARA>>"
    t = t.replace("\n\n", PARA)
    # Junta quebras entre caracteres de palavra (evita 'l\ni\nh\na')
    t = re.sub(r"(?<=\w)\n(?=\w)", "", t)
    # Remove barras invertidas soltas
    t = re.sub(r"\s*\\\s*", "", t)
    # Converte demais quebras simples em espaço
    t = t.replace("\n", " ")
    # Restaura parágrafos
    t = t.replace(PARA, "\n\n")

    # Normaliza espaços
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r"\s+([,.;:!?])", r"\1", t)
    t = re.sub(r"\(\s+", "(", t)
    t = re.sub(r"\s+\)", ")", t)
    # Ajustes leves de moeda/decimal: 'R $' -> 'R$ ', '195 , 80' -> '195,80'
    t = t.replace("R $", "R$")
    t = re.sub(r"R\$\s+", "R$ ", t)
    t = re.sub(r"(\d)\s*,\s*(\d{1,2})", r"\1,\2", t)

    return t.strip()


@app.get("/meta/campaigns", response_model=CampaignsResponse)
def get_campaigns(date_preset: str = "last_7d", since: str | None = None, until: str | None = None):
    """Retorna lista de campanhas normalizadas para o período informado."""
    _require_env()

    try:
        raw = meta_client.fetch_insights(
            access_token=META_ACCESS_TOKEN,
            ad_account_id=META_AD_ACCOUNT_ID,
            date_preset=date_preset,
            since=since,
            until=until,
        )
        norm_list = meta_client.normalize_insights(raw)

        # Valida com Pydantic
        campaigns: List[CampaignMetrics] = [CampaignMetrics(**c) for c in norm_list]
        return {"campaigns": campaigns, "date_preset": date_preset}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/meta/analyze", response_model=AnalyzeResponse)
def analyze(date_preset: str = "last_7d", include_campaigns: bool = True, user_message: str | None = None, since: str | None = None, until: str | None = None):
    """Analisa campanhas com GPT-4o-mini e retorna o texto da análise.

    Parâmetros:
        date_preset: janela temporal do Meta (ex: last_7d)
        include_campaigns: retorna também a lista de campanhas normalizadas
    """
    _require_env()

    try:
        raw = meta_client.fetch_insights(
            access_token=META_ACCESS_TOKEN,
            ad_account_id=META_AD_ACCOUNT_ID,
            date_preset=date_preset,
            since=since,
            until=until,
        )
        norm_list = meta_client.normalize_insights(raw)
        # Para GET clássico, analisamos campanha e, se a pergunta indicar criativos/conjuntos, buscamos níveis adicionais
        adsets = None
        ads = None
        text = (user_message or "").lower()
        wants_ads = any(k in text for k in ["criativo", "criativos", "anuncio", "anúncio", "ads"]) if user_message else False
        wants_adsets = any(k in text for k in ["conjunto", "conjuntos", "adset"]) if user_message else False
        if wants_adsets:
            raw_s = meta_client.fetch_insights_by_level(
                access_token=META_ACCESS_TOKEN,
                ad_account_id=META_AD_ACCOUNT_ID,
                level="adset",
                date_preset=date_preset,
                since=since,
                until=until,
            )
            adsets = meta_client.normalize_insights_adset(raw_s)
        if wants_ads:
            raw_a = meta_client.fetch_insights_by_level(
                access_token=META_ACCESS_TOKEN,
                ad_account_id=META_AD_ACCOUNT_ID,
                level="ad",
                date_preset=date_preset,
                since=since,
                until=until,
            )
            ads = meta_client.normalize_insights_ad(raw_a)

        period_label = f"{since} até {until}" if since and until else date_preset
        # Enriquecimento leve com detecção de intenção para personalização
        intent = []
        if user_message:
            t = user_message.lower()
            if any(k in t for k in ["criativo", "criativos", "anuncio", "anúncio", "ads"]):
                intent.append("analise_criativos")
            if any(k in t for k in ["orçamento", "budget", "gastar", "investir", "escala"]):
                intent.append("alocacao_orcamento")
            if any(k in t for k in ["problema", "cairam", "queda", "queda de desempenho", "troubleshooting"]):
                intent.append("diagnostico")
            if any(k in t for k in ["novo produto", "novos produtos", "lançar", "lançamento", "go to market"]):
                intent.append("novo_produto")
            if any(k in t for k in ["estrutura", "funnel", "funil", "campanhas", "conjuntos"]):
                intent.append("estrutura")
        augmented_query = user_message
        if intent:
            augmented_query = f"{user_message}\n\nIntenção detectada: {', '.join(intent)}"
        analysis_text = analyze_campaigns_with_gpt(
            norm_list,
            api_key=OPENAI_API_KEY,
            user_query=augmented_query,
            period_label=period_label,
            adsets=adsets,
            ads=ads,
            intents=intent,
        )
        analysis_text = _sanitize_analysis(analysis_text)

        if include_campaigns:
            campaigns = [CampaignMetrics(**c) for c in norm_list]
        else:
            campaigns = None

        return {"analysis": analysis_text, "campaigns": campaigns}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/meta/analyze", response_model=AnalyzeResponse)
def analyze_post(body: AnalyzeRequest):
    """Versão POST para conversas/inputs maiores e controle de período."""
    _require_env()

    try:
        include_levels = body.include_levels or ["campaign", "adset", "ad"]
        # Refina include_levels com base na pergunta do usuário
        text = (body.user_message or "").lower()
        if "ad" not in include_levels and any(k in text for k in ["criativo", "criativos", "anuncio", "anúncio", "ads"]):
            include_levels.append("ad")
        if "adset" not in include_levels and any(k in text for k in ["conjunto", "conjuntos", "adset"]):
            include_levels.append("adset")

        campaigns = None
        adsets = None
        ads = None

        if "campaign" in include_levels:
            raw_c = meta_client.fetch_insights(
                access_token=META_ACCESS_TOKEN,
                ad_account_id=META_AD_ACCOUNT_ID,
                date_preset=body.date_preset or "last_7d",
                since=body.since,
                until=body.until,
            )
            campaigns = [CampaignMetrics(**c) for c in meta_client.normalize_insights(raw_c)]

        if "adset" in include_levels:
            raw_s = meta_client.fetch_insights_by_level(
                access_token=META_ACCESS_TOKEN,
                ad_account_id=META_AD_ACCOUNT_ID,
                level="adset",
                date_preset=body.date_preset or "last_7d",
                since=body.since,
                until=body.until,
            )
            adsets = [AdSetMetrics(**c) for c in meta_client.normalize_insights_adset(raw_s)]

        if "ad" in include_levels:
            raw_a = meta_client.fetch_insights_by_level(
                access_token=META_ACCESS_TOKEN,
                ad_account_id=META_AD_ACCOUNT_ID,
                level="ad",
                date_preset=body.date_preset or "last_7d",
                since=body.since,
                until=body.until,
            )
            ads = [AdMetrics(**c) for c in meta_client.normalize_insights_ad(raw_a)]

        period_label = f"{body.since} até {body.until}" if body.since and body.until else (body.date_preset or "last_7d")
        # Detecção simples de intenção para personalizar a resposta
        augmented_query = body.user_message
        if body.user_message:
            t = body.user_message.lower()
            intent = []
            if any(k in t for k in ["criativo", "criativos", "anuncio", "anúncio", "ads"]):
                intent.append("analise_criativos")
            if any(k in t for k in ["orçamento", "budget", "gastar", "investir", "escala"]):
                intent.append("alocacao_orcamento")
            if any(k in t for k in ["problema", "cairam", "queda", "queda de desempenho", "troubleshooting"]):
                intent.append("diagnostico")
            if any(k in t for k in ["novo produto", "novos produtos", "lançar", "lançamento", "go to market"]):
                intent.append("novo_produto")
            if any(k in t for k in ["estrutura", "funnel", "funil", "campanhas", "conjuntos"]):
                intent.append("estrutura")
            if intent:
                augmented_query = f"{body.user_message}\n\nIntenção detectada: {', '.join(intent)}"
        analysis_text = analyze_campaigns_with_gpt(
            campaigns=[c.dict() for c in campaigns] if campaigns else None,
            api_key=OPENAI_API_KEY,
            user_query=augmented_query,
            period_label=period_label,
            adsets=[s.dict() for s in adsets] if adsets else None,
            ads=[a.dict() for a in ads] if ads else None,
            history=[m.dict() for m in (body.messages or [])] if hasattr(body, "messages") and body.messages else None,
            intents=intent if body.user_message else None,
        )
        analysis_text = _sanitize_analysis(analysis_text)

        result = {"analysis": analysis_text}
        if body.include_campaigns:
            result["campaigns"] = campaigns
            if adsets is not None:
                result["adsets"] = adsets
            if ads is not None:
                result["ads"] = ads
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="127.0.0.1", port=3000, reload=True)
@app.get("/meta/adsets", response_model=AdSetsResponse)
def get_adsets(date_preset: str = "last_7d", since: str | None = None, until: str | None = None):
    _require_env()
    try:
        raw = meta_client.fetch_insights_by_level(
            access_token=META_ACCESS_TOKEN,
            ad_account_id=META_AD_ACCOUNT_ID,
            level="adset",
            date_preset=date_preset,
            since=since,
            until=until,
        )
        norm_list = meta_client.normalize_insights_adset(raw)
        adsets = [AdSetMetrics(**c) for c in norm_list]
        return {"adsets": adsets, "date_preset": date_preset}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/meta/ads", response_model=AdsResponse)
def get_ads(date_preset: str = "last_7d", since: str | None = None, until: str | None = None):
    _require_env()
    try:
        raw = meta_client.fetch_insights_by_level(
            access_token=META_ACCESS_TOKEN,
            ad_account_id=META_AD_ACCOUNT_ID,
            level="ad",
            date_preset=date_preset,
            since=since,
            until=until,
        )
        norm_list = meta_client.normalize_insights_ad(raw)
        ads = [AdMetrics(**c) for c in norm_list]
        return {"ads": ads, "date_preset": date_preset}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



