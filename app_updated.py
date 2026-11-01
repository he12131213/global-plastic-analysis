import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(
    page_title="플라스틱 생산·폐기 분석",
    page_icon="♻️",
    layout="wide"
)

PRODUCTION_FILE = "global-plastics-production.csv"
FATE_FILE = "plastic-fate.csv"

# 첨부 CSV의 수치 규모와 원자료 정의를 확인한 결과 두 세계 데이터는 톤(t) 단위다.
# 예: 2019년 세계 플라스틱 생산량 약 459,746,016톤.
# 따라서 kg -> tonne 변환을 적용하지 않고, 화면에서 백만 톤 단위로 환산해 표시한다.
WORLD_UNIT = "톤"
MILLION = 1_000_000

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

# 국내 플라스틱 폐기물 발생 및 처리 자료
# 출처: 통계청 SDG 이행보고서(2022), 환경부·한국환경공단
# "The amount of plastic waste generated and the share of each disposal type; 2010~2019"
# 발생량 단위: 톤/일, 처리 방식은 해당 연도 총 발생량 대비 비율(%)
# 2019년은 분류체계 변경 및 합성수지 통계 재분류에 유의.
KOREA_DATA = pd.DataFrame({
    "year": list(range(2010, 2020)),
    "total_ton_per_day": [3991, 3949, 4387, 4366, 4606, 4939, 5446, 5852, 6375, 9293],
    "재활용": [36.9, 35.3, 35.6, 35.3, 35.8, 35.0, 38.0, 40.7, 39.9, 48.8],
    "소각": [39.1, 42.8, 45.6, 45.8, 46.2, 47.0, 45.4, 43.9, 45.4, 38.3],
    "매립": [24.0, 21.9, 18.8, 18.9, 17.9, 18.0, 16.6, 15.4, 14.7, 11.7],
    "기타": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.1],
})
for method in ["재활용", "소각", "매립", "기타"]:
    KOREA_DATA[f"{method}_ton_per_day"] = (
        KOREA_DATA["total_ton_per_day"] * KOREA_DATA[method] / 100
    )

@st.cache_data
def load_data():
    production = pd.read_csv(PRODUCTION_FILE)
    fate = pd.read_csv(FATE_FILE)

    required_p = {"entity", "year", "plastic_production"}
    required_f = {"entity", "year", *FATE_COLUMNS.values()}
    if not required_p.issubset(production.columns):
        raise ValueError(f"생산량 파일 필수 컬럼 누락: {required_p - set(production.columns)}")
    if not required_f.issubset(fate.columns):
        raise ValueError(f"폐기물 파일 필수 컬럼 누락: {required_f - set(fate.columns)}")

    for df in [production, fate]:
        df["year"] = pd.to_numeric(df["year"], errors="coerce")
    production["plastic_production"] = pd.to_numeric(
        production["plastic_production"], errors="coerce"
    )
    for col in FATE_COLUMNS.values():
        fate[col] = pd.to_numeric(fate[col], errors="coerce")

    production = production[production["year"].between(2000, 2019)].copy()
    fate = fate[fate["year"].between(2000, 2019)].copy()

    production = production[
        production["entity"].astype(str).str.lower().eq("world")
    ][["year", "plastic_production"]].drop_duplicates("year").sort_values("year")

    # 연간 배수 = 해당 연도 생산량 / 전년도 생산량
    # 1.25배는 전년 생산량의 1.25배 수준이라는 뜻이다.
    production["production_increase"] = production["plastic_production"].diff()
    production["production_multiple"] = (
        production["plastic_production"] /
        production["plastic_production"].shift(1)
    )

    production["period_status"] = production["year"].apply(
        lambda y: "추정치 주의 구간(2015년 이후)" if y >= 2015 else "2015년 이전"
    )
    return production, fate.sort_values(["entity", "year"])

try:
    production, fate_all = load_data()
except Exception as exc:
    st.error(f"데이터를 불러오지 못했습니다: {exc}")
    st.info("CSV 파일 2개를 app.py와 같은 폴더에 넣고 실행하세요.")
    st.stop()

st.title("♻️ 플라스틱 생산량과 폐기물 처리 방식 분석")
st.caption("세계 자료 분석 기간: 2000~2019년 | 세계 자료 단위: 톤(t), 그래프 표시 단위: 백만 톤")

with st.sidebar:
    st.header("분석 설정")
    start_year, end_year = st.slider(
        "분석 기간 선택",
        min_value=2000,
        max_value=2019,
        value=(2000, 2019),
        step=1
    )
    entities = sorted(fate_all["entity"].dropna().unique().tolist())
    default_entity = "World" if "World" in entities else entities[0]
    target_entity = st.selectbox(
        "세계 폐기물 자료의 분석 대상",
        entities,
        index=entities.index(default_entity)
    )
    selected_methods = st.multiselect(
        "폐기물 처리 방식",
        options=list(FATE_COLUMNS.keys()),
        default=list(FATE_COLUMNS.keys())
    )

prod_view = production[
    production["year"].between(start_year, end_year)
].copy()
fate_view = fate_all[
    (fate_all["entity"] == target_entity) &
    (fate_all["year"].between(start_year, end_year))
].copy()

# 전년 대비 배수 계산 시 선택 시작 연도의 직전 연도도 함께 참조한다.
prod_with_previous = production[
    production["year"].between(max(2000, start_year - 1), end_year)
].copy()
prod_with_previous["production_increase"] = prod_with_previous["plastic_production"].diff()
prod_with_previous["production_multiple"] = (
    prod_with_previous["plastic_production"] /
    prod_with_previous["plastic_production"].shift(1)
)
prod_change_view = prod_with_previous[
    prod_with_previous["year"].between(start_year, end_year)
].copy()

def fmt(value, digits=2):
    return "자료 없음" if pd.isna(value) else f"{value:,.{digits}f}"

def add_period_background(fig, x0=start_year, x1=end_year):
    if x1 >= 2015:
        fig.add_vrect(
            x0=max(2015, x0) - 0.5,
            x1=x1 + 0.5,
            fillcolor="rgba(245, 166, 35, 0.12)",
            line_width=0,
            annotation_text="2015년 이후: 추정치 해석 주의",
            annotation_position="top left"
        )

# 공통 주의 문구
st.warning(
    "실측치·추정치 해석 주의: 2015년 이후의 생산량 자료는 추정치 구간으로 구분해 해석해야 합니다. "
    "2015년 이후 수치와 증가 추세를 확정적인 실측 변화로 단정하지 말고, 출처와 산정 방법의 차이를 고려하세요."
)

if target_entity == "World" and not prod_view.empty:
    latest = prod_view.dropna(subset=["plastic_production"]).iloc[-1]
    previous = prod_change_view[
        prod_change_view["year"] == latest["year"]
    ]
    last_multiple = previous["production_multiple"].iloc[0] if not previous.empty else float("nan")
    c1, c2, c3 = st.columns(3)
    c1.metric("선택 기간 마지막 생산량", f"{latest['plastic_production']/MILLION:,.2f} 백만 톤")
    c2.metric("전년 대비 증가량", f"{latest['production_increase']/MILLION:,.2f} 백만 톤" if pd.notna(latest["production_increase"]) else "자료 없음")
    c3.metric("전년 대비 생산량 배수", f"{last_multiple:.3f}배" if pd.notna(last_multiple) else "자료 없음")
else:
    st.info("생산량 CSV에는 세계(World) 자료만 포함되어 있어, 국가·지역별 생산량 비교는 제공되지 않습니다.")

st.header("1. 연도별 플라스틱 생산량 증가량과 전년 대비 배수")
if target_entity == "World" and not prod_change_view.empty:
    fig1 = make_subplots(specs=[[{"secondary_y": True}]])
    fig1.add_trace(
        go.Scatter(
            x=prod_change_view["year"],
            y=prod_change_view["production_increase"] / MILLION,
            mode="lines+markers",
            name="전년 대비 증가량",
            line=dict(color="#2878B5", width=3),
            connectgaps=False
        ),
        secondary_y=False
    )
    fig1.add_trace(
        go.Scatter(
            x=prod_change_view["year"],
            y=prod_change_view["production_multiple"],
            mode="lines+markers",
            name="전년 대비 생산량 배수",
            line=dict(color="#E07A2D", width=3, dash="dot"),
            connectgaps=False
        ),
        secondary_y=True
    )
    add_period_background(fig1)
    fig1.update_yaxes(title_text="증가량 (백만 톤)", secondary_y=False)
    fig1.update_yaxes(title_text="전년 대비 배수 (배)", secondary_y=True)
    fig1.update_layout(
        height=450,
        hovermode="x unified",
        legend=dict(orientation="h", y=1.13),
        xaxis_title="연도"
    )
    st.plotly_chart(fig1, use_container_width=True)
    st.caption(
        "배수는 해당 연도 생산량 ÷ 전년도 생산량으로 계산합니다. "
        "예를 들어 1.25배는 전년 생산량의 1.25배라는 의미입니다. "
        "선택 기간 시작 연도의 전년도 자료를 계산에만 참조해 첫 해의 배수도 계산합니다."
    )
else:
    st.info("세계(World)를 선택하면 생산량 그래프를 확인할 수 있습니다.")

st.header("2. 전년 대비 생산량 증가량이 가장 컸던 연도")
if target_entity == "World":
    delta = prod_change_view.dropna(subset=["production_increase"]).copy()
    if not delta.empty:
        delta["구간"] = delta["year"].apply(
            lambda y: "2015년 이후 추정치 주의 구간" if y >= 2015 else "2015년 이전"
        )
        fig2 = go.Figure()
        for label, color in [
            ("2015년 이전", "#4C78A8"),
            ("2015년 이후 추정치 주의 구간", "#F2A541")
        ]:
            part = delta[delta["구간"] == label]
            if not part.empty:
                fig2.add_trace(go.Bar(
                    x=part["year"],
                    y=part["production_increase"] / MILLION,
                    name=label,
                    marker_color=color,
                    hovertemplate="연도: %{x}<br>증가량: %{y:.2f} 백만 톤<extra></extra>"
                ))
        peak = delta.loc[delta["production_increase"].idxmax()]
        fig2.add_annotation(
            x=peak["year"],
            y=peak["production_increase"] / MILLION,
            text=f"최댓값: {int(peak['year'])}년<br>{peak['production_increase']/MILLION:.2f}백만 톤",
            showarrow=True,
            arrowhead=2
        )
        add_period_background(fig2)
        fig2.update_layout(
            barmode="overlay",
            height=430,
            xaxis_title="연도",
            yaxis_title="전년 대비 증가량 (백만 톤)",
            legend=dict(orientation="h", y=1.13)
        )
        st.plotly_chart(fig2, use_container_width=True)
        st.metric(
            "선택 기간 내 증가량 최댓값",
            f"{int(peak['year'])}년 · {peak['production_increase']/MILLION:,.2f} 백만 톤"
        )
        st.warning(
            "2015년 이후는 추정치 구간으로 구분했습니다. 이 구간의 증가량 최댓값은 "
            "실측치만으로 산출한 결과와 다를 수 있으므로, 2015년 이전 자료와 동일한 확실성을 가진 값으로 해석하지 마세요."
        )
    else:
        st.info("선택 기간에서 계산 가능한 증가량이 없습니다.")

st.header("3. 세계 플라스틱 폐기물의 처리 방식별 변화")
if not fate_view.empty and selected_methods:
    all_fate_cols = list(FATE_COLUMNS.values())
    fate_view["total_fate"] = fate_view[all_fate_cols].sum(axis=1, min_count=1)
    for method in selected_methods:
        col = FATE_COLUMNS[method]
        fate_view[f"{method}_share"] = (
            fate_view[col] / fate_view["total_fate"] * 100
        )

    st.subheader("3-1. 처리 방식별 양의 연도 추이")
    fig3 = go.Figure()
    for method in selected_methods:
        col = FATE_COLUMNS[method]
        fig3.add_trace(go.Scatter(
            x=fate_view["year"],
            y=fate_view[col] / MILLION,
            mode="lines+markers",
            name=method,
            line=dict(width=2.5, color=COLORS[method])
        ))
    add_period_background(fig3)
    fig3.update_layout(
        height=430,
        xaxis_title="연도",
        yaxis_title="처리량 (백만 톤)",
        hovermode="x unified"
    )
    st.plotly_chart(fig3, use_container_width=True)

    st.subheader("3-2. 처리 방식별 비율의 연도 추이")
    fig4 = go.Figure()
    for method in selected_methods:
        fig4.add_trace(go.Scatter(
            x=fate_view["year"],
            y=fate_view[f"{method}_share"],
            mode="lines+markers",
            name=method,
            line=dict(width=2.5, color=COLORS[method])
        ))
    add_period_background(fig4)
    fig4.update_layout(
        height=430,
        xaxis_title="연도",
        yaxis_title="4개 처리 방식 합계 중 비율 (%)",
        hovermode="x unified"
    )
    st.plotly_chart(fig4, use_container_width=True)
    st.caption(
        "비율은 재활용·소각·부적절한 처리·매립 4개 항목의 합계를 분모로 계산한 구성비입니다."
    )

    st.subheader(f"3-3. 같은 기간({start_year}~{end_year}년) 세계 플라스틱 폐기물 처리 방식별 양과 비율 변화")
    start_row = fate_view[fate_view["year"] == start_year]
    end_row = fate_view[fate_view["year"] == end_year]
    if not start_row.empty and not end_row.empty:
        total_start = float(start_row[all_fate_cols].sum(axis=1).iloc[0])
        total_end = float(end_row[all_fate_cols].sum(axis=1).iloc[0])
        rows = []
        for method in selected_methods:
            col = FATE_COLUMNS[method]
            amount_start = float(start_row[col].iloc[0])
            amount_end = float(end_row[col].iloc[0])
            share_start = amount_start / total_start * 100 if total_start else float("nan")
            share_end = amount_end / total_end * 100 if total_end else float("nan")
            rows.append({
                "처리 방식": method,
                f"{start_year}년 처리량(톤)": amount_start,
                f"{end_year}년 처리량(톤)": amount_end,
                "처리량 변화(톤)": amount_end - amount_start,
                f"{start_year}년 비율(%)": share_start,
                f"{end_year}년 비율(%)": share_end,
                "비율 변화(%p)": share_end - share_start
            })
        comparison = pd.DataFrame(rows)
        amount_start_col = f"{start_year}년 처리량(톤)"
        amount_end_col = f"{end_year}년 처리량(톤)"
        share_start_col = f"{start_year}년 비율(%)"
        share_end_col = f"{end_year}년 비율(%)"
        st.dataframe(
            comparison.style.format({
                amount_start_col: "{:,.0f}",
                amount_end_col: "{:,.0f}",
                "처리량 변화(톤)": "{:+,.0f}",
                share_start_col: "{:.2f}",
                share_end_col: "{:.2f}",
                "비율 변화(%p)": "{:+.2f}"
            }),
            use_container_width=True,
            hide_index=True
        )
        fig5 = go.Figure()
        fig5.add_trace(go.Bar(
            x=comparison["처리 방식"],
            y=comparison["비율 변화(%p)"],
            marker_color=[COLORS[m] for m in comparison["처리 방식"]],
            name="비율 변화"
        ))
        fig5.update_layout(
            height=350,
            xaxis_title="처리 방식",
            yaxis_title="비율 변화 (퍼센트포인트, %p)"
        )
        st.plotly_chart(fig5, use_container_width=True)
        st.caption(
            f"위 비교는 사이드바에서 선택한 {start_year}년과 {end_year}년을 기준으로 계산합니다. "
            "처리량 변화는 톤, 비율 변화는 퍼센트포인트(%p)입니다."
        )
    else:
        st.info("선택한 시작 연도 또는 종료 연도의 폐기물 자료가 없습니다.")
else:
    st.info("폐기물 처리 방식을 하나 이상 선택하거나 선택 대상의 자료를 확인하세요.")

st.header("4. 세계 플라스틱 생산량과 부적절한 처리의 연도별 관계")
if target_entity == "World" and not prod_view.empty and not fate_view.empty:
    relation = pd.merge(
        prod_view[["year", "plastic_production"]],
        fate_view[["year", "littered_mismanaged_combined"]],
        on="year",
        how="inner"
    ).dropna()
    if not relation.empty:
        st.subheader("4-1. 연도에 따른 두 지표의 추세")
        fig6 = make_subplots(specs=[[{"secondary_y": True}]])
        fig6.add_trace(go.Scatter(
            x=relation["year"],
            y=relation["plastic_production"] / MILLION,
            mode="lines+markers",
            name="플라스틱 생산량",
            line=dict(color="#2878B5", width=3)
        ), secondary_y=False)
        fig6.add_trace(go.Scatter(
            x=relation["year"],
            y=relation["littered_mismanaged_combined"] / MILLION,
            mode="lines+markers",
            name="부적절한 처리량",
            line=dict(color="#D55E00", width=3, dash="dash")
        ), secondary_y=True)
        add_period_background(fig6)
        fig6.update_yaxes(title_text="생산량 (백만 톤)", secondary_y=False)
        fig6.update_yaxes(title_text="부적절한 처리량 (백만 톤)", secondary_y=True)
        fig6.update_layout(
            height=440,
            hovermode="x unified",
            legend=dict(orientation="h", y=1.13),
            xaxis_title="연도"
        )
        st.plotly_chart(fig6, use_container_width=True)

        st.subheader("4-2. 생산량과 부적절한 처리량의 산점도")
        scatter = go.Figure()
        scatter.add_trace(go.Scatter(
            x=relation["plastic_production"] / MILLION,
            y=relation["littered_mismanaged_combined"] / MILLION,
            mode="markers+text",
            text=relation["year"].astype(int).astype(str),
            textposition="top center",
            marker=dict(
                size=10,
                color=relation["year"],
                colorscale="Viridis",
                showscale=True,
                colorbar=dict(title="연도")
            ),
            customdata=relation[["year"]].to_numpy(),
            hovertemplate=(
                "연도: %{customdata[0]}년<br>"
                "생산량: %{x:,.2f} 백만 톤<br>"
                "부적절한 처리량: %{y:,.2f} 백만 톤<extra></extra>"
            ),
            name="연도별 자료"
        ))
        scatter.update_layout(
            height=500,
            xaxis_title="연간 플라스틱 생산량 (백만 톤)",
            yaxis_title="부적절한 처리량 (백만 톤)"
        )
        st.plotly_chart(scatter, use_container_width=True)
        st.caption(
            "각 점은 한 해를 나타내며 점의 색과 라벨로 연도를 구분합니다. "
            "두 값은 서로 다른 지표이므로 직접 빼지 않으며, 산점도는 두 변수의 동반 변화 관계를 살펴보는 용도입니다."
        )
    else:
        st.info("선택 기간에 두 자료가 겹치는 연도가 없습니다.")
else:
    st.info("생산량과 부적절한 처리량의 관계는 두 자료 모두 세계(World)일 때 표시됩니다.")

st.warning(
    "부적절한 처리(littered/mismanaged)는 관리되지 않거나 부적절하게 처리된 폐기물의 추정량입니다. "
    "이 양 전체가 실제 자연환경으로 유출되었다는 뜻은 아니며, 실제 환경 유출량과 동일시해서는 안 됩니다."
)

st.header("5. 국내 플라스틱 폐기물 자료와 해결 방안 탐색")
korea_view = KOREA_DATA[
    KOREA_DATA["year"].between(start_year, end_year)
].copy()
if not korea_view.empty:
    st.markdown(
        f"국내 플라스틱 폐기물 발생량과 처리 방식 자료는 **{int(korea_view['year'].min())}~"
        f"{int(korea_view['year'].max())}년** 범위에서 제공됩니다. "
        "국내 자료의 발생량 단위는 톤/일이며, 세계 자료의 연간 톤(t)과 시간 단위가 다릅니다."
    )
    st.subheader("5-1. 국내 플라스틱 폐기물 발생량")
    fig7 = go.Figure()
    fig7.add_trace(go.Scatter(
        x=korea_view["year"],
        y=korea_view["total_ton_per_day"],
        mode="lines+markers",
        name="국내 플라스틱 폐기물 발생량",
        line=dict(color="#2878B5", width=3)
    ))
    fig7.update_layout(
        height=380,
        xaxis_title="연도",
        yaxis_title="발생량 (톤/일)"
    )
    st.plotly_chart(fig7, use_container_width=True)

    st.subheader("5-2. 국내 처리 방식별 비율")
    fig8 = go.Figure()
    for method, color in [
        ("재활용", COLORS["재활용"]),
        ("소각", COLORS["소각"]),
        ("매립", COLORS["매립"]),
        ("기타", "#888888")
    ]:
        fig8.add_trace(go.Scatter(
            x=korea_view["year"],
            y=korea_view[method],
            mode="lines+markers",
            name=method,
            line=dict(width=2.5, color=color)
        ))
    fig8.update_layout(
        height=420,
        xaxis_title="연도",
        yaxis_title="처리 방식 비율 (%)",
        hovermode="x unified"
    )
    st.plotly_chart(fig8, use_container_width=True)

    st.subheader("5-3. 국내 처리 방식별 추정 처리량")
    fig9 = go.Figure()
    for method, color in [
        ("재활용", COLORS["재활용"]),
        ("소각", COLORS["소각"]),
        ("매립", COLORS["매립"]),
        ("기타", "#888888")
    ]:
        fig9.add_trace(go.Scatter(
            x=korea_view["year"],
            y=korea_view[f"{method}_ton_per_day"],
            mode="lines+markers",
            name=method,
            line=dict(width=2.5, color=color)
        ))
    fig9.update_layout(
        height=420,
        xaxis_title="연도",
        yaxis_title="처리량 (톤/일)",
        hovermode="x unified"
    )
    st.plotly_chart(fig9, use_container_width=True)

    first_k = korea_view.iloc[0]
    last_k = korea_view.iloc[-1]
    st.markdown("#### 국내 자료를 바탕으로 생각해 볼 해결 방안")
    st.markdown(
        f"- 선택 기간의 국내 플라스틱 폐기물 발생량은 {first_k['year']}년 "
        f"{first_k['total_ton_per_day']:,.0f}톤/일에서 {last_k['year']}년 "
        f"{last_k['total_ton_per_day']:,.0f}톤/일로 변화했습니다."
    )
    st.markdown(
        f"- 마지막 연도 재활용 비율은 {last_k['재활용']:.1f}%입니다. "
        "재활용률을 높이는 것과 함께 실제 재생원료로 다시 사용되는 물질 재활용의 질을 높일 필요가 있습니다."
    )
    st.markdown(
        f"- 마지막 연도 소각 비율은 {last_k['소각']:.1f}%입니다. "
        "일회용 플라스틱 감량, 다회용 제품 전환, 재사용 체계 확대를 통해 소각으로 향하는 폐기물 자체를 줄이는 방안을 검토할 수 있습니다."
    )
    st.markdown(
        f"- 마지막 연도 매립 비율은 {last_k['매립']:.1f}%입니다. "
        "분리배출 품질 개선과 재활용이 어려운 복합재질의 대체·설계 개선도 함께 고려할 수 있습니다."
    )
    st.warning(
        "국내 시계열 해석 주의: 2016년에는 발포폴리스티렌(EPS)이 재활용 통계에 새로 포함되었습니다. "
        "2019년에는 플라스틱과 폐합성수지의 분류·집계 방식이 달라졌습니다. "
        "따라서 특히 2019년의 급격한 발생량 증가는 실제 발생 증가뿐 아니라 분류·집계 기준 변화의 영향도 고려해야 합니다."
    )
else:
    st.info("국내 플라스틱 자료는 2010~2019년만 제공되어 선택한 분석 기간과 겹치는 연도가 없습니다.")

with st.expander("데이터 출처 및 계산 기준"):
    st.markdown("""
    **세계 생산량 및 폐기물 자료**
    - 파일: `global-plastics-production.csv`, `plastic-fate.csv`
    - 분석 기간: 2000~2019년
    - 단위 확인: 원자료의 생산량·처리량 수치는 톤(t) 단위로 취급합니다. kg 단위로 잘못 해석하거나 1,000으로 나누지 않습니다.
    - 화면의 대규모 수치는 백만 톤(원자료 값 ÷ 1,000,000)으로 표시합니다.
    - 생산량 증가량 = 해당 연도 생산량 − 전년도 생산량
    - 전년 대비 배수 = 해당 연도 생산량 ÷ 전년도 생산량
    - 폐기물 처리 비율 = 해당 처리 방식의 양 ÷ 네 처리 방식 합계 × 100
    - 비율 변화 = 종료 연도 비율 − 시작 연도 비율(%p)

    **국내 플라스틱 폐기물 자료**
    - 출처: 통계청 SDG 이행보고서(2022), 환경부·한국환경공단 「전국 폐기물 발생 및 처리현황」
    - 수록 기간: 2010~2019년
    - 발생량 단위: 톤/일
    - 처리 방식별 양은 발생량에 처리 비율을 곱해 계산한 추정 환산값입니다.
    - 2016년 EPS 재활용 분류 포함, 2019년 플라스틱·폐합성수지 분류 변경에 유의합니다.
    """)
    st.markdown(
        "국내 자료 원문: "
        "[통계청 SDG 이행보고서 자료(PDF)](https://mods.go.kr/boardDownload.es?bid=12317&list_no=417859&seq=2)"
    )
    st.markdown(
        "세계 자료 참고: "
        "[Our World in Data - Plastic Pollution](https://ourworldindata.org/plastic-pollution)"
    )

    st.write("현재 선택한 세계 폐기물 원자료")
    st.dataframe(fate_view, use_container_width=True, hide_index=True)

st.caption(
    "세계 자료: 2000~2019년 · 톤(t) | 국내 자료: 2010~2019년 · 톤/일 | "
    "자료 정의와 분류체계 차이에 유의하세요."
)
