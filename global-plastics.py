import streamlit as st
import pandas as pd
import plotly.graph_objects as go

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
    production["production_growth_rate"] = (
        production["production_increase"] /
        production["plastic_production"].shift(1) * 100
    )

    production["period_status"] = production["year"].apply(
        lambda y: "추정치 주의 구간(2016–2018년)" if 2016 <= y <= 2018 else "실측 자료 구간"
    )
    return production, fate.sort_values(["entity", "year"])

try:
    production, fate_all = load_data()
except Exception as exc:
    st.error(f"데이터를 불러오지 못했습니다: {exc}")
    st.info("CSV 파일 2개를 app.py와 같은 폴더에 넣고 실행하세요.")
    st.stop()

st.title("♻️ 플라스틱 생산량과 폐기물 처리 방식 분석")
st.caption("세계 자료 분석 기간: 2000–2019년 | 세계 자료 단위: 톤(t), 그래프 표시 단위: 백만 톤")

with st.expander("연구 질문과 분석 가설", expanded=True):
    st.markdown("""
    **연구 주제:** 세계 플라스틱 생산량의 장기적 변화와 플라스틱 폐기물 처리 방식의 관계 분석

    - **큰 질문:** 지난 20년 동안 플라스틱 생산량은 어떻게 변했을까?
    - **작은 질문 ①:** 2000~2019년 세계 플라스틱 생산량은 몇 톤 증가했고, 몇 배가 되었을까?
    - **작은 질문 ②:** 2000~2019년 중 세계 플라스틱 생산량이 전년보다 가장 크게 증가한 시기는 언제일까?
    - **작은 질문 ③(선택):** 같은 기간 세계 플라스틱 폐기물의 처리 방식별 양과 비율은 어떻게 변했을까?

    **분석 가설:** 세계 플라스틱 생산량은 장기적으로 증가했을 것이다. 폐기물 처리 방식별 양과 비율도 변화했을 것이며, 생산량과 부적절한 처리량이 함께 증가하는 양상이 나타날 수 있다. 다만 함께 증가하는 양상만으로 인과관계를 단정하지 않는다.
    """)

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
prod_with_previous["production_growth_rate"] = (
    prod_with_previous["production_increase"] /
    prod_with_previous["plastic_production"].shift(1) * 100
)
prod_change_view = prod_with_previous[
    prod_with_previous["year"].between(start_year, end_year)
].copy()

def fmt(value, digits=2):
    return "자료 없음" if pd.isna(value) else f"{value:,.{digits}f}"

def add_production_estimate_background(fig, x0=start_year, x1=end_year):
    """생산량 자료의 추정 구간(2016–2018년)에만 음영을 표시한다."""
    left = max(2016, int(x0))
    right = min(2018, int(x1))
    if left <= right:
        fig.add_vrect(
            x0=left - 0.5,
            x1=right + 0.5,
            fillcolor="rgba(245, 166, 35, 0.12)",
            line_width=0,
            annotation_text="2016–2018년 추정치",
            annotation_position="top left"
        )

# 공통 주의 문구
st.warning(
    "생산량 자료 해석 주의: 2015년은 Geyer 논문의 실측값이며, 2016~2018년은 추정치입니다. "
    "추정치 구간의 수치와 증가 추세를 확정적인 실측 변화로 단정하지 말고 출처와 산정 방법을 고려하세요."
)

with st.expander("데이터 전처리 및 분석 범위 확인"):
    st.markdown("""
    - 두 CSV에서 연도 열을 숫자형으로 변환하고 2000~2019년 자료만 사용합니다.
    - 생산량은 세계(World) 행만 추출하며, 폐기물 자료는 사이드바에서 선택한 분석 대상의 행만 사용합니다.
    - 생산량과 폐기물 자료의 연도가 다를 수 있으므로 관계 분석에서는 연도를 기준으로 내부 결합(inner join)하여 두 자료가 모두 있는 해만 비교합니다.
    - 생산량 증가량은 해당 연도 값에서 전년도 값을 뺀 값이며, 증가율은 증가량을 전년도 값으로 나누어 백분율로 나타냅니다.
    - 처리 방식 비율은 재활용·소각·부적절한 처리·매립 네 항목의 합계를 분모로 계산합니다.
    - 누락된 수치가 있는 해는 그래프에서 결측으로 남기며, 임의로 0으로 대체하지 않습니다. 중복 연도는 첫 번째 행만 남깁니다.
    - 생산량의 2016~2018년은 추정치로 표시하고, 폐기물 자료에는 이 추정 구간 음영을 적용하지 않습니다.
    """)

if target_entity == "World" and not prod_view.empty:
    valid_period = prod_view.dropna(subset=["plastic_production"]).sort_values("year")
    first_row = valid_period.iloc[0]
    last_row = valid_period.iloc[-1]
    period_increase = last_row["plastic_production"] - first_row["plastic_production"]
    period_multiple = (
        last_row["plastic_production"] / first_row["plastic_production"]
        if first_row["plastic_production"] else float("nan")
    )
    c1, c2, c3 = st.columns(3)
    c1.metric("선택 기간 마지막 생산량", f"{last_row['plastic_production']/MILLION:,.2f} 백만 톤")
    c2.metric("선택 기간 생산량 증가량", f"{period_increase/MILLION:+,.2f} 백만 톤")
    c3.metric("첫해 대비 마지막 해 생산량 배수", f"{period_multiple:.3f}배" if pd.notna(period_multiple) else "자료 없음")
    st.caption(
        f"{int(first_row['year'])}년에서 {int(last_row['year'])}년까지의 생산량을 비교한 값입니다. "
        "증가량은 마지막 해 생산량−첫해 생산량, 배수는 마지막 해 생산량÷첫해 생산량입니다."
    )
else:
    st.info("생산량 CSV에는 세계(World) 자료만 포함되어 있어, 국가·지역별 생산량 비교는 제공되지 않습니다.")

st.header("1. 연도별 플라스틱 생산량 변화")
if target_entity == "World" and not prod_view.empty:
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(
        x=prod_view["year"],
        y=prod_view["plastic_production"] / MILLION,
        mode="lines+markers",
        name="연간 플라스틱 생산량",
        line=dict(color="#2878B5", width=3),
        connectgaps=False,
        hovertemplate="연도: %{x}년<br>생산량: %{y:,.2f} 백만 톤<extra></extra>"
    ))
    add_production_estimate_background(fig1)
    fig1.update_layout(
        height=450,
        hovermode="x unified",
        xaxis_title="연도",
        yaxis_title="연간 플라스틱 생산량 (백만 톤)"
    )
    st.plotly_chart(fig1, use_container_width=True)
    st.caption(
        "① 선택 기간의 첫해와 마지막 해 생산량을 비교하고, 연도별 생산량 자체의 변화를 확인합니다. "
        "2015년은 실측값이며 2016–2018년은 추정치로 음영 처리했습니다."
    )
else:
    st.info("세계(World)를 선택하면 생산량 그래프를 확인할 수 있습니다.")

st.header("2. 전년 대비 생산량 증가량이 가장 컸던 연도")
if target_entity == "World":
    delta = prod_change_view.dropna(subset=["production_increase"]).copy()
    if not delta.empty:
        delta["구간"] = delta["year"].apply(
            lambda y: "2016–2018년 추정치" if 2016 <= y <= 2018 else "실측 자료 구간"
        )
        fig2 = go.Figure()
        for label, color in [
            ("실측 자료 구간", "#4C78A8"),
            ("2016–2018년 추정치", "#F2A541")
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
        add_production_estimate_background(fig2)
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
        st.markdown("**연도별 생산량 증가량 순위**")
        ranking = delta[["year", "production_increase", "production_growth_rate"]].copy()
        ranking = ranking.sort_values("production_increase", ascending=False)
        ranking = ranking.rename(columns={
            "year": "연도",
            "production_increase": "전년 대비 증가량(백만 톤)",
            "production_growth_rate": "전년 대비 증가율(%)"
        })
        ranking["전년 대비 증가량(백만 톤)"] /= MILLION
        ranking["연도"] = ranking["연도"].astype(int)
        st.dataframe(
            ranking.style.format({
                "전년 대비 증가량(백만 톤)": "{:+,.2f}",
                "전년 대비 증가율(%)": "{:+.2f}%"
            }),
            use_container_width=True,
            hide_index=True
        )
        st.warning(
            "2016–2018년은 추정치 구간으로 구분했습니다. 이 구간의 증가량 최댓값은 "
            "실측치만으로 산출한 결과와 다를 수 있으므로 확정적인 실측 변화로 해석하지 마세요."
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
                f"{start_year}년 처리량(백만 톤)": amount_start / MILLION,
                f"{end_year}년 처리량(백만 톤)": amount_end / MILLION,
                "처리량 변화(백만 톤)": (amount_end - amount_start) / MILLION,
                f"{start_year}년 비율(%)": share_start,
                f"{end_year}년 비율(%)": share_end,
                "비율 변화(%p)": share_end - share_start,
                "비율 변화율(%)": (
                    (share_end - share_start) / share_start * 100
                    if pd.notna(share_start) and share_start != 0
                    else float("nan")
                ),
                "변화 구분": (
                    "증가" if share_end > share_start
                    else "감소" if share_end < share_start
                    else "변화 없음"
                )
            })
        comparison = pd.DataFrame(rows)
        amount_start_col = f"{start_year}년 처리량(백만 톤)"
        amount_end_col = f"{end_year}년 처리량(백만 톤)"
        share_start_col = f"{start_year}년 비율(%)"
        share_end_col = f"{end_year}년 비율(%)"
        st.dataframe(
            comparison.style.format({
                amount_start_col: "{:,.1f}",
                amount_end_col: "{:,.1f}",
                "처리량 변화(백만 톤)": "{:+,.1f}",
                share_start_col: "{:.2f}",
                share_end_col: "{:.2f}",
                "비율 변화(%p)": "{:+.2f}",
                "비율 변화율(%)": "{:+.2f}"
            }),
            use_container_width=True,
            hide_index=True
        )
        fig5 = go.Figure()
        bar_colors = [
            "#2E8B57" if value > 0 else "#D55E00" if value < 0 else "#888888"
            for value in comparison["비율 변화(%p)"]
        ]
        fig5.add_trace(go.Bar(
            x=comparison["처리 방식"],
            y=comparison["비율 변화(%p)"],
            marker_color=bar_colors,
            text=[
                f"{value:+.2f}%p ({'증가' if value > 0 else '감소' if value < 0 else '변화 없음'})"
                for value in comparison["비율 변화(%p)"]
            ],
            textposition="outside",
            name="비율 변화"
        ))
        fig5.add_hline(y=0, line_color="gray", line_width=1)
        fig5.update_layout(
            height=400,
            xaxis_title="처리 방식",
            yaxis_title="비율 변화 (퍼센트포인트, %p)",
            uniformtext_minsize=9,
            uniformtext_mode="hide"
        )
        st.plotly_chart(fig5, use_container_width=True)
        st.caption(
            f"{start_year}년 대비 {end_year}년의 비율 변화를 표시합니다. "
            "양수는 증가, 음수는 감소이며, 표의 ‘비율 변화율(%)’은 시작 연도 비율을 기준으로 한 상대 변화율입니다. "
            "비율 변화(%p)와 비율 변화율(%)은 서로 다른 개념입니다."
        )
    else:
        st.info("선택한 시작 연도 또는 종료 연도의 폐기물 자료가 없습니다.")
else:
    st.info("폐기물 처리 방식을 하나 이상 선택하거나 선택 대상의 자료를 확인하세요.")

st.info(
    "생산량과 폐기물 처리량이 같은 기간에 함께 증가하더라도, 그것만으로 생산량 증가가 특정 처리 방식의 증가를 "
    "일으켰다고 결론 내릴 수는 없습니다. 산점도는 상관관계를 탐색하는 자료이며 상관관계는 인과관계를 뜻하지 않습니다."
)
# 생산량과 부적절한 처리량의 관계: 계획서의 ③ 보조 분석
st.header("4. 생산량과 부적절한 처리량의 관계")
if target_entity == "World" and not prod_view.empty and not fate_view.empty:
    relation = pd.merge(
        prod_view[["year", "plastic_production"]],
        fate_view[["year", FATE_COLUMNS["부적절한 처리"]]],
        on="year",
        how="inner"
    ).sort_values("year").copy()
    relation = relation.dropna(
        subset=["plastic_production", FATE_COLUMNS["부적절한 처리"]]
    )

    if len(relation) >= 2:
        mismanaged_col = FATE_COLUMNS["부적절한 처리"]
        corr = relation["plastic_production"].corr(relation[mismanaged_col])

        st.markdown(
            "생산량과 부적절한 처리량이 같은 시기에 어떻게 분포하는지 확인하는 "
            "탐색적 산점도입니다. 두 값이 함께 증가하더라도 생산량이 부적절한 처리를 "
            "증가시켰다는 인과관계를 증명하지는 않습니다."
        )
        fig_relation = go.Figure()
        fig_relation.add_trace(go.Scatter(
            x=relation["plastic_production"] / MILLION,
            y=relation[mismanaged_col] / MILLION,
            mode="markers+text",
            text=relation["year"].astype(int).astype(str),
            textposition="top center",
            name="연도별 관측값",
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
            )
        ))
        fig_relation.update_layout(
            height=480,
            xaxis_title="연간 플라스틱 생산량 (백만 톤)",
            yaxis_title="부적절한 처리량 (백만 톤)",
            hovermode="closest"
        )
        st.plotly_chart(fig_relation, use_container_width=True)
        st.metric("두 변수의 피어슨 상관계수(참고값)", f"{corr:.3f}")
        st.caption(
            "상관계수는 두 변수의 선형적 동행 정도를 요약할 뿐입니다. "
            "연도에 따른 장기 증가 추세가 두 변수 모두에 반영되어 상관이 높게 나타날 수 있으며, "
            "다른 요인과 시간 추세를 통제하지 않았으므로 인과관계로 해석할 수 없습니다. "
            "생산량과 폐기물 처리량은 서로 다른 지표이므로 실제 환경 유출량과 동일시하지 않습니다."
        )
    else:
        st.info("두 자료가 함께 존재하는 연도가 2개 미만이어서 산점도를 그릴 수 없습니다.")
else:
    st.info("세계(World) 자료를 선택하면 생산량과 부적절한 처리량의 관계를 확인할 수 있습니다.")

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
        x=korea_view["year"].astype(int),
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
            x=korea_view["year"].astype(int),
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
            x=korea_view["year"].astype(int),
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
    st.subheader("2018년과 2019년 처리 비율 함께 보기")
    compare_korea = KOREA_DATA[KOREA_DATA["year"].isin([2018, 2019])][
        ["year", "total_ton_per_day", "재활용", "소각", "매립", "기타"]
    ].copy()
    compare_korea["year"] = compare_korea["year"].astype(int)
    compare_korea = compare_korea.rename(columns={
        "year": "연도", "total_ton_per_day": "발생량(톤/일)"
    })
    st.dataframe(
        compare_korea.style.format({
            "발생량(톤/일)": "{:,.0f}", "재활용": "{:.1f}%",
            "소각": "{:.1f}%", "매립": "{:.1f}%", "기타": "{:.1f}%"
        }),
        use_container_width=True, hide_index=True
    )
    st.caption(
        "2019년은 분류·집계 기준이 바뀐 해이므로 2019년 수치만으로 추세를 단정하지 않고, "
        "2018년 값과 함께 확인해야 합니다. 국내 통계의 ‘재활용’ 비율은 집계 정의가 세계 자료와 달라 "
        "세계 플라스틱의 재활용 비율 9%와 직접 나란히 비교할 수 없습니다."
    )
    st.markdown("#### 국내 자료를 바탕으로 생각해 볼 해결 방안")
    k18 = KOREA_DATA.loc[KOREA_DATA["year"] == 2018].iloc[0]
    k19 = KOREA_DATA.loc[KOREA_DATA["year"] == 2019].iloc[0]
    st.markdown(
        f"- **근거:** 국내 플라스틱 폐기물 발생량은 2018년 {int(k18['total_ton_per_day']):,}톤/일, "
        f"2019년 {int(k19['total_ton_per_day']):,}톤/일로 집계되었습니다. 다만 2019년은 분류·집계 기준이 바뀌었으므로 "
        "두 해의 차이를 실제 발생량 증가만으로 해석해서는 안 됩니다."
    )
    st.markdown(
        f"- **근거:** 재활용 비율은 2018년 {k18['재활용']:.1f}%, 2019년 {k19['재활용']:.1f}%로 나타납니다. "
        "집계 정의가 세계 자료와 다르므로 세계 재활용 비율 9%와 직접 비교하지 않습니다."
    )
    st.markdown(
        "- **누가:** 우리 학교 학생들이 분리배출 실태를 점검하고 실천을 주도합니다."
    )
    st.markdown(
        "- **무엇을:** 교실·매점에서 일회용 플라스틱 사용량을 조사하고, 다회용 컵·용기 사용과 정확한 분리배출을 실천합니다. "
        "재활용이 어려운 복합재질 제품은 사용을 줄이고 대체 제품을 제안합니다."
    )
    st.warning(
        "국내 시계열 해석 주의: 2016년에는 발포폴리스티렌(EPS)이 재활용 통계에 새로 포함되었습니다. "
        "2019년에는 플라스틱과 폐합성수지의 분류·집계 방식이 달라졌습니다. "
        "따라서 특히 2019년의 급격한 발생량 증가는 실제 발생 증가뿐 아니라 분류·집계 기준 변화의 영향도 고려해야 합니다."
    )
else:
    st.info("국내 플라스틱 자료는 2010~2019년만 제공되어 선택한 분석 기간과 겹치는 연도가 없습니다.")

st.header("6. 예상되는 한계점")
st.markdown("""
1. **자료 기간과 범위의 한계:** 분석은 세계 자료의 공통 기간인 2000~2019년에 한정되며, 이후의 최신 변화는 반영하지 않습니다. 생산량 자료는 세계 전체를 대상으로 하지만 폐기물 자료는 OECD 모형의 지역별 추정과 가정에 의존하므로 자료의 범위와 산정 방식이 완전히 같지 않을 수 있습니다.
2. **실측값과 추정값의 차이:** 생산량 자료에서 2015년은 Geyer 논문의 실측값이며 2016~2018년은 추정치입니다. 출처와 산정 방식이 달라지는 시점 전후의 변화는 불확실성을 고려해 해석해야 합니다.
3. **분류·집계 기준의 차이:** 국내 자료는 2016년 EPS 재활용 분류 포함, 2019년 플라스틱·폐합성수지 분류 변경 등의 영향을 받습니다. 따라서 연도 간 수치 차이가 실제 발생량 변화만을 뜻하지 않을 수 있습니다.
4. **처리 방식 정의의 차이:** 국내 통계의 재활용 비율과 세계 자료의 재활용 비율은 집계 정의가 다를 수 있어 직접 비교하기 어렵습니다. 또한 부적절한 처리량은 실제 자연환경 유출량과 동일한 값이 아닙니다.
5. **상관관계 분석의 한계:** 생산량과 부적절한 처리량이 함께 증가하더라도 인과관계를 증명하지 않습니다. 시간에 따른 공통 증가 추세, 인구, 소비량, 정책, 수거·처리 인프라 등 다른 요인을 통제하지 않았습니다.
6. **국내 해결 방안의 적용 한계:** 국내 통계의 연도별 수치만으로 학교 현장의 플라스틱 사용 원인을 직접 확인할 수 없습니다. 학교에서 실제 사용량과 분리배출 실태를 추가 조사해야 구체적인 실천 효과를 평가할 수 있습니다.
""")

with st.expander("데이터 출처 및 계산 기준"):
    st.markdown("""
    **세계 생산량 및 폐기물 자료**
    - 파일: `global-plastics-production.csv`, `plastic-fate.csv`
    - 분석 기간: 2000–2019년
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
    "세계 자료: 2000–2019년 · 톤(t) | 국내 자료: 2010–2019년 · 톤/일 | "
    "자료 정의와 분류체계 차이에 유의하세요."
)
