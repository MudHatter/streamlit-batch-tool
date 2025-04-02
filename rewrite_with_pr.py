import streamlit as st
import pandas as pd
from openai import OpenAI
from io import BytesIO
import re

# OpenAI APIキーを取得
client = OpenAI(api_key=st.secrets["openai"]["api_key"])

# --- 共通関数 ---
def convert_df(df):
    output = BytesIO()
    df.to_excel(output, index=False, engine="openpyxl")
    return output.getvalue()

# --- 言い換え複製 キャッチコピーバージョン ---
def rewrite_pr():
    st.header("言い換え複製（職種とキャッチコピー）")

    if "df_result_rewrite" not in st.session_state:
        st.session_state.df_result_rewrite = None

    uploaded_file = st.file_uploader("Excelファイルを選択してください（A列=職種名, B列=キャッチコピー）※1行目は見出し扱いになります", type=["xlsx"])
    num_variations = st.slider("複製数を指定してください（2〜10）", min_value=2, max_value=10, value=3)

    if uploaded_file is not None:
        st.success("ファイルを読み込みました ✅")
        df = pd.read_excel(uploaded_file, engine="openpyxl")
        df.replace({r"_x000D_": "", r"\r": "", r"\n": ""}, regex=True, inplace=True)
        st.dataframe(df.head())

        if st.button("処理を開始する"):
            expanded_rows = []

            for i in range(len(df)):
                title = str(df.iloc[i, 0])
                detail = str(df.iloc[i, 1])

                # --- ステップ1: 職種名をAIでリスト出力 ---
                prompt_title = f"""
以下の職種名をもとに、求人広告で使える自然な職種名のバリエーションを{num_variations}個作成してください。
単語を言い換えたり、記号を変更したり、語順を変更したり、表現を言い換えて、重複しないようにしてください。
箇条書きで出力してください。
---
職種名: {title}
---
"""
                try:
                    response = client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[{"role": "user", "content": prompt_title}],
                        temperature=0.7
                    )
                    lines = response.choices[0].message.content.strip().splitlines()
                    variations = [re.sub(r"^[-\d\.・\s]+", "", line).strip() for line in lines if line.strip()]
                except Exception as e:
                    variations = [f"[ERROR] {e}" for _ in range(num_variations)]

                for var_title in variations[:num_variations]:
                    # --- ステップ2: キャッチコピーを生成 ---
                    prompt_detail = f"""
以下の求人広告のキャッチコピーをもとに、単語を言い換えたり、記号や語順を変更したりして、全く異なる自然な表現の新しいキャッチコピーを作成してください。
---
キャッチコピー: {detail}
---
新しいキャッチコピー:
"""
                    try:
                        response = client.chat.completions.create(
                            model="gpt-3.5-turbo",
                            messages=[{"role": "user", "content": prompt_detail}],
                            temperature=0.7
                        )
                        rewritten_detail = response.choices[0].message.content.strip()
                    except Exception as e:
                        rewritten_detail = f"[ERROR] {e}"

                    expanded_rows.append({
                        "元の職種名": title,
                        "元のキャッチコピー": detail,
                        "複製の職種名": var_title,
                        "複製のキャッチコピー": rewritten_detail
                    })

            df_result = pd.DataFrame(expanded_rows)
            st.session_state.df_result_rewrite = df_result

    if st.session_state.df_result_rewrite is not None:
        st.success("✅ 言い換え複製 完了！")
        st.dataframe(st.session_state.df_result_rewrite.head(10))

        excel_data = convert_df(st.session_state.df_result_rewrite)
        st.download_button(
            label="📥 結果をダウンロード（Excel）",
            data=excel_data,
            file_name="rewrite_pr_output.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
