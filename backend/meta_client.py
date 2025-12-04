"""
Cliente da Meta Graph API (v24.0) para buscar insights de campanhas.

Este módulo:
- Lê métricas via endpoint /act_<ad_account_id>/insights
- Normaliza campos numéricos (pandas-friendly)
- Consolida compras e valores de compra (action_values)

Observação: a API do Graph retorna números como strings. Convertemos para tipos
numéricos apropriados. O campo 'ctr' é retornado como percentual (ex: "1.23"),
então usamos também o recálculo via clicks/impressions*100 como fallback.
"""
from __future__ import annotations

import requests
from typing import Dict, List, Any


GRAPH_BASE = "https://graph.facebook.com/v24.0"


def _to_int(x: Any) -> int:
    try:
        return int(float(x))
    except Exception:
        return 0


def _to_float(x: Any) -> float:
    try:
        return float(x)
    except Exception:
        return 0.0


def fetch_insights(
    access_token: str,
    ad_account_id: str,
    date_preset: str = "last_7d",
    since: str | None = None,
    until: str | None = None,
    timeout: int = 30,
) -> List[Dict[str, Any]]:
    """Busca dados de insights no nível de campanha, com paginação.

    Args:
        access_token: Token de acesso da Meta.
        ad_account_id: ID da conta de anúncios, sem o prefixo "act_".
        date_preset: Janela temporal (ex: last_7d, last_14d, last_30d).
        timeout: Timeout da requisição em segundos.
    Returns:
        Lista de objetos brutos retornados pela API.
    Raises:
        RuntimeError em caso de erro da API.
    """
    url = f"{GRAPH_BASE}/act_{ad_account_id}/insights"
    params = {
        "fields": ",".join(
            [
                "campaign_id",
                "campaign_name",
                "impressions",
                "clicks",
                "spend",
                "cpm",
                "cpc",
                "ctr",
                "actions",
                "action_values",
            ]
        ),
        "level": "campaign",
        "limit": 5000,
        "access_token": access_token,
    }
    # Garantir que ações/valores sejam contados por tempo de conversão (alinha com o Ads Manager)
    params["action_report_time"] = "conversion"
    params["use_unified_attribution_setting"] = True
    # Permite escolher entre preset e intervalo customizado
    if since and until:
        params["time_range"] = {"since": since, "until": until}
    else:
        params["date_preset"] = date_preset

    all_data: List[Dict[str, Any]] = []
    while True:
        resp = requests.get(url, params=params, timeout=timeout)
        data = resp.json()

        if resp.status_code != 200 or "error" in data:
            err = data.get("error", {})
            message = err.get("message", "Erro ao consultar Meta Graph API")
            raise RuntimeError(message)

        page = data.get("data", [])
        all_data.extend(page)

        paging = data.get("paging", {})
        next_url = paging.get("next")
        if not next_url:
            break

        # A próxima página já inclui token; zera params para continuar por URL completa
        url = next_url
        params = {}

    return all_data


def fetch_insights_by_level(
    access_token: str,
    ad_account_id: str,
    level: str = "campaign",  # "campaign" | "adset" | "ad"
    date_preset: str = "last_7d",
    since: str | None = None,
    until: str | None = None,
    timeout: int = 30,
) -> List[Dict[str, Any]]:
    """Versão genérica parametrizando o `level`.

    Inclui campos de identificação conforme o nível solicitado.
    """
    valid_levels = {"campaign", "adset", "ad"}
    if level not in valid_levels:
        raise ValueError(f"level inválido: {level}")

    id_fields = {
        "campaign": ["campaign_id", "campaign_name"],
        "adset": ["adset_id", "adset_name", "campaign_id"],
        "ad": ["ad_id", "ad_name", "adset_id", "campaign_id"],
    }[level]

    common_fields = [
        "impressions",
        "clicks",
        "spend",
        "cpm",
        "cpc",
        "ctr",
        "actions",
        "action_values",
    ]

    url = f"{GRAPH_BASE}/act_{ad_account_id}/insights"
    params: Dict[str, Any] = {
        "fields": ",".join(id_fields + common_fields),
        "level": level,
        "limit": 5000,
        "access_token": access_token,
    }
    params["action_report_time"] = "conversion"
    params["use_unified_attribution_setting"] = True
    if since and until:
        params["time_range"] = {"since": since, "until": until}
    else:
        params["date_preset"] = date_preset

    all_data: List[Dict[str, Any]] = []
    while True:
        resp = requests.get(url, params=params, timeout=timeout)
        data = resp.json()

        if resp.status_code != 200 or "error" in data:
            err = data.get("error", {})
            message = err.get("message", "Erro ao consultar Meta Graph API")
            raise RuntimeError(message)

        page = data.get("data", [])
        all_data.extend(page)

        paging = data.get("paging", {})
        next_url = paging.get("next")
        if not next_url:
            break

        url = next_url
        params = {}

    return all_data


def _is_purchase_type(action_type: str) -> bool:
    at = (action_type or "").lower()
    allowed = {
        "purchase",
        "fb_pixel_purchase",
        "offsite_conversion.purchase",
        "offsite_conversion.fb_pixel_purchase",
        "onsite_conversion.purchase",
        "omni_purchase",
    }
    return at in allowed or at.endswith(".purchase") or at.endswith("_purchase")


PURCHASE_PRIORITY = [
    "omni_purchase",
    "offsite_conversion.fb_pixel_purchase",
    "offsite_conversion.purchase",
    "onsite_conversion.purchase",
    "fb_pixel_purchase",
    "purchase",
]


def _pick_purchase_count(actions: List[Dict[str, Any]]) -> int:
    by_type = {str(a.get("action_type", "")).lower(): a for a in (actions or [])}
    for t in PURCHASE_PRIORITY:
        a = by_type.get(t)
        if a is not None:
            return _to_int(a.get("value", 0))
    # fallback: soma de todos os tipos de purchase (evitar zero absoluto)
    total = 0
    for a in actions or []:
        if _is_purchase_type(a.get("action_type")):
            total += _to_int(a.get("value", 0))
    return total


def _pick_purchase_value(action_values: List[Dict[str, Any]]) -> float:
    by_type = {str(a.get("action_type", "")).lower(): a for a in (action_values or [])}
    for t in PURCHASE_PRIORITY:
        a = by_type.get(t)
        if a is not None:
            return _to_float(a.get("value", 0.0))
    # fallback: soma (se não houver nenhum dos tipos preferidos)
    total = 0.0
    for av in action_values or []:
        if _is_purchase_type(av.get("action_type")):
            total += _to_float(av.get("value", 0.0))
    return total


def normalize_insights(raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Converte a lista bruta da API em métricas numéricas e campos úteis.

    - CTR: percentual (ex: 1.23 == 1,23%)
    - ROAS: purchase_value / spend
    - Purchases: soma de qualquer action_type contendo "purchase"
    - Purchase_value: soma dos action_values com action_type contendo "purchase"
    """
    normalized: List[Dict[str, Any]] = []
    for row in raw:
        impressions = _to_int(row.get("impressions", 0))
        clicks = _to_int(row.get("clicks", 0))
        spend = _to_float(row.get("spend", 0.0))
        cpm = _to_float(row.get("cpm", 0.0))
        cpc = _to_float(row.get("cpc", 0.0))
        ctr_raw = _to_float(row.get("ctr", 0.0))

        # Recalcula CTR em % como fallback
        ctr_calc = (clicks / impressions * 100.0) if impressions > 0 else 0.0
        ctr = ctr_calc if ctr_calc > 0 else ctr_raw

        actions = row.get("actions", []) or []
        action_values = row.get("action_values", []) or []

        purchases = _pick_purchase_count(actions)
        purchase_value = _pick_purchase_value(action_values)

        roas = (purchase_value / spend) if spend > 0 else 0.0

        normalized.append(
            {
                "campaign_id": row.get("campaign_id", ""),
                "campaign_name": row.get("campaign_name", "(sem nome)"),
                "impressions": impressions,
                "clicks": clicks,
                "spend": round(spend, 4),
                "cpm": round(cpm, 4),
                "cpc": round(cpc, 4),
                "ctr": round(ctr, 4),
                "purchases": purchases,
                "purchase_value": round(purchase_value, 4),
                "roas": round(roas, 4),
            }
        )

    return normalized


def normalize_insights_adset(raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for row in raw:
        impressions = _to_int(row.get("impressions", 0))
        clicks = _to_int(row.get("clicks", 0))
        spend = _to_float(row.get("spend", 0.0))
        cpm = _to_float(row.get("cpm", 0.0))
        cpc = _to_float(row.get("cpc", 0.0))
        ctr_raw = _to_float(row.get("ctr", 0.0))
        ctr_calc = (clicks / impressions * 100.0) if impressions > 0 else 0.0
        ctr = ctr_calc if ctr_calc > 0 else ctr_raw

        actions = row.get("actions", []) or []
        action_values = row.get("action_values", []) or []
        purchases = _pick_purchase_count(actions)
        purchase_value = _pick_purchase_value(action_values)
        roas = (purchase_value / spend) if spend > 0 else 0.0

        normalized.append(
            {
                "adset_id": row.get("adset_id", ""),
                "adset_name": row.get("adset_name", "(sem nome)"),
                "campaign_id": row.get("campaign_id"),
                "impressions": impressions,
                "clicks": clicks,
                "spend": round(spend, 4),
                "cpm": round(cpm, 4),
                "cpc": round(cpc, 4),
                "ctr": round(ctr, 4),
                "purchases": purchases,
                "purchase_value": round(purchase_value, 4),
                "roas": round(roas, 4),
            }
        )
    return normalized


def normalize_insights_ad(raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for row in raw:
        impressions = _to_int(row.get("impressions", 0))
        clicks = _to_int(row.get("clicks", 0))
        spend = _to_float(row.get("spend", 0.0))
        cpm = _to_float(row.get("cpm", 0.0))
        cpc = _to_float(row.get("cpc", 0.0))
        ctr_raw = _to_float(row.get("ctr", 0.0))
        ctr_calc = (clicks / impressions * 100.0) if impressions > 0 else 0.0
        ctr = ctr_calc if ctr_calc > 0 else ctr_raw

        actions = row.get("actions", []) or []
        action_values = row.get("action_values", []) or []
        purchases = _pick_purchase_count(actions)
        purchase_value = _pick_purchase_value(action_values)
        roas = (purchase_value / spend) if spend > 0 else 0.0

        normalized.append(
            {
                "ad_id": row.get("ad_id", ""),
                "ad_name": row.get("ad_name", "(sem nome)"),
                "adset_id": row.get("adset_id"),
                "campaign_id": row.get("campaign_id"),
                "impressions": impressions,
                "clicks": clicks,
                "spend": round(spend, 4),
                "cpm": round(cpm, 4),
                "cpc": round(cpc, 4),
                "ctr": round(ctr, 4),
                "purchases": purchases,
                "purchase_value": round(purchase_value, 4),
                "roas": round(roas, 4),
            }
        )
    return normalized
