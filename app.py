import streamlit as st
import pandas as pd
import openai

# APIキーをsecretsから取得
openai.api_key = st.secrets["openai"]["api_key"]

st.title("求人情報をAIで分析")

uploaded_file = st.file_uploader("Excelファイルを選択", type=["xlsx"])

if uploaded_file is not None:
    df = pd.read_excel(uploaded_file, engine="openpyxl")

    # ✅ 改行コードや _x000D_ の除去をここで実行
    df.replace({r"_x000D_": "", r"\r": "", r"\n": ""}, regex=True, inplace=True)

    st.success("ファイルを読み込みました ✅")
    st.write("📄 アップロード内容（先頭5行）:")
    st.dataframe(df.head())

    # C列用の空リスト
    task_results = []

    # 2行目（index=1）以降を処理
    for i in range(1, len(df)):
        title = str(df.iloc[i, 0])  # A列
        detail = str(df.iloc[i, 1])  # B列

        prompt = f"""
以下は求人広告の情報です。この仕事に含まれる具体的な作業内容を、箇条書きでリストアップしてください。
---
職種: {title}
仕事内容: {detail}
"""

        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            tasks = response["choices"][0]["message"]["content"]
        except Exception as e:
            tasks = f"[ERROR] {e}"

        task_results.append(tasks)

    # 結果をC列に追加（1行目は見出しなので、そこには入れない）
    df.loc[1:, "作業リスト"] = task_results

    st.write("🛠 処理結果（先頭10行）:")
    st.dataframe(df.head(10))

    # ダウンロード用
    @st.cache_data
    def convert_df(df):
        return df.to_excel(index=False, engine="openpyxl")

    excel_data = convert_df(df)
    st.download_button("📥 処理結果をダウンロード", data=excel_data, file_name="ai_processed.xlsx")
