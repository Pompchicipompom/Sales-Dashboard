from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

DEFAULT_DATA_PATH = Path(__file__).parent / "data" / "dashboard_data.xlsx"
MONTHS_RU = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]


@st.cache_data(show_spinner=False)
def load_wide_data(file_obj_or_path) -> tuple[pd.DataFrame, list[str]]:
    source = pd.read_excel(file_obj_or_path, header=[0, 1])

    if source.shape[1] < 7:
        raise ValueError("Файл Excel должен содержать минимум 7 колонок в ожидаемой структуре.")

    region_names: list[str] = []
    for col_idx in range(1, 4):
        region_name = str(source.columns[col_idx][1]).strip()
        region_names.append(region_name if region_name else f"Регион{col_idx}")

    frame = pd.DataFrame({"date": pd.to_datetime(source.iloc[:, 0], errors="coerce")})

    for i, region in enumerate(region_names, start=1):
        frame[f"akb__{region}"] = pd.to_numeric(source.iloc[:, i], errors="coerce")

    for i, _region in enumerate(region_names, start=4):
        mapped_region = region_names[i - 4]
        frame[f"volume__{mapped_region}"] = pd.to_numeric(source.iloc[:, i], errors="coerce")

    frame = frame.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    return frame, region_names


def build_long_data(wide: pd.DataFrame, regions: Iterable[str]) -> pd.DataFrame:
    chunks: list[pd.DataFrame] = []
    for region in regions:
        chunk = pd.DataFrame(
            {
                "date": wide["date"],
                "region": region,
                "akb": wide[f"akb__{region}"],
                "volume": wide[f"volume__{region}"],
            }
        )
        chunk["lakb"] = np.where(chunk["akb"] > 0, chunk["volume"] / chunk["akb"], np.nan)
        chunks.append(chunk)

    long_df = pd.concat(chunks, ignore_index=True)
    return long_df.dropna(subset=["akb", "volume"]).sort_values(["date", "region"]).reset_index(drop=True)


def month_label(value: pd.Timestamp) -> str:
    return f"{MONTHS_RU[value.month - 1]} {value.year}"


def month_short_label(value: pd.Timestamp) -> str:
    return MONTHS_RU[value.month - 1]


def style_period_axis_with_year_brackets(fig: go.Figure, dates: pd.Series) -> None:
    axis_dates = pd.to_datetime(dates).tolist()
    if not axis_dates:
        return

    fig.update_xaxes(
        tickmode="array",
        tickvals=axis_dates,
        ticktext=[month_short_label(d) for d in axis_dates],
        tickangle=0,
        showgrid=False,
    )

    grouped = pd.DataFrame({"date": axis_dates})
    grouped["year"] = grouped["date"].dt.year

    for year, group in grouped.groupby("year", sort=True):
        start = pd.Timestamp(group["date"].iloc[0])
        end = pd.Timestamp(group["date"].iloc[-1])
        center = start + (end - start) / 2

        fig.add_shape(
            type="line",
            xref="x",
            yref="paper",
            x0=start,
            x1=end,
            y0=-0.12,
            y1=-0.12,
            line=dict(color="#94A3B8", width=1.2),
        )
        fig.add_shape(
            type="line",
            xref="x",
            yref="paper",
            x0=start,
            x1=start,
            y0=-0.12,
            y1=-0.09,
            line=dict(color="#94A3B8", width=1.2),
        )
        fig.add_shape(
            type="line",
            xref="x",
            yref="paper",
            x0=end,
            x1=end,
            y0=-0.12,
            y1=-0.09,
            line=dict(color="#94A3B8", width=1.2),
        )
        fig.add_annotation(
            x=center,
            y=-0.18,
            xref="x",
            yref="paper",
            text=str(year),
            showarrow=False,
            font=dict(size=12, color="#475569"),
        )

    axis_center = pd.Timestamp(axis_dates[0]) + (pd.Timestamp(axis_dates[-1]) - pd.Timestamp(axis_dates[0])) / 2
    fig.add_annotation(
        x=axis_center,
        y=-0.26,
        xref="x",
        yref="paper",
        text="Период",
        showarrow=False,
        font=dict(size=12, color="#334155"),
    )


def pct_change(current: float, previous: float) -> float:
    if np.isnan(current) or np.isnan(previous) or previous == 0:
        return float("nan")
    return (current - previous) / previous * 100


def format_delta(value: float, suffix: str = "%") -> str | None:
    if np.isnan(value):
        return None
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.1f}{suffix}"


def fmt_int(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ")


def add_vertical_space(px: int = 16) -> None:
    st.markdown(f"<div style='height:{px}px;'></div>", unsafe_allow_html=True)


def render_block_title(text: str) -> None:
    st.markdown(
        f"<p style='margin:0; font-size:1.06rem; font-weight:600; color:#0F172A;'>{text}</p>",
        unsafe_allow_html=True,
    )


def render_insight_cards(min_height_px: int = 340) -> None:
    html = """
    <style>
    .insights-wrap {{
        display: grid;
        grid-template-rows: repeat(4, minmax(0, 1fr));
        gap: 6px;
        margin-top: 8px;
        min-height: {min_height_px}px;
    }}
    .insight-card {{
        display: grid;
        grid-template-columns: 30px 1fr;
        gap: 10px;
        align-items: start;
        padding: 7px 0;
        border-radius: 10px;
        border: none;
        background: transparent;
    }}
    .insight-icon {{
        width: 24px;
        height: 24px;
        border-radius: 6px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 13px;
        font-weight: 700;
        line-height: 1;
    }}
    .icon-green {{ background: #DCFCE7; color: #15803D; }}
    .icon-blue {{ background: #DBEAFE; color: #1D4ED8; }}
    .icon-orange {{ background: #FFEDD5; color: #C2410C; }}
    .icon-amber {{ background: #FEF3C7; color: #B45309; }}
    .insight-title {{
        margin: 0 0 3px 0;
        font-size: 14px;
        font-weight: 600;
        color: #0F172A;
    }}
    .insight-text {{
        margin: 0;
        font-size: 12.5px;
        line-height: 1.3;
        color: #334155;
    }}
    </style>
    <div class="insights-wrap">
        <div class="insight-card">
            <div class="insight-icon icon-green">↗</div>
            <div>
                <p class="insight-title">Сезонность</p>
                <p class="insight-text">Пик бизнеса приходится на июль-август, снижение - на январь-февраль.</p>
            </div>
        </div>
        <div class="insight-card">
            <div class="insight-icon icon-blue">II</div>
            <div>
                <p class="insight-title">Динамика по годам</p>
                <p class="insight-text">2025 год превосходит 2024 по общему объёму на +33.2%; темп 2026 года (YTD) отстаёт от 2025 на 23.7%.</p>
            </div>
        </div>
        <div class="insight-card">
            <div class="insight-icon icon-orange">!</div>
            <div>
                <p class="insight-title">Зона роста</p>
                <p class="insight-text">Восстановление АКБ и конверсии в Регионах 2-3 вне пикового сезона.</p>
            </div>
        </div>
        <div class="insight-card">
            <div class="insight-icon icon-amber">◎</div>
            <div>
                <p class="insight-title">Фокус действий</p>
                <p class="insight-text">Следует сфокусироваться на "предсезонная активации" в мае-июне с опорой на лидера Регион1 (доля 45.3%). Контрольный ориентир: пиковый месяц - июл 2025 (2 638 199 л).</p>
            </div>
        </div>
    </div>
    """.format(min_height_px=min_height_px)
    st.markdown(html, unsafe_allow_html=True)


def aggregate_period_metrics(wide_period: pd.DataFrame, regions: list[str]) -> dict:
    long_period = build_long_data(wide_period, regions)
    monthly_period = (
        long_period.groupby("date", as_index=False)
        .agg(volume=("volume", "sum"), akb=("akb", "sum"))
        .sort_values("date")
    )
    monthly_period["lakb"] = np.where(
        monthly_period["akb"] > 0,
        monthly_period["volume"] / monthly_period["akb"],
        np.nan,
    )

    total_volume_period = float(monthly_period["volume"].sum())
    total_akb_period = float(monthly_period["akb"].sum())
    avg_akb_period = float(monthly_period["akb"].mean()) if not monthly_period.empty else float("nan")
    avg_lakb_period = (
        total_volume_period / total_akb_period if total_akb_period > 0 else float("nan")
    )

    return {
        "long": long_period,
        "monthly": monthly_period,
        "total_volume": total_volume_period,
        "total_akb": total_akb_period,
        "avg_akb": avg_akb_period,
        "avg_lakb": avg_lakb_period,
    }


def compute_comparison_metrics(
    wide_df: pd.DataFrame, filtered_wide: pd.DataFrame, regions: list[str]
) -> tuple[dict, dict | None, str]:
    current_metrics = aggregate_period_metrics(filtered_wide, regions)
    selected_indexes = filtered_wide.index.to_list()
    period_len = len(selected_indexes)
    current_start_idx = selected_indexes[0]

    if current_start_idx - period_len >= 0:
        prev_wide = wide_df.iloc[current_start_idx - period_len : current_start_idx].copy()
        prev_metrics = aggregate_period_metrics(prev_wide, regions)
        return current_metrics, prev_metrics, "к предыдущему периоду той же длины"

    if period_len >= 2:
        half = max(1, period_len // 2)
        prev_wide = filtered_wide.iloc[:half].copy()
        current_tail = filtered_wide.iloc[-half:].copy()
        prev_metrics = aggregate_period_metrics(prev_wide, regions)
        current_tail_metrics = aggregate_period_metrics(current_tail, regions)
        return current_tail_metrics, prev_metrics, "вторая половина периода к первой"

    if current_start_idx > 0:
        prev_wide = wide_df.iloc[current_start_idx - 1 : current_start_idx].copy()
        prev_metrics = aggregate_period_metrics(prev_wide, regions)
        return current_metrics, prev_metrics, "к предыдущему месяцу"

    return current_metrics, None, "база сравнения недоступна"


def main() -> None:
    st.set_page_config(page_title="Балтика | Управление представленностью", layout="wide")

    st.title("Балтика | Управление представленностью")
    st.caption(
        "Разработчик: Старков О.А. в рамках тестового задания на позицию «Менеджер аналитики и целеполагания» "
        "специально для компании ООО «Пивоваренная Компания \"Балтика\"»."
    )

    with st.sidebar:
        st.header("Фильтры")
        uploaded = st.file_uploader("Загрузить .xlsx", type=["xlsx"])

        if uploaded is not None:
            wide_df, available_regions = load_wide_data(uploaded)
            source_label = uploaded.name
        else:
            if not DEFAULT_DATA_PATH.exists():
                st.error(f"Файл источника не найден: {DEFAULT_DATA_PATH}")
                st.stop()
            wide_df, available_regions = load_wide_data(DEFAULT_DATA_PATH)
            source_label = DEFAULT_DATA_PATH.name

        st.caption(f"Источник данных: {source_label}")

        min_date = wide_df["date"].min().date()
        max_date = wide_df["date"].max().date()

        selected_regions = st.multiselect(
            "Регионы",
            options=available_regions,
            default=available_regions,
        )

        date_from, date_to = st.slider(
            "Период",
            min_value=min_date,
            max_value=max_date,
            value=(min_date, max_date),
        )

    if not selected_regions:
        st.warning("Выберите хотя бы один регион для отображения дашборда.")
        st.stop()

    mask = (wide_df["date"].dt.date >= date_from) & (wide_df["date"].dt.date <= date_to)
    filtered_wide = wide_df.loc[mask].copy()

    if filtered_wide.empty:
        st.warning("В выбранном периоде нет данных.")
        st.stop()

    current_metrics = aggregate_period_metrics(filtered_wide, selected_regions)
    long_df = current_metrics["long"]
    monthly = current_metrics["monthly"]
    total_volume = current_metrics["total_volume"]
    total_akb = current_metrics["total_akb"]
    avg_akb = current_metrics["avg_akb"]
    avg_lakb = current_metrics["avg_lakb"]

    comp_current_metrics, comp_prev_metrics, comparison_basis = compute_comparison_metrics(
        wide_df, filtered_wide, selected_regions
    )
    if comp_prev_metrics is not None:
        volume_delta = pct_change(comp_current_metrics["total_volume"], comp_prev_metrics["total_volume"])
        akb_delta = pct_change(comp_current_metrics["avg_akb"], comp_prev_metrics["avg_akb"])
        lakb_delta = pct_change(comp_current_metrics["avg_lakb"], comp_prev_metrics["avg_lakb"])
    else:
        volume_delta = 0.0
        akb_delta = 0.0
        lakb_delta = 0.0

    region_summary = (
        long_df.groupby("region", as_index=False)
        .agg(volume_sum=("volume", "sum"), akb_sum=("akb", "sum"), akb_avg=("akb", "mean"))
        .sort_values("region")
    )
    region_summary["lakb"] = np.where(
        region_summary["akb_sum"] > 0,
        region_summary["volume_sum"] / region_summary["akb_sum"],
        np.nan,
    )
    leader = region_summary.loc[region_summary["volume_sum"].idxmax()]
    leader_share = leader["volume_sum"] / region_summary["volume_sum"].sum() * 100
    peak_row = monthly.loc[monthly["volume"].idxmax()]

    year_volume = monthly.assign(year=monthly["date"].dt.year).groupby("year", as_index=False)["volume"].sum()
    year_map = dict(zip(year_volume["year"], year_volume["volume"]))
    growth_2025_vs_2024 = (
        ((year_map[2025] - year_map[2024]) / year_map[2024] * 100)
        if 2024 in year_map and 2025 in year_map and year_map[2024] != 0
        else float("nan")
    )
    ytd_2026_vs_2025 = float("nan")
    if 2025 in year_map and 2026 in year_map:
        vol_2025 = monthly[monthly["date"].dt.year == 2025]["volume"].reset_index(drop=True)
        vol_2026 = monthly[monthly["date"].dt.year == 2026]["volume"].reset_index(drop=True)
        months_count = min(len(vol_2025), len(vol_2026))
        if months_count > 0:
            vol_2025_ytd = vol_2025.iloc[:months_count].sum()
            vol_2026_ytd = vol_2026.iloc[:months_count].sum()
            if vol_2025_ytd != 0:
                ytd_2026_vs_2025 = (vol_2026_ytd - vol_2025_ytd) / vol_2025_ytd * 100

    c1, c2, c3, c4 = st.columns(4)
    with c1.container(border=True):
        st.metric("Общий объем", f"{fmt_int(total_volume)} л", delta=format_delta(volume_delta))
    with c2.container(border=True):
        st.metric("Средний АКБ", fmt_int(avg_akb), delta=format_delta(akb_delta))
    with c3.container(border=True):
        st.metric("Средний L/АКБ", f"{avg_lakb:.2f}", delta=format_delta(lakb_delta))
    with c4.container(border=True):
        st.metric(
            "Лидер по объему",
            str(leader["region"]),
            delta=f"{leader_share:.1f}% доля",
        )
    st.caption(f"Логика процента под KPI: {comparison_basis}.")

    fig_main = make_subplots(specs=[[{"secondary_y": True}]])
    fig_main.add_trace(
        go.Scatter(
            x=monthly["date"],
            y=monthly["volume"],
            name="Объем",
            mode="lines+markers",
            line=dict(color="#3B82F6", width=3),
        ),
        secondary_y=False,
    )
    fig_main.add_trace(
        go.Scatter(
            x=monthly["date"],
            y=monthly["akb"],
            name="АКБ",
            mode="lines+markers",
            line=dict(color="#F59E0B", width=3),
        ),
        secondary_y=True,
    )
    fig_main.update_layout(
        title="Динамика объема и АКБ",
        margin=dict(l=10, r=10, t=45, b=105),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig_main.update_yaxes(title_text="Объем, л", secondary_y=False)
    fig_main.update_yaxes(title_text="АКБ", secondary_y=True)
    style_period_axis_with_year_brackets(fig_main, monthly["date"])
    with st.container(border=True):
        st.plotly_chart(fig_main, use_container_width=True)

    equal_block_height = 520
    region_plot_height = 390
    eff_plot_height = 460
    heat_plot_height = 330
    lower_grid_gap_px = 16

    left, right = st.columns(2, gap="medium")

    with left:
        avg_line = float(monthly["lakb"].mean())
        fig_eff = go.Figure()
        fig_eff.add_trace(
            go.Scatter(
                x=monthly["date"],
                y=monthly["lakb"],
                mode="lines+markers",
                name="L/АКБ",
                line=dict(color="#10B981", width=3),
            )
        )
        fig_eff.add_hline(
            y=avg_line,
            line_dash="dash",
            line_color="#94A3B8",
            annotation_text=f"Среднее: {avg_line:.2f}",
        )
        fig_eff.update_layout(
            margin=dict(l=10, r=10, t=10, b=105),
            height=eff_plot_height,
        )
        style_period_axis_with_year_brackets(fig_eff, monthly["date"])
        with st.container(border=True, height=equal_block_height):
            eff_title_col, _ = st.columns([1.15, 1.0], gap="small")
            with eff_title_col:
                add_vertical_space(4)
                render_block_title("Эффективность точки (L/АКБ)")
            st.plotly_chart(fig_eff, use_container_width=True)

    with right:
        with st.container(border=True, height=equal_block_height):
            title_col, metric_col = st.columns([1.1, 1.2], gap="small", vertical_alignment="center")
            with title_col:
                render_block_title("Сравнение регионов")
            with metric_col:
                comparison_metric = st.segmented_control(
                    "Метрика для сравнения регионов",
                    options=["volume_sum", "akb_avg", "lakb"],
                    default="volume_sum",
                    format_func=lambda x: {
                        "volume_sum": "Объем",
                        "akb_avg": "АКБ",
                        "lakb": "Объём/АКБ",
                    }[x],
                    label_visibility="collapsed",
                    width="stretch",
                    key="comparison_metric_radio",
                )
            num_bars = max(2, len(region_summary))
            palette = px.colors.sample_colorscale("Blues", np.linspace(0.35, 0.75, num_bars))
            rank_idx = (
                region_summary[comparison_metric]
                .rank(method="first", ascending=True)
                .astype(int)
                .sub(1)
                .clip(lower=0, upper=num_bars - 1)
                .tolist()
            )
            bar_colors = [palette[i] for i in rank_idx]

            fig_region = go.Figure(
                data=[
                    go.Bar(
                        x=region_summary["region"],
                        y=region_summary[comparison_metric],
                        marker=dict(
                            color=bar_colors,
                            line=dict(color="#3B82F6", width=0.8),
                        ),
                        text=region_summary[comparison_metric].round(2),
                        textposition="outside",
                        hovertemplate=(
                            "Регион: %{x}<br>"
                            "Значение: %{y:.2f}<extra></extra>"
                        ),
                    )
                ]
            )
            fig_region.update_layout(
                showlegend=False,
                margin=dict(l=10, r=10, t=10, b=10),
                xaxis_title="Регион",
                yaxis_title="Значение",
                height=region_plot_height,
            )
            st.plotly_chart(fig_region, use_container_width=True)

    add_vertical_space(lower_grid_gap_px)
    heat_cols, insight_cols = st.columns(2, gap="medium")

    with heat_cols:
        with st.container(border=True, height=equal_block_height):
            title_col, metric_col = st.columns([1.1, 1.2], gap="small", vertical_alignment="center")
            with title_col:
                render_block_title("Тепловая карта")
            with metric_col:
                heat_metric = st.segmented_control(
                    "Метрика тепловой карты",
                    options=["volume", "akb", "lakb"],
                    default="volume",
                    format_func=lambda x: {
                        "volume": "Объем",
                        "akb": "АКБ",
                        "lakb": "Объём/АКБ",
                    }[x],
                    label_visibility="collapsed",
                    width="stretch",
                    key="heat_metric_segment",
                )
            sampled_dates = monthly["date"].iloc[::3]
            heat = long_df[long_df["date"].isin(sampled_dates)].copy()
            heat["period"] = heat["date"].map(month_label)

            pivot = heat.pivot_table(index="region", columns="period", values=heat_metric, aggfunc="mean")
            ordered_periods = [month_label(d) for d in sampled_dates]
            pivot = pivot.reindex(columns=[p for p in ordered_periods if p in pivot.columns])

            fmt = ".2f" if heat_metric == "lakb" else ".0f"
            hover_fmt = ".2f" if heat_metric == "lakb" else ".0f"
            fig_heat = px.imshow(
                pivot,
                text_auto=fmt,
                aspect="equal",
                color_continuous_scale="RdYlGn",
            )
            fig_heat.update_traces(
                xgap=5,
                ygap=5,
                textfont=dict(size=12, color="#0F172A"),
                hovertemplate=(
                    "Регион: %{y}<br>"
                    "Период: %{x}<br>"
                    f"Значение: %{{z:{hover_fmt}}}<extra></extra>"
                ),
            )
            fig_heat.update_xaxes(
                side="top",
                tickangle=0,
                showgrid=False,
                title_text="Период",
            )
            fig_heat.update_yaxes(showgrid=False, title_text="Регион")
            fig_heat.update_layout(
                margin=dict(l=10, r=10, t=10, b=10),
                height=heat_plot_height,
                plot_bgcolor="#F8FAFC",
                paper_bgcolor="#FFFFFF",
                coloraxis_colorbar=dict(
                    title=(
                        "Объем, л"
                        if heat_metric == "volume"
                        else ("АКБ" if heat_metric == "akb" else "L/АКБ")
                    ),
                    thickness=14,
                    len=0.78,
                ),
            )
            heat_vertical_offset = max(0, int((equal_block_height - heat_plot_height - 120) / 2))
            add_vertical_space(heat_vertical_offset)
            st.plotly_chart(fig_heat, use_container_width=True)

    with insight_cols:
        with st.container(border=True, height=equal_block_height):
            add_vertical_space(4)
            render_block_title("Ключевые выводы")
            render_insight_cards(min_height_px=max(260, equal_block_height - 120))

if __name__ == "__main__":
    main()
