"""
Cliente da API da OpenAI para análise das campanhas com o modelo gpt-4o-mini.
"""
from __future__ import annotations

from typing import List, Dict, Optional
import pandas as pd

from openai import OpenAI


def _top_n(df: pd.DataFrame, by: str, n: int = 5, cols: Optional[List[str]] = None) -> str:
    if df.empty or by not in df.columns:
        return "(sem dados)"
    view = df.sort_values(by=by, ascending=False).head(n)
    if cols:
        view = view[[c for c in cols if c in view.columns]]
    return view.to_csv(index=False)


def _stats_block(df: pd.DataFrame, label: str, metrics: Optional[List[str]] = None) -> str:
    if df.empty:
        return f"[{label} Stats]\n(sem dados)"
    metrics = metrics or ["roas", "purchases", "purchase_value", "ctr", "cpc", "spend"]
    parts: List[str] = [f"[{label} Stats]"]
    for m in metrics:
        if m in df.columns and df[m].dtype != "O":
            series = pd.to_numeric(df[m], errors="coerce").fillna(0)
            q25 = float(series.quantile(0.25))
            med = float(series.quantile(0.50))
            q75 = float(series.quantile(0.75))
            parts.append(f"- {m}: p25={q25:.2f} · p50={med:.2f} · p75={q75:.2f}")
    return "\n".join(parts)


def _build_prompt(
    campaigns: Optional[List[Dict]] = None,
    adsets: Optional[List[Dict]] = None,
    ads: Optional[List[Dict]] = None,
    user_query: str | None = None,
    period_label: str | None = None,
    intents: Optional[List[str]] = None,
) -> str:
    """Monta um prompt claro e focado em performance de campanhas.

    Inclui tabela CSV com métricas essenciais para permitir análise numérica.
    """
    csv_sections = []

    if campaigns:
        df_c = pd.DataFrame(campaigns)
        # shares de orçamento e receita
        if not df_c.empty:
            total_spend_c = float(df_c["spend"].sum()) or 1.0
            total_rev_c = float(df_c["purchase_value"].sum()) or 1.0
            df_c["spend_share"] = (df_c["spend"] / total_spend_c) * 100
            df_c["rev_share"] = (df_c["purchase_value"] / total_rev_c) * 100
        if not df_c.empty and "roas" in df_c.columns:
            df_c = df_c.sort_values(by="roas", ascending=False)
        csv_sections.append("[Campanhas]\n" + df_c.to_csv(index=False))

    if adsets:
        df_s = pd.DataFrame(adsets)
        if not df_s.empty:
            total_spend_s = float(df_s["spend"].sum()) or 1.0
            total_rev_s = float(df_s["purchase_value"].sum()) or 1.0
            df_s["spend_share"] = (df_s["spend"] / total_spend_s) * 100
            df_s["rev_share"] = (df_s["purchase_value"] / total_rev_s) * 100
        if not df_s.empty and "roas" in df_s.columns:
            df_s = df_s.sort_values(by="roas", ascending=False)
        csv_sections.append("[Conjuntos]\n" + df_s.to_csv(index=False))

    if ads:
        df_a = pd.DataFrame(ads)
        if not df_a.empty:
            total_spend_a = float(df_a["spend"].sum()) or 1.0
            total_rev_a = float(df_a["purchase_value"].sum()) or 1.0
            df_a["spend_share"] = (df_a["spend"] / total_spend_a) * 100
            df_a["rev_share"] = (df_a["purchase_value"] / total_rev_a) * 100
        if not df_a.empty and "roas" in df_a.columns:
            df_a = df_a.sort_values(by="roas", ascending=False)
        csv_sections.append("[Anúncios]\n" + df_a.to_csv(index=False))

    csv_view = "\n\n".join(csv_sections) if csv_sections else "(sem dados)"

    # Resumo de disponibilidade de dados e colunas (ajuda a evitar alucinações)
    summary_lines: List[str] = []
    if campaigns:
        dfc = pd.DataFrame(campaigns)
        summary_lines.append(f"Campanhas: {len(dfc)} linhas • colunas: {', '.join(list(dfc.columns))}")
    if adsets:
        dfs = pd.DataFrame(adsets)
        summary_lines.append(f"Conjuntos: {len(dfs)} linhas • colunas: {', '.join(list(dfs.columns))}")
    if ads:
        dfa = pd.DataFrame(ads)
        summary_lines.append(f"Anúncios: {len(dfa)} linhas • colunas: {', '.join(list(dfa.columns))}")
    availability = "\n".join(summary_lines) if summary_lines else "Nenhum dado disponível no período."

    # Destaques para facilitar respostas objetivas
    highlights_parts: List[str] = []
    if campaigns:
        dfc = pd.DataFrame(campaigns)
        highlights_parts.append("[Top Campanhas por ROAS]\n" + _top_n(dfc, "roas", cols=["campaign_name","campaign_id","roas","purchase_value","purchases","ctr","cpc","spend"]))
    if adsets:
        dfs = pd.DataFrame(adsets)
        highlights_parts.append("[Top Conjuntos por ROAS]\n" + _top_n(dfs, "roas", cols=["adset_name","adset_id","campaign_id","roas","purchase_value","purchases","ctr","cpc","spend"]))
    if ads:
        dfa = pd.DataFrame(ads)
        highlights_parts.append("[Top Anúncios por ROAS]\n" + _top_n(dfa, "roas", cols=["ad_name","ad_id","adset_id","campaign_id","roas","purchase_value","purchases","ctr","cpc","spend"]))
        highlights_parts.append("[Top Anúncios por Compras]\n" + _top_n(dfa, "purchases", cols=["ad_name","ad_id","purchases","purchase_value","roas","ctr","cpc","spend"]))
        highlights_parts.append("[Top Anúncios por CTR]\n" + _top_n(dfa, "ctr", cols=["ad_name","ad_id","ctr","roas","purchases","spend"]))
    highlights = "\n\n".join([p for p in highlights_parts if p]) if highlights_parts else "(sem destaques)"

    # Estatísticas de benchmarks por nível
    stats_blocks: List[str] = []
    if campaigns:
        stats_blocks.append(_stats_block(pd.DataFrame(campaigns), "Campanhas"))
    if adsets:
        stats_blocks.append(_stats_block(pd.DataFrame(adsets), "Conjuntos"))
    if ads:
        stats_blocks.append(_stats_block(pd.DataFrame(ads), "Anúncios"))
    stats_text = "\n".join(stats_blocks) if stats_blocks else "(sem estatísticas)"

    grounding_rules = (
        "Regras de fundamentação (obrigatórias):\n"
        "- Use apenas os dados fornecidos nas seções abaixo. Não invente números, nomes ou resultados.\n"
        "- Se alguma informação não estiver presente, diga 'Sem dados suficientes' e explique o que falta.\n"
        "- Ao listar itens, inclua nome e ID (quando disponíveis) e as métricas exatas usadas (ex.: ROAS, compras, CTR, spend).\n"
        "- Prefira valores com 2 casas decimais; não arredonde ao ponto de distorcer.\n"
        "- Priorize o nível solicitado pela pergunta (Anúncios → Conjuntos → Campanhas).\n"
    )

    output_format = (
        "Formato de saída (siga estritamente):\n"
        "1) Resposta direta (duas a três linhas) — responda exatamente o que foi perguntado.\n"
        "2) Evidências (bullets) — liste até 5 itens com Nome/ID e métricas usadas.\n"
        "3) Ações recomendadas (bullets) — passos objetivos e acionáveis.\n"
        "4) Riscos/Observações (curto).\n"
        "5) Próximos passos mensuráveis (bullets).\n"
    )

    # Estilos de resposta dinâmicos por intenção
    style_guidance: List[str] = []
    intents = intents or []
    if any(i in intents for i in ["analise_criativos", "creative_strategy", "criativos"]):
        style_guidance.append(
            "Modo: Relatório de criativos — comece listando os 3–5 melhores anúncios por objetivo (ROAS, compras, CTR), depois insights sobre padrões de criativos (formato, ângulos, hooks) e um plano de teste A/B multivariado (3 hipóteses)."
        )
    if any(i in intents for i in ["alocacao_orcamento", "budget_plan", "escala", "growth"]):
        style_guidance.append(
            "Modo: Plano de orçamento — traga uma tabela (texto) de realocação com campanha/conjunto/anúncio, spend_share atual → sugerido, e justificativa breve; finalize com regras automáticas (limiares de pausa/escala)."
        )
    if any(i in intents for i in ["diagnostico", "troubleshooting", "queda"]):
        style_guidance.append(
            "Modo: Diagnóstico — destaque quedas versus mediana (p50) e aponte 3 causas prováveis por nível, com passos de correção imediatos."
        )
    if any(i in intents for i in ["novo_produto", "go_to_market", "estrutura", "funnel", "funil"]):
        style_guidance.append(
            "Modo: Go-to-market — proponha estrutura Prospecting/Retargeting/Retention, com metas de CTR/CPC/ROAS e orçamentos iniciais proporcionais; inclua timeline de 2 semanas com checkpoints."
        )
    if not style_guidance:
        style_guidance.append("Modo: Responda de forma específica para a pergunta do usuário, sem formato fixo, escolhendo o estilo mais adequado (lista, passos, mini-tabela, ou plano).")

    style_text = "\n".join(style_guidance)

    instructions = (
        "Contexto: Você é um analista de mídia focado em Meta Ads.\n"
        f"{grounding_rules}\n"
        "Evite clichês e conselhos genéricos. Não repita frases. Adapte o formato ao objetivo da pergunta.\n"
        f"{style_text}\n"
        f"{output_format}"
    )
    user_section = f"\nPergunta do usuário: {user_query}\n" if user_query else ""
    period_section = f"Período analisado: {period_label}\n" if period_label else ""

    return (
        f"{instructions}\n{period_section}{user_section}\n"
        "Disponibilidade de dados:\n"
        f"{availability}\n\n"
        "Benchmarks (p25/p50/p75):\n"
        f"{stats_text}\n\n"
        "Destaques calculados:\n"
        f"{highlights}\n\n"
        "Dados completos (CSV):\n"
        f"{csv_view}\n"
    )


def analyze_campaigns_with_gpt(
    campaigns: Optional[List[Dict]],
    api_key: str,
    user_query: str | None = None,
    period_label: str | None = None,
    adsets: Optional[List[Dict]] = None,
    ads: Optional[List[Dict]] = None,
    history: Optional[List[Dict[str, str]]] = None,
    intents: Optional[List[str]] = None,
) -> str:
    """Chama o modelo gpt-4o-mini para analisar as campanhas.

    Args:
        campaigns: lista de dicionários normalizados.
        api_key: OPENAI_API_KEY.
    Returns:
        Texto com análise.
    """
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY não encontrado nas variáveis de ambiente.")

    client = OpenAI(api_key=api_key)

    prompt = _build_prompt(campaigns=campaigns, adsets=adsets, ads=ads, user_query=user_query, period_label=period_label, intents=intents)

    # Monta histórico conversacional (opcional)
    messages = [
        {"role": "system", "content": (
            "Você é um analista de mídia sênior especializado em Meta Ads. "
            "Nunca invente dados; se não houver dado, diga claramente. "
            "Responda primeiro à pergunta, depois mostre evidências e ações."
        )},
    ]
    if history:
        # Mantém apenas as últimas 8 mensagens para reduzir tokens
        trimmed = history[-8:]
        # Filtra apenas roles suportados
        for m in trimmed:
            r = m.get("role", "user")
            if r not in ("user", "assistant"):
                r = "user"
            messages.append({"role": r, "content": m.get("content", "")})
    # Adiciona a solicitação atual com dados tabulares
    messages.append({"role": "user", "content": prompt})

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.25,
        max_tokens=1600,
        frequency_penalty=0.2,
        presence_penalty=0.1,
    )

    return completion.choices[0].message.content.strip()
