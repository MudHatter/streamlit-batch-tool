import streamlit as st
from datetime import datetime, timedelta, timezone
from split_module import job_split
from rewrite_module import run_rewrite_combined
from rewrite_module2 import job_rewrite

# 日本時間（JST）に変換
JST = timezone(timedelta(hours=9))

# --- アプリ切り替えメニュー ---
menu = st.sidebar.radio("処理を選択してください", ["業務分割", "言い換え複製", "言い換え複製改"])

# 更新日時を表示（日本時間）
st.sidebar.markdown("---")
st.sidebar.caption(f"🕒 最終更新: {datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S')}（JST）")

if menu == "業務分割":
    job_split()
elif menu == "言い換え複製":
    run_rewrite_combined()
elif menu == "言い換え複製改":
    job_rewrite()