import streamlit as st
import pandas as pd
from openai import OpenAI
from io import BytesIO

# ✅ OpenAIクライアント初期化
client = OpenAI(api_key=st.secrets["openai"]["api_key"])

st.title("求人情報の作業内容をAIでリストアップ（縦展開）")

# ✅ 1件ずつAIに問い合わせて作業リストを得る
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

# ✅ AIで作業リストを取得し、元のDataFrameに1列追加
def process_dataframe(df):
    results = []
    for i in range(len(df)):
        title = str(df.iloc[i, 0])
        detail = str(df.iloc[i, 1])
        result = analyze_row(title, detail)
        results.append(result)
    df["作業リスト"] = results
    return df

# ✅ 作業リストを縦に展開する関数（1作業＝1行）
def expand_to_rows(df):
    expanded_rows = []

    for i in range(len(df)):
        title = str(df.iloc[i, 0])
        detail = str(df.iloc[i, 1])
        task_list_raw = str(df.iloc[i, 2])

        # 箇条書きを1行ずつ分割（-・番号などに対応）
        tasks = [line.lstrip("-・0123456789. ").strip()
                 for line in task_list_raw.splitlines() if line.strip()]

        for task in tasks:
            expanded_rows.append({
                "職種": title,
                "詳細": detail,
                "作業": task
            })

    return pd.DataFrame(expanded_rows)

# ✅ ダウンロード用（Excelバイナリ）
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

    # ✅ AIで処理（作業リスト列を追加）
    df_processed = process_dataframe(df)

    # ✅ 縦展開（1行1作業に変換）
    df_expanded = expand_to_rows(df_processed)

    st.write("🛠 AIによる作業内容（縦展開）:")
    st.dataframe(df_expanded.head(10))

    # ✅ ダウンロード
    excel_data = convert_df(df_expanded)
    st.download_button(
        label="📥 結果をダウンロード（Excel）",
        data=excel_data,
        file_name="ai_processed_vertical.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
