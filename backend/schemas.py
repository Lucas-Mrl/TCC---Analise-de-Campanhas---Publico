from pydantic import BaseModel
from typing import List, Optional


class CampaignMetrics(BaseModel):
    """Modelo de métricas normalizadas por campanha."""
    campaign_id: str
    campaign_name: str
    impressions: int
    clicks: int
    spend: float
    cpm: float
    cpc: float
    ctr: float  # porcentagem, ex: 1.23 significa 1,23%
    purchases: int
    purchase_value: float
    roas: float


class CampaignsResponse(BaseModel):
    campaigns: List[CampaignMetrics]
    date_preset: str


class AnalyzeResponse(BaseModel):
    analysis: str
    campaigns: Optional[List[CampaignMetrics]] = None
    adsets: Optional[List["AdSetMetrics"]] = None
    ads: Optional[List["AdMetrics"]] = None


class ErrorResponse(BaseModel):
    detail: str


class AnalyzeRequest(BaseModel):
    """Entrada para análise interativa com escolha de período e prompt do usuário."""
    user_message: Optional[str] = None
    date_preset: Optional[str] = "last_7d"  # ex.: last_7d, maximum, etc.
    since: Optional[str] = None  # YYYY-MM-DD
    until: Optional[str] = None  # YYYY-MM-DD
    include_campaigns: bool = True
    include_levels: Optional[List[str]] = None  # ["campaign","adset","ad"]
    messages: Optional[List["ChatMessage"]] = None  # historico opcional do chat
    focus: Optional[str] = None  # criativos | orcamento | diagnostico | lancamento | estrutura


class AdSetMetrics(BaseModel):
    """Métricas normalizadas por conjunto de anúncios (ad set)."""
    adset_id: str
    adset_name: str
    campaign_id: Optional[str] = None
    impressions: int
    clicks: int
    spend: float
    cpm: float
    cpc: float
    ctr: float
    purchases: int
    purchase_value: float
    roas: float


class AdSetsResponse(BaseModel):
    adsets: List[AdSetMetrics]
    date_preset: str


class AdMetrics(BaseModel):
    """Métricas normalizadas por anúncio."""
    ad_id: str
    ad_name: str
    adset_id: Optional[str] = None
    campaign_id: Optional[str] = None
    impressions: int
    clicks: int
    spend: float
    cpm: float
    cpc: float
    ctr: float
    purchases: int
    purchase_value: float
    roas: float


class AdsResponse(BaseModel):
    ads: List[AdMetrics]
    date_preset: str


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


try:
    AnalyzeResponse.update_forward_refs(AdSetMetrics=AdSetMetrics, AdMetrics=AdMetrics)
    AnalyzeRequest.update_forward_refs(ChatMessage=ChatMessage)
except Exception:
    pass

