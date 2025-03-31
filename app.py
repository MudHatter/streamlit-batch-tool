import streamlit as st
import pandas as pd



st.title("Excelファイルアップロード")

uploaded_file = st.file_uploader("ファイルを選択してください（Excel形式）", type=["xlsx"])

if uploaded_file is not None:
    try:
        df = pd.read_excel(uploaded_file, engine="openpyxl")
        st.success("ファイルを読み込みました ✅")
        st.write("📄 プレビュー（先頭5行）:")
        st.dataframe(df.head())

        # 後続処理へつなげたいときはここに記述していけます
    except Exception as e:
        st.error(f"ファイルの読み込み中にエラーが発生しました: {e}")

