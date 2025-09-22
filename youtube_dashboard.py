import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine
from streamlit_autorefresh import st_autorefresh
from datetime import datetime

# ---------------- PostgreSQL connection ----------------
engine = create_engine(
    "postgresql+psycopg2://postgres:itsmaygal02@localhost:5432/youtube_dashboard"
)

# ---------------- Page Config ----------------
st.set_page_config(page_title="YouTube Analytics Dashboard", layout="wide")
st.title("📊 YouTube Channel Analytics Dashboard")

# ---------------- Cached Data Load ----------------
@st.cache_data(ttl=30)
def load_tables():
    # read channel (latest & history) and video tables
    channel_latest = pd.read_sql(
        "SELECT * FROM channel_stats ORDER BY fetched_at DESC LIMIT 1", engine
    )
    channel_history = pd.read_sql(
        "SELECT * FROM channel_stats ORDER BY fetched_at ASC", engine
    )
    videos = pd.read_sql("SELECT * FROM video_stats ORDER BY fetched_at DESC", engine)
    return channel_latest, channel_history, videos


channel_df, channel_history_df, videos_df = load_tables()

# Ensure datetime types
if "fetched_at" in channel_history_df.columns:
    channel_history_df["fetched_at"] = pd.to_datetime(channel_history_df["fetched_at"])
if "fetched_at" in videos_df.columns:
    videos_df["fetched_at"] = pd.to_datetime(videos_df["fetched_at"])
if "published_at" in videos_df.columns:
    videos_df["published_at"] = pd.to_datetime(videos_df["published_at"])

# ---------------- Sidebar: Filters / Controls ----------------
st.sidebar.header("🔎 Filters & Controls")

# Theme (plotly template)
theme = st.sidebar.selectbox("Theme", options=["plotly_white", "plotly_dark"])

# Date range filter for videos (use published_at if available else fetched_at)
date_col = "published_at" if "published_at" in videos_df.columns else "fetched_at"
if date_col in videos_df.columns and not videos_df[date_col].isnull().all():
    min_date = videos_df[date_col].min().date()
    max_date = videos_df[date_col].max().date()
    date_range = st.sidebar.date_input("Date range", value=[min_date, max_date], min_value=min_date, max_value=max_date)
    if len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date, end_date = min_date, max_date
else:
    # fallback: no date column
    start_date, end_date = None, None

top_n = st.sidebar.slider("Top N videos to show (by views)", min_value=3, max_value=50, value=10, step=1)

# Manual refresh button
if st.sidebar.button("🔄 Refresh Data Now"):
    st.cache_data.clear()
    st.rerun()


# Info about auto-refresh
st.sidebar.caption("Auto-refresh interval: 60s")

# ---------------- Prepare filtered dataset (for charts & engagement KPIs) ----------------
filtered_videos = videos_df.copy()
if start_date and end_date and date_col in filtered_videos.columns:
    start_ts = pd.to_datetime(start_date)
    end_ts = pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    filtered_videos = filtered_videos[
        (filtered_videos[date_col] >= start_ts) & (filtered_videos[date_col] <= end_ts)
    ]

# Defensive: ensure numeric columns exist and fillna
for col in ["views", "likes", "dislikes", "comments"]:
    if col not in filtered_videos.columns:
        filtered_videos[col] = 0
    filtered_videos[col] = pd.to_numeric(filtered_videos[col], errors="coerce").fillna(0)

# Engagement rate (safe against division by zero)
filtered_videos["engagement_rate"] = (
    (filtered_videos["likes"] + filtered_videos["comments"]) /
    filtered_videos["views"].replace({0: pd.NA})
).fillna(0)

# Top N by views within the filtered set
df_top_n = filtered_videos.nlargest(top_n, "views").copy()

# ---------------- KPI Row 1: Channel Overview (always from channel_df latest) ----------------
st.markdown("### 📌 Channel Overview")
col1, col2, col3, col4 = st.columns(4)

with col1:
    try:
        st.metric("👥 Subscribers", f"{int(channel_df['subscribers'].iloc[0]):,}")
    except Exception:
        st.metric("👥 Subscribers", "N/A")
with col2:
    try:
        st.metric("👀 Total Views", f"{int(channel_df['total_views'].iloc[0]):,}")
    except Exception:
        st.metric("👀 Total Views", "N/A")
with col3:
    try:
        st.metric("🎞 Total Videos", f"{int(channel_df['total_videos'].iloc[0]):,}")
    except Exception:
        st.metric("🎞 Total Videos", "N/A")
with col4:
    try:
        avg_views = channel_df['total_views'].iloc[0] / max(channel_df['total_videos'].iloc[0], 1)
        st.metric("📊 Avg Views / Video", f"{avg_views:,.0f}")
    except Exception:
        st.metric("📊 Avg Views / Video", "N/A")

# ---------------- KPI Row 2: Engagement Metrics (from filtered_videos) ----------------
st.markdown("### 📊 Engagement Metrics (filtered)")
c1, c2, c3, c4, c5 = st.columns([1,1,1,1,1])

total_likes = int(filtered_videos["likes"].sum())
total_dislikes = int(filtered_videos["dislikes"].sum())
total_comments = int(filtered_videos["comments"].sum())
total_views_filtered = int(filtered_videos["views"].sum())
avg_engagement = float(filtered_videos["engagement_rate"].mean()) if not filtered_videos.empty else 0.0

with c1:
    st.metric("👍 Total Likes", f"{total_likes:,}")
with c2:
    st.metric("👎 Total Dislikes", f"{total_dislikes:,}")
with c3:
    st.metric("💬 Total Comments", f"{total_comments:,}")
with c4:
    st.metric("👀 Filtered Views", f"{total_views_filtered:,}")
with c5:
    st.metric("📈 Avg Engagement Rate", f"{avg_engagement:.2%}")

# Most viewed / liked / disliked (from filtered set; fallback to global videos_df if empty)
if not filtered_videos.empty:
    mv = filtered_videos.loc[filtered_videos["views"].idxmax()]
    ml = filtered_videos.loc[filtered_videos["likes"].idxmax()]
    md = filtered_videos.loc[filtered_videos["dislikes"].idxmax()]
else:
    mv = videos_df.loc[videos_df["views"].idxmax()] if not videos_df.empty else None
    ml = videos_df.loc[videos_df["likes"].idxmax()] if not videos_df.empty else None
    md = videos_df.loc[videos_df["dislikes"].idxmax()] if not videos_df.empty else None

r1, r2, r3 = st.columns(3)
if mv is not None:
    r1.metric("🔥 Most Viewed (filtered)", mv.get("title", "N/A"), f'{int(mv.get("views",0)):,} views')
else:
    r1.metric("🔥 Most Viewed (filtered)", "N/A")
if ml is not None:
    r2.metric("❤️ Most Liked (filtered)", ml.get("title", "N/A"), f'{int(ml.get("likes",0)):,} likes')
else:
    r2.metric("❤️ Most Liked (filtered)", "N/A")
if md is not None:
    r3.metric("👎 Most Disliked (filtered)", md.get("title", "N/A"), f'{int(md.get("dislikes",0)):,} dislikes')
else:
    r3.metric("👎 Most Disliked (filtered)", "N/A")

# ---------------- Subscriber Growth Charts ----------------
st.subheader("📈 Subscriber Growth")

# Prepare subscriber history (daily points + monthly aggregation)
if not channel_history_df.empty and "fetched_at" in channel_history_df.columns:
    ch = channel_history_df.copy()
    ch["fetched_at"] = pd.to_datetime(ch["fetched_at"])
    # daily/all-points line (shows immediate changes within month)
    fig_daily = px.line(ch, x="fetched_at", y="subscribers", markers=True, title="Subscriber snapshots over time")
    fig_daily.update_layout(template=theme)
    st.plotly_chart(fig_daily, use_container_width=True)

    # monthly aggregated
    ch["month"] = ch["fetched_at"].dt.to_period("M")
    monthly_subs = ch.groupby("month")["subscribers"].last().reset_index()
    monthly_subs["month"] = monthly_subs["month"].dt.to_timestamp()
    fig_monthly = px.line(monthly_subs, x="month", y="subscribers", markers=True, title="Monthly Subscriber Growth")
    fig_monthly.update_layout(template=theme)
    st.plotly_chart(fig_monthly, use_container_width=True)
else:
    st.info("No channel history available to plot subscriber growth.")

# ---------------- Video Insights / Charts ----------------
st.subheader("🔥 Top Videos & Engagement")

# Top N by views bar chart
if not df_top_n.empty:
    fig_top = px.bar(df_top_n, x="title", y="views", text="views", title=f"Top {top_n} Videos by Views")
    fig_top.update_layout(template=theme, xaxis_tickangle=-45)
    fig_top.update_traces(texttemplate='%{text:.2s}', textposition='outside')
    st.plotly_chart(fig_top, use_container_width=True)
else:
    st.info("No video rows to show in Top N chart.")

# Engagement Rate chart: top by engagement
st.markdown("**Top videos by engagement rate**")
top_eng = filtered_videos.sort_values("engagement_rate", ascending=False).head(top_n)
if not top_eng.empty:
    fig_eng = px.bar(top_eng, x="title", y="engagement_rate", text=top_eng["engagement_rate"].map(lambda x: f"{x:.2%}"),
                     title=f"Top {min(top_n, len(top_eng))} Videos by Engagement Rate")
    fig_eng.update_layout(template=theme, xaxis_tickangle=-45)
    st.plotly_chart(fig_eng, use_container_width=True)
else:
    st.info("No videos to show in engagement chart.")

# Engagement vs Views scatter
st.markdown("**Engagement vs Views (bubble = likes)**")
if not filtered_videos.empty:
    fig_scatter = px.scatter(filtered_videos, x="views", y="engagement_rate", size="likes",
                             hover_name="title", title="Engagement Rate vs Views", template=theme)
    st.plotly_chart(fig_scatter, use_container_width=True)
else:
    st.info("No data for scatter chart.")

# Likes distribution pie (top 10)
st.subheader("Likes Distribution (Top 10)")
top_likes = filtered_videos.nlargest(10, "likes")
if not top_likes.empty:
    fig_likes = px.pie(top_likes, names="title", values="likes", title="Top 10 Videos by Likes")
    fig_likes.update_layout(template=theme)
    st.plotly_chart(fig_likes, use_container_width=True)
else:
    st.info("Not enough data for likes pie chart.")

# Optional: Dislikes distribution if there are dislikes
if filtered_videos["dislikes"].sum() > 0:
    st.subheader("Dislikes Distribution (Top 10)")
    top_dislikes = filtered_videos.nlargest(10, "dislikes")
    fig_dislikes = px.pie(top_dislikes, names="title", values="dislikes", title="Top 10 Videos by Dislikes")
    fig_dislikes.update_layout(template=theme)
    st.plotly_chart(fig_dislikes, use_container_width=True)

# ---------------- Latest Video Table ----------------
st.subheader("Latest Video Stats (filtered)")
table_cols = ["title", "views", "likes", "dislikes", "comments", date_col] if date_col in filtered_videos.columns else ["title", "views", "likes", "dislikes", "comments"]
st.dataframe(filtered_videos[table_cols].reset_index(drop=True))

# ---------------- Auto-refresh ----------------
# Auto-refresh every 60 seconds (keep it)
count = st_autorefresh(interval=60000, key="refresh")

# ---------------- Footer ----------------
st.caption("Built with ❤️ — Auto-refresh 60s • Use sidebar to filter & manually refresh.")
st.markdown("---")
st.markdown("Data source: YouTube Data API v3 • Database: PostgreSQL")