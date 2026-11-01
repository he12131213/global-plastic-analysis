import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="세계 플라스틱 생산·폐기 분석", page_icon="♻️", layout="wide")

PRODUCTION_FILE = "global-plastics-production.csv"
FATE_FILE = "plastic-fate.csv"

FATE_COLUMNS = {
    "재활용": "value_recycled",
    "소각": "value_incinerated",
    "부적절한 처리": "littered_mismanaged_combined",
    "매립": "value_landfilled",
}
COLORS = {
    "재활용": "#2E8B57",
    "소각": "#E69F00",
    "부적절한 처리": "#D55E00",
    "매립": "#4C78A8",
}

@st.cache_data
def load_data():
    production = pd.read_csv(PRODUCTION_FILE)
    fate = pd.read_csv(FATE_FILE)

    required_p = {"entity", "year", "plastic_production"}
    required_f = {"entity", "year", *FATE_COLUMNS.values()}
    if not required_p.issubset(production.columns):
        raise ValueError(f"생산량 파일에 필요한 컬럼이 없습니다: {required_p - set(production.columns)}")
    if not required_f.issubset(fate.columns):
        raise ValueError(f"폐기물 파일에 필요한 컬럼이 없습니다: {required_f - set(fate.columns)}")

    production["year"] = pd.to_numeric(production["year"], errors="coerce")
    fate["year"] = pd.to_numeric(fate["year"], errors="coerce")
    production["plastic_production"] = pd.to_numeric(production["plastic_production"], errors="coerce")
    for col in FATE_COLUMNS.values():
        fate[col] = pd.to_numeric(fate[col], errors="coerce")

    # 요청한 공통 기간(2000~2019)으로 맞춘다.
    production = production[production["year"].between(2000, 2019)].copy()
    fate = fate[fate["year"].between(2000, 2019)].copy()

    # 생산량 자료는 세계(World)만 제공된다.
    production = production[production["entity"].astype(str).str.lower().eq("world")]
    production = production[["year", "plastic_production"]].drop_duplicates("year")

    # 연도별 증감량·증가율 계산. 2000년은 전년도 값이 없으므로 결측치.
    production = production.sort_values("year")
    production["production_increase"] = production["plastic_production"].diff()
    production["production_growth_pct"] = (
        production["production_increase"] / production["plastic_production"].shift(1) * 100
    )
    # 파일에 추정치 플래그가 없으므로, 사용자가 지정한 2015년 이후 구간은
    # '추정/산정 기준 변경 주의 구간'으로 표시하되 확정적인 실측/추정 판정은 하지 않는다.
    production["estimate_status"] = production["year"].apply(
        lambda y: "추정·출처/산정 기준 변경 주의 구간" if y >= 2015 else "자료상 별도 표시 없음"
    )

    fate["estimate_status"] = "원자료에 실측/추정 구분 메타데이터 없음"
    fate = fate.sort_values(["entity", "year"])
    return production, fate

try:
    production, fate_all = load_data()
except Exception as exc:
    st.error(f"데이터를 불러오지 못했습니다: {exc}")
    st.info("두 CSV 파일을 이 파이썬 파일과 같은 폴더에 두고 실행하세요.")
    st.stop()

st.title("♻️ 플라스틱 생산량과 폐기물 처리 방식 분석")
st.caption("분석 기간: 2000~2019년 | 단위: 원자료 기준(톤으로 해석되는 질량 단위)")

with st.sidebar:
    st.header("분석 설정")
    min_year, max_year = 2000, 2019
    start_year, end_year = st.slider(
        "분석 기간 선택",
        min_value=min_year, max_value=max_year,
        value=(min_year, max_year), step=1
    )
    entities = sorted(fate_all["entity"].dropna().unique().tolist())
    default_entity = "World" if "World" in entities else entities[0]
    target_entity = st.selectbox("분석 대상(국가·지역)", entities, index=entities.index(default_entity))
    selected_methods = st.multiselect(
        "폐기물 처리 방식",
        options=list(FATE_COLUMNS.keys()),
        default=list(FATE_COLUMNS.keys())
    )
    st.caption("생산량 자료는 세계(World) 자료만 포함합니다. 다른 국가·지역을 선택하면 해당 대상의 폐기물 처리 자료만 분석합니다.")

years = list(range(start_year, end_year + 1))
prod_view = production[production["year"].between(start_year, end_year)].copy()
fate_view = fate_all[
    (fate_all["entity"] == target_entity) &
    (fate_all["year"].between(start_year, end_year))
].copy()

def format_tonnes(value):
    if pd.isna(value):
        return "자료 없음"
    return f"{value:,.0f}"

if start_year >= end_year:
    st.warning("전년 대비 변화와 2000년·2019년 비교를 보려면 분석 기간을 2개 연도 이상으로 설정하세요.")

# 핵심 요약
if target_entity == "World" and not prod_view.empty:
    latest = prod_view.dropna(subset=["plastic_production"]).iloc[-1]
    c1, c2, c3 = st.columns(3)
    c1.metric("선택 기간 마지막 생산량", f"{latest['plastic_production']/1e6:,.1f} 백만 톤")
    c2.metric("전년 대비 증가량", format_tonnes(latest["production_increase"]) + " 톤")
    c3.metric("전년 대비 증가율", "자료 없음" if pd.isna(latest["production_growth_pct"]) else f"{latest['production_growth_pct']:.2f}%")
else:
    st.info("현재 생산량 파일은 세계(World) 자료만 제공하므로, 선택한 국가·지역의 생산량과 폐기물 처리량을 직접 비교하지 않습니다.")

st.header("1. 연도별 플라스틱 생산량 증가량과 증가율")
if target_entity == "World" and not prod_view.empty:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(
        x=prod_view["year"], y=prod_view["production_increase"] / 1e6,
        mode="lines+markers", name="전년 대비 증가량",
        line=dict(color="#2878B5", width=3),
        connectgaps=False
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=prod_view["year"], y=prod_view["production_growth_pct"],
        mode="lines+markers", name="전년 대비 증가율",
        line=dict(color="#E07A2D", width=3, dash="dot"),
        connectgaps=False
    ), secondary_y=True)
    fig.update_yaxes(title_text="증가량 (백만 톤)", secondary_y=False)
    fig.update_yaxes(title_text="증가율 (%)", secondary_y=True)
    fig.update_layout(height=430, hovermode="x unified", legend=dict(orientation="h", y=1.12))
    st.plotly_chart(fig, use_container_width=True)
    st.caption("2000년은 1999년 값이 분석 범위에 없어 전년 대비 증가량·증가율을 계산하지 않습니다.")
else:
    st.info("세계 생산량 자료가 없으므로 이 그래프는 세계(World)를 선택했을 때 표시됩니다.")

st.header("2. 전년 대비 생산량 증가량이 가장 컸던 연도")
if target_entity == "World" and not prod_view.empty:
    delta = prod_view.dropna(subset=["production_increase"]).copy()
    if not delta.empty:
        # 2015년 이전/이후를 구분해 색상과 주석으로 표시
        delta["구간"] = delta["year"].apply(lambda y: "2015년 이후(추정·출처/산정 기준 변경 주의)" if y >= 2015 else "2015년 이전")
        fig2 = go.Figure()
        for label, color in [("2015년 이전", "#4C78A8"), ("2015년 이후(추정·출처/산정 기준 변경 주의)", "#F2A541")]:
            part = delta[delta["구간"] == label]
            if not part.empty:
                fig2.add_trace(go.Bar(
                    x=part["year"], y=part["production_increase"] / 1e6,
                    name=label, marker_color=color,
                    hovertemplate="연도: %{x}<br>증가량: %{y:.2f} 백만 톤<extra></extra>"
                ))
        peak = delta.loc[delta["production_increase"].idxmax()]
        fig2.add_annotation(
            x=peak["year"], y=peak["production_increase"] / 1e6,
            text=f"최댓값: {peak['year']}년<br>{peak['production_increase']/1e6:.2f}백만 톤",
            showarrow=True, arrowhead=2
        )
        fig2.update_layout(
            barmode="overlay", height=420, xaxis_title="연도",
            yaxis_title="전년 대비 증가량 (백만 톤)",
            legend=dict(orientation="h", y=1.12)
        )
        st.plotly_chart(fig2, use_container_width=True)
        st.metric("선택 기간 내 증가량 최댓값", f"{int(peak['year'])}년 · {peak['production_increase']/1e6:,.2f} 백만 톤")
        st.warning(
            "2015년 이후 값은 원자료에 실측/추정 플래그가 제공되지 않아 확정적으로 추정치라고 단정할 수 없습니다. "
            "다만 요청에 따라 2015년을 경계로 별도 색상 표시했으며, 출처·산정 기준 변화 가능성을 고려해 "
            "2015년 이전 구간과 단순히 같은 조건의 연속 관측값처럼 해석하지 않도록 주의해야 합니다."
        )
    else:
        st.info("선택한 기간에서 계산 가능한 전년 대비 증가량이 없습니다.")

st.header("3. 폐기물 처리 방식의 장기 변화")
if not fate_view.empty and selected_methods:
    available_methods = [m for m in selected_methods if FATE_COLUMNS[m] in fate_view.columns]
    # 처리 방식별 원자료 값 및 전체 처리량 대비 비율
    value_cols = list(FATE_COLUMNS.values())
    fate_view["total_fate"] = fate_view[value_cols].sum(axis=1, min_count=1)
    for method in available_methods:
        col = FATE_COLUMNS[method]
        fate_view[f"{method}_share"] = fate_view[col] / fate_view["total_fate"] * 100

    st.subheader("3-1. 처리 방식별 연도 추이")
    fig3 = go.Figure()
    for method in available_methods:
        col = FATE_COLUMNS[method]
        fig3.add_trace(go.Scatter(
            x=fate_view["year"], y=fate_view[col] / 1e6,
            mode="lines+markers", name=f"{method} (백만 톤)",
            line=dict(width=2.5, color=COLORS[method])
        ))
    fig3.update_layout(height=430, xaxis_title="연도", yaxis_title="처리량 (백만 톤)", hovermode="x unified")
    st.plotly_chart(fig3, use_container_width=True)

    st.subheader("3-2. 처리 방식별 비율 추이")
    fig4 = go.Figure()
    for method in available_methods:
        fig4.add_trace(go.Scatter(
            x=fate_view["year"], y=fate_view[f"{method}_share"],
            mode="lines+markers", name=method,
            line=dict(width=2.5, color=COLORS[method])
        ))
    fig4.update_layout(height=430, xaxis_title="연도", yaxis_title="해당 연도 처리 방식 합계 중 비율 (%)", hovermode="x unified")
    st.plotly_chart(fig4, use_container_width=True)
    st.caption("비율은 재활용·소각·부적절한 처리·매립 4개 항목의 합계를 분모로 계산한 구성비입니다.")

    st.subheader("3-3. 2000년과 2019년 비교")
    first = fate_all[(fate_all["entity"] == target_entity) & (fate_all["year"] == 2000)]
    last = fate_all[(fate_all["entity"] == target_entity) & (fate_all["year"] == 2019)]
    if not first.empty and not last.empty:
        rows = []
        first_total = first[list(FATE_COLUMNS.values())].sum(axis=1).iloc[0]
        last_total = last[list(FATE_COLUMNS.values())].sum(axis=1).iloc[0]
        for method in available_methods:
            col = FATE_COLUMNS[method]
            v0, v1 = float(first[col].iloc[0]), float(last[col].iloc[0])
            s0 = v0 / first_total * 100 if first_total else float("nan")
            s1 = v1 / last_total * 100 if last_total else float("nan")
            rows.append({
                "처리 방식": method,
                "2000년 처리량": v0,
                "2019년 처리량": v1,
                "처리량 변화(2019-2000)": v1-v0,
                "2000년 비율(%)": s0,
                "2019년 비율(%)": s1,
                "비율 변화(%p)": s1-s0,
            })
        comparison = pd.DataFrame(rows)
        st.dataframe(
            comparison.style.format({
                "2000년 처리량": "{:,.0f}", "2019년 처리량": "{:,.0f}",
                "처리량 변화(2019-2000)": "{:+,.0f}",
                "2000년 비율(%)": "{:.2f}", "2019년 비율(%)": "{:.2f}",
                "비율 변화(%p)": "{:+.2f}",
            }),
            use_container_width=True, hide_index=True
        )
        fig5 = go.Figure()
        fig5.add_trace(go.Bar(
            x=comparison["처리 방식"], y=comparison["비율 변화(%p)"],
            marker_color=[COLORS[x] for x in comparison["처리 방식"]],
            name="비율 변화"
        ))
        fig5.update_layout(height=350, yaxis_title="비율 변화 (퍼센트포인트, %p)", xaxis_title="처리 방식")
        st.plotly_chart(fig5, use_container_width=True)
    else:
        st.info("원자료에 2000년 또는 2019년 값이 없어 장기 비교를 표시할 수 없습니다.")
else:
    st.info("폐기물 처리 방식을 하나 이상 선택하거나, 선택한 대상의 데이터가 있는지 확인하세요.")

st.header("4. 플라스틱 생산량과 부적절한 처리의 연도별 비교")
if target_entity == "World" and not prod_view.empty and not fate_view.empty:
    relation = pd.merge(
        prod_view[["year", "plastic_production"]],
        fate_view[["year", "littered_mismanaged_combined"]],
        on="year", how="inner"
    )
    if not relation.empty:
        fig6 = make_subplots(specs=[[{"secondary_y": True}]])
        fig6.add_trace(go.Scatter(
            x=relation["year"], y=relation["plastic_production"]/1e6,
            mode="lines+markers", name="플라스틱 생산량",
            line=dict(color="#2878B5", width=3)
        ), secondary_y=False)
        fig6.add_trace(go.Scatter(
            x=relation["year"], y=relation["littered_mismanaged_combined"]/1e6,
            mode="lines+markers", name="부적절한 처리량",
            line=dict(color="#D55E00", width=3, dash="dash")
        ), secondary_y=True)
        fig6.update_yaxes(title_text="생산량 (백만 톤)", secondary_y=False)
        fig6.update_yaxes(title_text="부적절한 처리량 (백만 톤)", secondary_y=True)
        fig6.update_layout(height=440, hovermode="x unified", legend=dict(orientation="h", y=1.12))
        st.plotly_chart(fig6, use_container_width=True)
        st.caption("두 지표는 서로 다른 개념과 값이므로 직접 빼거나 동일한 양으로 간주하지 않습니다. 이 그래프는 연도에 따른 추세를 비교하며, 이중 축을 사용합니다.")
    else:
        st.info("선택 기간에 두 자료가 겹치는 연도가 없습니다.")
else:
    st.info("생산량과 부적절한 처리량의 비교는 두 파일 모두 세계(World) 자료가 있을 때만 표시됩니다.")

st.warning(
    "해석 유의사항: '부적절한 처리(littered/mismanaged)'는 관리되지 않거나 부적절하게 처리된 폐기물의 추정량을 뜻하며, "
    "그 전량이 실제 자연환경으로 유출되었다는 의미는 아닙니다. 실제 환경 유출량과 동일시하지 마세요."
)

with st.expander("데이터 및 계산 기준"):
    st.markdown("""
    - 두 파일을 연도 기준으로 **2000~2019년**에 맞춘 뒤 결합합니다.
    - 생산량 자료는 `World` 행만 사용합니다. 폐기물 자료는 사이드바에서 선택한 국가·지역을 사용합니다.
    - 생산량 증가량 = 해당 연도 생산량 − 전년도 생산량
    - 생산량 증가율(%) = 증가량 ÷ 전년도 생산량 × 100
    - 폐기물 처리 방식 비율 = 해당 방식 처리량 ÷ (재활용+소각+부적절한 처리+매립) × 100
    - 비율 변화는 2019년 비율 − 2000년 비율이며, 단위는 퍼센트포인트(%p)입니다.
    - CSV 파일에는 실측/추정 여부 메타데이터가 포함되어 있지 않습니다. 따라서 2015년 이후는 사용자가 요청한 주의 구간으로 표시하며, 추정치 여부를 확정 판정하지 않습니다.
    """)
    st.write("현재 선택한 폐기물 자료의 원본 데이터")
    st.dataframe(fate_view, use_container_width=True, hide_index=True)

st.caption("분석 범위: 2000~2019년 | 자료의 결측치·정의·산정 방식 차이에 유의하세요.")
