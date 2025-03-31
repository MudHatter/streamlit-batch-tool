import streamlit as st
import pandas as pd
from openai import OpenAI
from io import BytesIO
import fugashi

# OpenAI APIキーの設定
client = OpenAI(api_key=st.secrets["openai"]["api_key"])

st.title("AIで求人作業内容をリストアップ＆案内文生成")

tagger = fugashi.Tagger()

# プレーンな作業名をAIで取得（修飾語はAIには含めさせない）
def analyze_row(title, detail):
    prompt = f"""
以下は求人広告の情報です。
この仕事に含まれる具体的な作業内容を、箇条書きでリストアップしてください。
箇条書きの各項目は、日本語で20文字以内に簡潔にまとめてください。
作業名だけを出力してください（前置きや補足は不要です）。
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

# 職種から前置き・後置き語句を抽出（fugashi使用）
def extract_prefix_suffix(title):
    words = list(tagger(title))
    prefix = ''
    suffix = ''

    for i in range(len(words)):
        surface = words[i].surface
        if surface.endswith("での") or surface.endswith("の"):
            prefix = ''.join([w.surface for w in words[:i+1]])
            break

    if ' ' in title:
        suffix = title.split()[-1]

    return prefix, suffix

# 作業名に修飾語を追加
def format_task(task, prefix, suffix):
    result = f"{prefix}{task}"
    if suffix:
        result += f"　{suffix}"
    return result

# 作業リストを1作業=1行に展開
def expand_to_rows(df):
    rows = []
    for i in range(len(df)):
        title = str(df.iloc[i, 0])
        detail = str(df.iloc[i, 1])
        raw_result = analyze_row(title, detail)

        tasks = [line.lstrip("-・0123456789. ").strip() for line in raw_result.splitlines() if line.strip()]

        prefix, suffix = extract_prefix_suffix(title)
        for task in tasks:
            formatted = format_task(task, prefix, suffix)
            rows.append({
                df.columns[0]: title,  # A列の見出しを維持
                df.columns[1]: detail,  # B列の見出しを維持
                "分割後の職種名": formatted
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
以下の説明文を、求人広告で使用する自然な仕事の説明文に書き換えてください。
以下のような文章のスタイルを参考にしてください。

【例文1】
製造装置への部材セットをお任せします。カメラの製造工程において、製造装置に必要な部材をセットする作業で、大小様々な材料を装置にセットして、製品の製造をスムーズに進める役割のお仕事です。

【例文2】
完成品の検査業務をお任せします。製造された製品にキズや不備がないかを確認するお仕事で、目視や道具を使って丁寧にチェックする作業です。

【例文3】
部品の梱包作業をお任せします。指定された部品をまとめ、箱に詰めてラベルを貼る作業で、出荷準備を整える大切なお仕事です。

---
元の説明: {original_explanation}
---
仕事の説明文（求人広告向け）:
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
    df_expanded["分割後の仕事詳細"] = df_expanded.apply(
        lambda row: describe_task(row["分割後の職種名"], row[df.columns[1]]), axis=1
    )

    # 案内文に書き換え
    st.info("求人広告向けの案内文に変換中...")
    df_expanded["案内文"] = df_expanded["分割後の仕事詳細"].apply(rewrite_for_job_ad)

    # 不要列を削除
    # （削除不要な列は明示的に指定して保持）
    df_result = df_expanded[[df.columns[0], df.columns[1], "分割後の職種名", "案内文"]].copy()
    df_result.rename(columns={"分割後の職種名": "分割後の職種名", "案内文": "分割後の仕事詳細"}, inplace=True)

    st.success("✅ 全ステップ完了！")
    st.dataframe(df_result.head(10))

    excel_data = convert_df(df_result)
    st.download_button(
        label="📥 結果をダウンロード（Excel）",
        data=excel_data,
        file_name="ai_job_ads_output.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
