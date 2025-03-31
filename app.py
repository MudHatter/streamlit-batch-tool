import streamlit as st
import pandas as pd
from openai import OpenAI
from io import BytesIO

# OpenAI APIキーの設定
client = OpenAI(api_key=st.secrets["openai"]["api_key"])

st.title("AIで求人作業内容をリストアップ＆案内文生成")

# 作業リストをAIで生成
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

# 作業リストを1作業=1行に展開
def expand_to_rows(df):
    rows = []
    for i in range(len(df)):
        title = str(df.iloc[i, 0])
        detail = str(df.iloc[i, 1])
        raw_result = analyze_row(title, detail)

        tasks = [line.lstrip("-・0123456789. ").strip() for line in raw_result.splitlines() if line.strip()]

        for task in tasks:
            rows.append({
                "職種": title,
                "元の説明": detail,
                "作業": task
            })

    return pd.DataFrame(rows)

# 各作業の詳細を説明

def describe_task(task, original_detail):
    prompt = f"""
以下の仕事内容の説明をもとに、「{task}」という作業が具体的に何を意味するのかを簡潔に説明してください。
---
仕事内容の説明: {original_detail}
---
作業の説明:
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

# 案内文スタイルに書き換える

def rewrite_for_job_ad(original_explanation):
    prompt = f"""
以下の説明文を、求人広告で使用する自然な仕事内容の説明文に書き換えてください。
前向きで丁寧な日本語にしてください。
---
元の説明: {original_explanation}
---
案内文（求人広告向け）:
"""
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"[ERROR] {e}"

# Excel変換
def convert_df(df):
    output = BytesIO()
    df.to_excel(output, index=False, engine="openpyxl")
    return output.getvalue()

# Streamlit UI処理
uploaded_file = st.file_uploader("Excelファイルを選択", type=["xlsx"])

if uploaded_file is not None:
    df = pd.read_excel(uploaded_file, engine="openpyxl")
    df.replace({r"_x000D_": "", r"\r": "", r"\n": ""}, regex=True, inplace=True)

    st.success("ファイルを読み込みました ✅")
    st.write("📄 アップロード内容（先頭5行）:")
    st.dataframe(df.head())

    # 作業リストアップ＆展開
    df_expanded = expand_to_rows(df)

    # 作業詳細を追加
    st.info("作業の詳細をAIで説明中...")
    df_expanded["作業詳細"] = df_expanded.apply(
        lambda row: describe_task(row["作業"], row["元の説明"]), axis=1
    )

    # 案内文に書き換え
    st.info("求人広告向けの案内文に変換中...")
    df_expanded["案内文"] = df_expanded["作業詳細"].apply(rewrite_for_job_ad)

    st.success("✅ 全ステップ完了！")
    st.dataframe(df_expanded.head(10))

    excel_data = convert_df(df_expanded)
    st.download_button(
        label="📥 結果をダウンロード（Excel）",
        data=excel_data,
        file_name="ai_job_ads_output.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
