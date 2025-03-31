import streamlit as st
import pandas as pd
from openai import OpenAI
from io import BytesIO

# ✅ OpenAIクライアント初期化
client = OpenAI(api_key=st.secrets["openai"]["api_key"])

st.title("AIで作業リスト＆詳細を生成")

# ✅ 作業リストアップ
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

# ✅ 作業リスト→1行1作業に展開
def expand_to_rows(df):
    rows = []
    for i in range(len(df)):
        title = str(df.iloc[i, 0])
        detail = str(df.iloc[i, 1])
        raw_result = analyze_row(title, detail)

        tasks = [line.lstrip("-・0123456789. ").strip()
                 for line in raw_result.splitlines() if line.strip()]

        for task in tasks:
            rows.append({
                "職種": title,
                "元の説明": detail,
                "作業": task
            })

    return pd.DataFrame(rows)

# ✅ 作業の説明を追加する関数
def describe_task(task, original_detail):
    prompt = f"""
以下の仕事内容の説明をもとに、「{task}」という作業が具体的に何を意味するのかを簡潔に説明してください。
---
仕事内容の説明: {original_detail}
---
作業の説明:"""
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"[ERROR] {e}"

# ✅ Excel出力用変換
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

    # ✅ AIで作業をリストアップし縦展開
    df_expanded = expand_to_rows(df)

    st.write("🛠 作業リスト展開（先頭10行）:")
    st.dataframe(df_expanded.head(10))

    # ✅ 各作業に詳細説明を追加（D列）
    st.info("作業ごとの詳細をAIで説明中...")
    df_expanded["作業詳細"] = df_expanded.apply(
        lambda row: describe_task(row["作業"], row["元の説明"]),
        axis=1
    )

    st.success("✅ 作業詳細を追加しました！")
    st.dataframe(df_expanded.head(10))

    # ✅ ダウンロード
    excel_data = convert_df(df_expanded)
    st.download_button(
        label="📥 結果をダウンロード（Excel）",
        data=excel_data,
        file_name="ai_tasks_detailed.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
