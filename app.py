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


def pct_change_last_3(series: pd.Series) -> float:
    if len(series) < 6:
        return float("nan")

    recent = float(series.iloc[-3:].sum())
    previous = float(series.iloc[-6:-3].sum())
    if previous == 0:
        return float("nan")
    return (recent - previous) / previous * 100


def format_delta(value: float, suffix: str = "%") -> str | None:
    if np.isnan(value):
        return None
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.1f}{suffix}"


def fmt_int(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ")


def main() -> None:
    st.set_page_config(page_title="Драйверы роста продаж: АКБ и эффективность точки", layout="wide")

    st.title("Драйверы роста продаж: АКБ и эффективность точки")
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

        heat_metric = st.radio(
            "Метрика тепловой карты",
            options=["volume", "lakb"],
            format_func=lambda x: "Объем" if x == "volume" else "L/АКБ",
            horizontal=True,
        )

    if not selected_regions:
        st.warning("Выберите хотя бы один регион для отображения дашборда.")
        st.stop()

    mask = (wide_df["date"].dt.date >= date_from) & (wide_df["date"].dt.date <= date_to)
    filtered_wide = wide_df.loc[mask].copy()

    if filtered_wide.empty:
        st.warning("В выбранном периоде нет данных.")
        st.stop()

    long_df = build_long_data(filtered_wide, selected_regions)
    monthly = (
        long_df.groupby("date", as_index=False)
        .agg(volume=("volume", "sum"), akb=("akb", "sum"))
        .sort_values("date")
    )
    monthly["lakb"] = np.where(monthly["akb"] > 0, monthly["volume"] / monthly["akb"], np.nan)

    total_volume = float(monthly["volume"].sum())
    total_akb = float(monthly["akb"].sum())
    avg_akb = float(monthly["akb"].mean())
    avg_lakb = total_volume / total_akb if total_akb > 0 else float("nan")

    volume_growth_3m = pct_change_last_3(monthly["volume"])
    akb_growth_3m = pct_change_last_3(monthly["akb"])

    if len(monthly) >= 6:
        recent = monthly.iloc[-3:]
        prev = monthly.iloc[-6:-3]
        recent_lakb = recent["volume"].sum() / recent["akb"].sum()
        prev_lakb = prev["volume"].sum() / prev["akb"].sum()
        lakb_growth_3m = ((recent_lakb - prev_lakb) / prev_lakb * 100) if prev_lakb != 0 else float("nan")
    else:
        lakb_growth_3m = float("nan")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Общий объем", f"{fmt_int(total_volume)} л", delta=format_delta(volume_growth_3m))
    c2.metric("Средний АКБ", fmt_int(avg_akb), delta=format_delta(akb_growth_3m))
    c3.metric("Средний L/АКБ", f"{avg_lakb:.2f}", delta=format_delta(lakb_growth_3m))
    c4.metric("Рост объема (3м к пред. 3м)", format_delta(volume_growth_3m) or "н/д")

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
        margin=dict(l=10, r=10, t=45, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig_main.update_yaxes(title_text="Объем, л", secondary_y=False)
    fig_main.update_yaxes(title_text="АКБ", secondary_y=True)
    st.plotly_chart(fig_main, use_container_width=True)

    left, right = st.columns(2)

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
        fig_eff.update_layout(title="Эффективность точки (L/АКБ)", margin=dict(l=10, r=10, t=45, b=10))
        st.plotly_chart(fig_eff, use_container_width=True)

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

    with right:
        comparison_metric = st.selectbox(
            "Метрика для сравнения регионов",
            options=["volume_sum", "akb_avg", "lakb"],
            format_func=lambda x: {
                "volume_sum": "Объем",
                "akb_avg": "Средний АКБ",
                "lakb": "L/АКБ",
            }[x],
        )

        fig_region = px.bar(
            region_summary,
            x="region",
            y=comparison_metric,
            color="region",
            title="Сравнение регионов",
            labels={"region": "Регион", comparison_metric: "Значение"},
        )
        fig_region.update_layout(showlegend=False, margin=dict(l=10, r=10, t=45, b=10))
        st.plotly_chart(fig_region, use_container_width=True)

    heat_cols, insight_cols = st.columns([2, 1])

    with heat_cols:
        sampled_dates = monthly["date"].iloc[::3]
        heat = long_df[long_df["date"].isin(sampled_dates)].copy()
        heat["period"] = heat["date"].map(month_label)

        pivot = heat.pivot_table(index="region", columns="period", values=heat_metric, aggfunc="mean")
        ordered_periods = [month_label(d) for d in sampled_dates]
        pivot = pivot.reindex(columns=[p for p in ordered_periods if p in pivot.columns])

        fmt = ".0f" if heat_metric == "volume" else ".2f"
        fig_heat = px.imshow(
            pivot,
            text_auto=fmt,
            aspect="auto",
            color_continuous_scale="RdYlGn",
            title=f"Тепловая карта ({'Объем' if heat_metric == 'volume' else 'L/АКБ'})",
        )
        fig_heat.update_layout(margin=dict(l=10, r=10, t=45, b=10))
        st.plotly_chart(fig_heat, use_container_width=True)

    with insight_cols:
        st.subheader("Ключевые выводы")

        year_volume = monthly.assign(year=monthly["date"].dt.year).groupby("year", as_index=False)["volume"].sum()
        year_map = dict(zip(year_volume["year"], year_volume["volume"]))
        growth_2025_vs_2024 = (
            ((year_map[2025] - year_map[2024]) / year_map[2024] * 100)
            if 2024 in year_map and 2025 in year_map and year_map[2024] != 0
            else float("nan")
        )

        years_sorted = sorted(year_map.keys())
        ytd_change = float("nan")
        if len(years_sorted) >= 2:
            prev_year, curr_year = years_sorted[-2], years_sorted[-1]
            prev_data = monthly[monthly["date"].dt.year == prev_year]
            curr_data = monthly[monthly["date"].dt.year == curr_year]
            months_count = len(curr_data)
            prev_ytd = prev_data.head(months_count)["volume"].sum()
            curr_ytd = curr_data["volume"].sum()
            if prev_ytd != 0:
                ytd_change = (curr_ytd - prev_ytd) / prev_ytd * 100

        peak_row = monthly.loc[monthly["volume"].idxmax()]
        leader = region_summary.loc[region_summary["volume_sum"].idxmax()]
        leader_share = leader["volume_sum"] / region_summary["volume_sum"].sum() * 100

        st.markdown(
            "\n".join(
                [
                    f"- Объем 2025 к 2024: {format_delta(growth_2025_vs_2024) or 'н/д'}",
                    f"- Последний YTD к прошлому году: {format_delta(ytd_change) or 'н/д'}",
                    f"- Пиковый месяц: **{month_label(pd.Timestamp(peak_row['date']))}** ({fmt_int(peak_row['volume'])} л)",
                    f"- Лидер по объему: **{leader['region']}** ({leader_share:.1f}%)",
                ]
            )
        )

    with st.expander("Показать отфильтрованные данные"):
        show_df = monthly.copy()
        show_df["date"] = show_df["date"].dt.strftime("%Y-%m-%d")
        st.dataframe(show_df, use_container_width=True)


if __name__ == "__main__":
    main()
