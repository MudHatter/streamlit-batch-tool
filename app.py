import streamlit as st
import pandas as pd
import openai
from io import BytesIO

# ✅ OpenAI APIキー（Streamlit CloudのSecretsで設定済み）
openai.api_key = st.secrets["openai"]["api_key"]

st.title("求人情報をAIで分析")

# ✅ AIによる1行分の処理
def analyze_row(title, detail):
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
        return response["choices"][0]["message"]["content"]
    except Exception as e:
        return f"[ERROR] {e}"

# ✅ DataFrame全体を処理（C列を追加）
def process_dataframe(df):
    task_results = []
    for i in range(1, len(df)):
        title = str(df.iloc[i, 0])
        detail = str(df.iloc[i, 1])
        result = analyze_row(title, detail)
        task_results.append(result)

    df.loc[1:, "作業リスト"] = task_results
    return df

# ✅ ダウンロード用（BytesIOで変換）
def convert_df(df):
    output = BytesIO()
    df.to_excel(output, index=False, engine="openpyxl")
    return output.getvalue()

# ✅ メイン処理
uploaded_file = st.file_uploader("Excelファイルを選択", type=["xlsx"])

if uploaded_file is not None:
    df = pd.read_excel(uploaded_file, engine="openpyxl")

    # 改行や_x000D_の除去
    df.replace({r"_x000D_": "", r"\r": "", r"\n": ""}, regex=True, inplace=True)

    st.success("ファイルを読み込みました ✅")
    st.write("📄 アップロード内容（先頭5行）:")
    st.dataframe(df.head())

    # ✅ AIによる処理実行
    df = process_dataframe(df)

    st.write("🛠 処理結果（先頭10行）:")
    st.dataframe(df.head(10))

    # ✅ ダウンロードボタン
    excel_data = convert_df(df)

    st.download_button(
        label="📥 処理結果をダウンロード",
        data=excel_data,
        file_name="ai_processed.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
