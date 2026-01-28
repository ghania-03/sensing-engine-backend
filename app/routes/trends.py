from fastapi import APIRouter
import pandas as pd
from pathlib import Path

router = APIRouter()
DATA_DIR = Path(__file__).resolve().parents[2] / 'data'
GOOGLE_SIGNALS_FILE = DATA_DIR / 'google_signals.csv'

SKU_TITLES = {
    'GS-019': 'Electric Kettle',
    'BL-101': 'High-speed Blender',
    'GS-045': 'Premium Mug',
    'VDJ-045': 'Vintage Denim Jacket',
    'PDE-112': 'Freshwater Pearl Earrings',
    'LCB-089': 'Leather Crossbody',
    'CBS-067': 'Cashmere Sweater',
}


def _load_social() -> pd.DataFrame:
    cleaned_dir = DATA_DIR / 'cleaned'
    parquet_path = cleaned_dir / 'social.parquet'
    if parquet_path.exists():
        df = pd.read_parquet(parquet_path)
    else:
        df = pd.read_csv(DATA_DIR / 'social.csv', parse_dates=['date']).fillna('')

    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
    else:
        df['date'] = pd.Timestamp.now()

    if 'hashtag' not in df.columns:
        df['hashtag'] = ''
    df['title_hashtag'] = df['hashtag'].astype(str).fillna('').str.strip()

    if 'sku' not in df.columns:
        df['sku'] = 'UNKNOWN'
    else:
        df['sku'] = df['sku'].astype(str).fillna('UNKNOWN')
    df['sku'] = df['sku'].replace({'': 'UNKNOWN'})

    if 'source' not in df.columns:
        df['source'] = 'social'
    else:
        df['source'] = df['source'].astype(str).fillna('social')
    df['source'] = df['source'].replace({'': 'social'})

    if 'mentions' not in df.columns:
        df['mentions'] = 0
    df['mentions'] = pd.to_numeric(df['mentions'], errors='coerce').fillna(0).astype(int)
    return df


def _load_google_signals() -> pd.DataFrame:
    if not GOOGLE_SIGNALS_FILE.exists():
        return pd.DataFrame(
            columns=['date', 'hashtag', 'mentions', 'source', 'sku', 'post_id', 'text', 'keyword']
        )
    df = pd.read_csv(GOOGLE_SIGNALS_FILE, parse_dates=['date']).fillna('')
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    if 'source' not in df.columns:
        df['source'] = 'google'
    else:
        df['source'] = df['source'].astype(str).fillna('google')
    df['mentions'] = pd.to_numeric(df['mentions'], errors='coerce').fillna(0).astype(int)
    return df


def _load_historic() -> pd.DataFrame:
    cleaned_dir = DATA_DIR / 'cleaned'
    parquet_path = cleaned_dir / 'historic.parquet'
    if parquet_path.exists():
        df = pd.read_parquet(parquet_path)
    else:
        df = pd.read_csv(DATA_DIR / 'historic.csv', parse_dates=['date'])
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    return df


def _pct_change(current: int, previous: int) -> int:
    if previous <= 0:
        return 100 if current > 0 else 0
    change = ((current - previous) / previous) * 100
    return int(max(-200, min(200, round(change))))


def _window_mentions(df: pd.DataFrame, sku: str, days: int, offset_days: int = 0) -> int:
    if df.empty:
        return 0
    now = df['date'].max()
    end = now - pd.Timedelta(days=offset_days)
    start = end - pd.Timedelta(days=days)
    mask = (df['date'] > start) & (df['date'] <= end) & (df['sku'] == sku)
    return int(df.loc[mask, 'mentions'].sum())


def _window_mentions_for_keyword(df: pd.DataFrame, keyword: str, days: int, offset_days: int = 0) -> int:
    if not keyword or df.empty:
        return 0
    now = df['date'].max()
    end = now - pd.Timedelta(days=offset_days)
    start = end - pd.Timedelta(days=days)
    mask = (df['date'] > start) & (df['date'] <= end) & (df['title_hashtag'] == keyword)
    return int(df.loc[mask, 'mentions'].sum())


def _sku_keywords(df: pd.DataFrame, sku: str) -> list[str]:
    subset = df[(df['sku'] == sku) & df['title_hashtag'].astype(bool)]
    if subset.empty:
        return []
    summary = (
        subset.groupby('title_hashtag')['mentions'].sum().sort_values(ascending=False).head(3)
    )
    return summary.index.to_list()


def _sku_source_breakdown(df: pd.DataFrame, sku: str) -> list[dict]:
    subset = df[df['sku'] == sku]
    if subset.empty:
        return []
    carriers = subset.groupby('source')['mentions'].sum().sort_values(ascending=False)
    return [{'source': source, 'mentions': int(count)} for source, count in carriers.items()]


def _estimate_stockout(avg_units: float, trend_spike: int) -> str:
    if not avg_units or avg_units <= 0:
        return 'Unknown'
    if trend_spike >= 150:
        return '12 hours'
    if trend_spike >= 100:
        return '24 hours'
    if avg_units < 100:
        return '36 hours'
    return '3 days'


def _build_sku_mappings(social_df: pd.DataFrame, historic_df: pd.DataFrame) -> list[dict]:
    if social_df.empty and historic_df.empty:
        return []

    skus = set(historic_df['sku'].dropna().unique())
    skus.update(social_df['sku'].dropna().unique())
    baseline = max(1, int(social_df['mentions'].median()) if not social_df.empty else 50)
    result = []
    now = social_df['date'].max() if not social_df.empty else pd.Timestamp.now()

    for sku in sorted(skus):
        hist_subset = historic_df[historic_df['sku'] == sku]
        avg_units = hist_subset['units'].tail(14).mean() if not hist_subset.empty else 0
        mentions_total = int(social_df[social_df['sku'] == sku]['mentions'].sum())
        change24 = _pct_change(
            _window_mentions(social_df, sku, days=1, offset_days=0),
            _window_mentions(social_df, sku, days=1, offset_days=1),
        )
        change7 = _pct_change(
            _window_mentions(social_df, sku, days=7, offset_days=0),
            _window_mentions(social_df, sku, days=7, offset_days=7),
        )
        trend_spike = min(999, int(((mentions_total + 1) / baseline) * 100))
        score = min(0.98, 0.2 + (avg_units / 200) + (mentions_total / max(1, mentions_total + 300)))
        confidence = int(max(20, min(100, score * 100)))
        time_to_stockout = _estimate_stockout(avg_units, trend_spike)
        revenue_at_risk = max(0, int((1 - (confidence / 100)) * 200_000))
        keywords = _sku_keywords(social_df, sku)
        status = (
            'action_required'
            if trend_spike > 150 or change24 > 50
            else 'in_review'
            if change24 > 25 or change7 > 40
            else 'monitor'
        )
        mapping_label = f"{keywords[0]} → SKU #{sku}" if keywords else f"SKU #{sku}"
        result.append(
            {
                'id': sku,
                'sku': sku,
                'title': SKU_TITLES.get(sku, sku),
                'confidence': confidence,
                'score': round(confidence / 100, 2),
                'trendSpike': trend_spike,
                'trendChange24': change24,
                'trendChange7': change7,
                'timeUntilStockout': time_to_stockout,
                'revenueAtRisk': revenue_at_risk,
                'status': status,
                'keywords': keywords,
                'mapping': mapping_label,
                'lastUpdated': now.isoformat(),
                'sourceBreakdown': _sku_source_breakdown(social_df, sku),
                'mentions': mentions_total,
            }
        )
    return sorted(result, key=lambda row: row['trendSpike'], reverse=True)


def _build_keyword_trends(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    keywords = df[df['title_hashtag'].astype(bool)]['title_hashtag'].unique().tolist()
    summary = []
    for keyword in keywords:
        recent = _window_mentions_for_keyword(df, keyword, days=1, offset_days=0)
        previous = _window_mentions_for_keyword(df, keyword, days=1, offset_days=1)
        weekly = _window_mentions_for_keyword(df, keyword, days=7, offset_days=0)
        prev_week = _window_mentions_for_keyword(df, keyword, days=7, offset_days=7)
        keyword_rows = df[df['title_hashtag'] == keyword]
        source = keyword_rows['source'].mode().iloc[0] if not keyword_rows.empty else 'social'
        summary.append(
            {
                'keyword': keyword,
                'mentions': int(keyword_rows['mentions'].sum()),
                'change24': _pct_change(recent, previous),
                'change7': _pct_change(weekly, prev_week),
                'source': source,
                'confidence': min(100, 50 + _pct_change(weekly, prev_week) // 2),
            }
        )
    return sorted(summary, key=lambda item: item['mentions'], reverse=True)[:6]


def _build_signal_sources(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    now = df['date'].max()
    recent = df[df['date'] > now - pd.Timedelta(days=7)]
    previous = df[(df['date'] <= now - pd.Timedelta(days=7)) & (df['date'] > now - pd.Timedelta(days=14))]
    sources = []
    for source, total in df.groupby('source')['mentions'].sum().items():
        recent_val = int(recent[recent['source'] == source]['mentions'].sum())
        prev_val = int(previous[previous['source'] == source]['mentions'].sum())
        sources.append(
            {
                'name': source,
                'mentions': int(total),
                'change7': _pct_change(recent_val, prev_val),
            }
        )
    return sorted(sources, key=lambda item: item['mentions'], reverse=True)


@router.get('/trends')
def trends():
    social_df = _load_social()
    historic_df = _load_historic()
    mappings = _build_sku_mappings(social_df, historic_df)
    return {
        'trending_skus': mappings[:5],
        'trend_keywords': _build_keyword_trends(social_df),
        'signal_sources': _build_signal_sources(social_df),
        'last_updated': pd.Timestamp.now().isoformat(),
    }


@router.get('/sku-mapping')
def sku_mapping():
    social_df = _load_social()
    historic_df = _load_historic()
    return {'mappings': _build_sku_mappings(social_df, historic_df)}


@router.get('/signals')
def signals():
    df = _load_social()
    rows = []
    for i, r in df.iterrows():
        rows.append(
            {
                'id': int(i) + 1,
                'sku': r.get('sku', 'GS-019'),
                'source': r.get('source', 'TikTok'),
                'velocity': int(r.get('mentions', 0)) if r.get('mentions') is not None else 0,
                'keyword': r.get('hashtag', ''),
            }
        )
    return rows


@router.get('/signals/google')
def google_signals():
    df = _load_google_signals()
    rows = []
    for i, r in df.iterrows():
        rows.append(
            {
                'id': int(i) + 1,
                'sku': r.get('sku', 'GS-019'),
                'source': r.get('source', 'Google'),
                'velocity': int(r.get('mentions', 0)) if r.get('mentions') is not None else 0,
                'keyword': r.get('hashtag', ''),
                'timestamp': r.get('date').isoformat() if pd.notna(r.get('date')) else None,
            }
        )
    return rows


@router.get('/social')
def social(hashtag: str = None, top_n: int = 10):
    df = _load_social()
    rows = df.to_dict(orient='records')
    if hashtag:
        rows = [row for row in rows if row.get('hashtag') == hashtag]
    top = []
    if rows:
        hashtags = pd.DataFrame(rows)
        if 'hashtag' in hashtags.columns and not hashtags['hashtag'].empty:
            top = (
                hashtags['hashtag']
                .value_counts()
                .head(top_n)
                .rename_axis('hashtag')
                .reset_index(name='count')
                .to_dict(orient='records')
            )
    return {'rows': rows, 'top_hashtags': top}


@router.get('/sources')
def sources():
    df = _load_social()
    return (
        df.groupby('source')['mentions']
        .sum()
        .reset_index(name='value')
        .assign(color='hsl(var(--chart-1))')
        .to_dict(orient='records')
    )
