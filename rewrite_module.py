import streamlit as st
import pandas as pd
from openai import OpenAI
from io import BytesIO
import fugashi
import random
import json
import os

# OpenAI APIキーの設定
client = OpenAI(api_key=st.secrets["openai"]["api_key"])

tagger = fugashi.Tagger()

# --- 共通関数 ---
def convert_df(df):
    from io import BytesIO
    output = BytesIO()
    df.to_excel(output, index=False, engine="openpyxl")
    return output.getvalue()

# --- 辞書読み込み ---
def load_replacement_dict():
    path = "replacement_dict.json"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        st.warning("⚠ 置換辞書（replacement_dict.json）が見つかりません。")
        return {}

replacement_dict = load_replacement_dict()

# --- 言い換え複製（職種名と仕事内容を一括処理） ---
def run_rewrite_combined():
    st.header("言い換え複製（職種名と仕事内容を一括リライト）")

    if "rewrite_combined_output" not in st.session_state:
        st.session_state.rewrite_combined_output = None

    if st.button("🔄 リセット"):
        st.session_state.rewrite_combined_output = None

    uploaded_file = st.file_uploader("Excelファイルを選択（A列=職種名, B列=仕事内容）", type=["xlsx"], key="combined_upload")
    num_copies = st.slider("バリエーション数（1〜5）", min_value=1, max_value=5, value=3)

    if st.button("処理を開始する") and uploaded_file:
        df = pd.read_excel(uploaded_file, engine="openpyxl")
        df.replace({r"_x000D_": "", r"\r": "", r"\n": ""}, regex=True, inplace=True)

        st.success("ファイルを読み込みました ✅")
        st.dataframe(df.head())

        results = []

        with st.spinner("AIで職種名と言い換え文章を生成中..."):
            for i in range(len(df)):
                title = str(df.iloc[i, 0])
                detail = str(df.iloc[i, 1])

                words = list(tagger(title))
                word_surfaces = [w.surface for w in words]

                for _ in range(num_copies):
                    replaced_words = []
                    for word in word_surfaces:
                        if word in replacement_dict:
                            replaced = random.choice(replacement_dict[word])
                            replaced_words.append(replaced)
                        else:
                            replaced_words.append(word)
                    raw_variation = ''.join(replaced_words)

                    # AIで整形
                    try:
                        prompt = f"""
以下の職種名を、求人広告で使える自然な職種名に整えてください。
出力は25文字以内で、「です」「ます」や句読点を付けずに簡潔な名詞として作成してください。
---
元の職種名（案）: {raw_variation}
---
整形後:
"""
                        response = client.chat.completions.create(
                            model="gpt-3.5-turbo",
                            messages=[{"role": "user", "content": prompt}],
                            temperature=0.5
                        )
                        new_title = response.choices[0].message.content.strip()

                        # 🔽 追加処理：整形後の職種名をクリーンアップ
                        new_title = new_title.splitlines()[0]  # 複数行のうち最初の行のみ
                        new_title = new_title.split("バリエーション")[0].strip()  # 「バリエーション」以降を削除

                        # 職種名でない表現を検出し再修正
                        if any(x in new_title for x in ["する", "です", "募集"]):
                            reprompt = f"""
以下の表現は職種名として不適切です。求人広告で使える自然な職種名に修正してください。
---
修正前: {new_title}
---
職種名:
"""
                            retry = client.chat.completions.create(
                                model="gpt-3.5-turbo",
                                messages=[{"role": "user", "content": reprompt}],
                                temperature=0.3
                            )
                            new_title = retry.choices[0].message.content.strip().splitlines()[0]

                    except Exception as e:
                        new_title = f"[ERROR] {e}"

                    # 案内文生成
                    try:
                        prompt = f"""
以下の職種名と仕事内容をもとに、単語を言い換えたり、記号を変更したり、語順を変更したりして、全く異なる表現にリライトしてください。
出力は、求人広告で使用する自然な文章で作成してください。
---
職種名: {title}
仕事内容: {detail}
---
案内文:
"""
                        response = client.chat.completions.create(
                            model="gpt-3.5-turbo",
                            messages=[{"role": "user", "content": prompt}],
                            temperature=0.7
                        )
                        new_detail = response.choices[0].message.content.strip()
                    except Exception as e:
                        new_detail = f"[ERROR] {e}"

                    results.append({
                        "元の職種名": title,
                        "元の仕事内容": detail,
                        "複製の職種名": new_title,
                        "複製の仕事内容": new_detail
                    })

        df_result = pd.DataFrame(results)
        st.session_state.rewrite_combined_output = df_result

    if st.session_state.rewrite_combined_output is not None:
        st.success("✅ 言い換え複製 完了！")
        st.dataframe(st.session_state.rewrite_combined_output.head(10))

        excel_data = convert_df(st.session_state.rewrite_combined_output)
        st.download_button(
            label="📥 結果をダウンロード（Excel）",
            data=excel_data,
            file_name="ai_job_rewrite_output.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )