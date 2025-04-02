import streamlit as st
from datetime import datetime, timedelta, timezone
from split_module import job_split
from rewrite_module import run_rewrite_combined
from rewrite_module2 import job_rewrite

# 日本時間（JST）に変換
JST = timezone(timedelta(hours=9))

# --- アプリ切り替えメニュー ---
menu = st.sidebar.radio("処理を選択してください", ["業務分割", "言い換え複製(職種と仕事内容)"])

# --- 更新日時表示（last_updated.txtから読み込み） ---
try:
    with open("last_updated.txt", "r", encoding="utf-8") as f:
        last_updated = f.read().strip()
    st.sidebar.markdown("---")
    st.sidebar.caption(f"🕒 最終更新: {last_updated}")
except Exception:
    st.sidebar.markdown("---")
    st.sidebar.caption("🕒 最終更新: 情報なし")

if menu == "業務分割":
    job_split()
elif menu == "言い換え複製(職種と仕事内容)":
    job_rewrite()