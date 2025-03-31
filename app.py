import streamlit as st
import pandas as pd
from openai import OpenAI
from io import BytesIO

# ✅ OpenAIクライアント初期化
client = OpenAI(api_key=st.secrets["openai"]["api_key"])

st.title("求人情報の作業内容をAIでリストアップ（縦展開）")

# ✅ AIによる1行処理
def analyze_row(title, detail):
    prompt = f"""
以下は求人広告の情報です。
この仕事に含まれる具体的な作業内容を、箇条書きでリストアップしてください。
---
職種: {title}
仕事内容: {detail}
"""
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"[ERROR] {e}"

# ✅ 作業を1行ずつ縦展開して追加
def process_dataframe(df):
    rows = []

    for i in range(len(df)):
        title = str(df.iloc[i, 0])
        detail = str(df.iloc[i, 1])
        raw_result = analyze_row(title, detail)

        # 箇条書きっぽいものを分解（-・数字などで始まる行）
        tasks = [line.lstrip("-・0123456789. ").strip() for line in raw_result.splitlines() if line.strip()]

        for task in tasks:
            rows.append({
                "職種": title,
                "詳細": detail,
                "作業": task
            })

    return pd.DataFrame(rows)

# ✅ ダウンロード用（バイナリ形式）
def convert_df(df):
    output = BytesIO()
    df.to_excel(output, index=False, engine="openpyxl")
    return output.getvalue()

# ✅ メイン処理
uploaded_file = st.file_uploader("Excelファイルを選択", type=["xlsx"])

if uploaded_file is not None:
    df = pd.read_excel(uploaded_file, engine="openpyxl")
    df.replace({r"_x000D_": "", r"\r": "", r"\n": ""}, regex=True, inplace=True)

    st.success("ファイルを読み込みました ✅")
    st.write("📄 アップロード内容（先頭5行）:")
    st.dataframe(df.head())

    # ✅ 処理開始（縦展開）
    processed_df = process_dataframe(df)

    st.write("🛠 AIによる作業リストアップ結果（先頭10行）:")
    st.dataframe(processed_df.head(10))

    excel_data = convert_df(processed_df)

    st.download_button(
        label="📥 結果をExcelでダウンロード",
        data=excel_data,
        file_name="ai_processed_vertical.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
