import streamlit as st
import pandas as pd
from openai import OpenAI
from io import BytesIO
import fugashi
from datetime import datetime, timedelta, timezone

# 日本時間（JST）に変換
JST = timezone(timedelta(hours=9))

# OpenAI APIキーの設定
client = OpenAI(api_key=st.secrets["openai"]["api_key"])

tagger = fugashi.Tagger()

# --- 共通関数 ---
def convert_df(df):
    output = BytesIO()
    df.to_excel(output, index=False, engine="openpyxl")
    return output.getvalue()

# --- 業務分割処理 ---
def job_split():
    st.header("業務分割（仕事内容を複数に分ける）")

    if "df_result_split" not in st.session_state:
        st.session_state.df_result_split = None

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
            error_msg = str(e)
            if "quota" in error_msg.lower() or "rate limit" in error_msg.lower():
                st.error("⚠ OpenAIの利用上限に達しています。しばらく時間をおいて再実行してください。")
            return f"[ERROR] {e}"

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

    def format_task(task, prefix, suffix):
        result = f"{prefix}{task}"
        if suffix:
            result += f"　{suffix}"
        return result

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
                    df.columns[0]: title,
                    df.columns[1]: detail,
                    "分割後の職種名": formatted
                })
        return pd.DataFrame(rows)

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
            error_msg = str(e)
            if "quota" in error_msg.lower() or "rate limit" in error_msg.lower():
                st.error("⚠ OpenAIの利用上限に達しています。しばらく時間をおいて再実行してください。")
            return f"[ERROR] {e}"

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
            error_msg = str(e)
            if "quota" in error_msg.lower() or "rate limit" in error_msg.lower():
                st.error("⚠ OpenAIの利用上限に達しています。しばらく時間をおいて再実行してください。")
            return f"[ERROR] {e}"

    uploaded_file = st.file_uploader("Excelファイルを選択", type=["xlsx"])

    if uploaded_file is not None and st.session_state.df_result_split is None:
        df = pd.read_excel(uploaded_file, engine="openpyxl")
        df.replace({r"_x000D_": "", r"\r": "", r"\n": ""}, regex=True, inplace=True)

        st.success("ファイルを読み込みました ✅")
        st.write("📄 アップロード内容（先頭5行）:")
        st.dataframe(df.head())

        df_expanded = expand_to_rows(df)
        st.info("作業の詳細をAIで説明中...")
        df_expanded["分割後の仕事詳細"] = df_expanded.apply(
            lambda row: describe_task(row["分割後の職種名"], row[df.columns[1]]), axis=1
        )

        st.info("求人広告向けの案内文に変換中...")
        df_expanded["案内文"] = df_expanded["分割後の仕事詳細"].apply(rewrite_for_job_ad)

        df_result = df_expanded[[df.columns[0], df.columns[1], "分割後の職種名", "案内文"]].copy()
        df_result.rename(columns={"案内文": "分割後の仕事詳細"}, inplace=True)

        st.session_state.df_result_split = df_result

    if st.session_state.df_result_split is not None:
        st.success("✅ 全ステップ完了！")
        st.dataframe(st.session_state.df_result_split.head(10))

        excel_data = convert_df(st.session_state.df_result_split)
        st.download_button(
            label="📥 結果をダウンロード（Excel）",
            data=excel_data,
            file_name="ai_job_ads_output.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


# --- 職種名のバリエーション生成（ステップ1） ---
def job_title_variation():
    st.header("ステップ1: 職種名バリエーション生成")

    if "job_title_output" not in st.session_state:
        st.session_state.job_title_output = None

    # リセットボタン
    if st.button("🔄 リセット（職種名バリエーション）"):
        st.session_state.job_title_output = None

    uploaded_file = st.file_uploader("① Excelファイルを選択してください（A列に職種名）", type=["xlsx"], key="title_upload")
    num_copies = st.slider("② バリエーション数（1〜5）", min_value=1, max_value=5, value=3)

    if st.button("③ 職種名バリエーションを生成") and uploaded_file:
        df = pd.read_excel(uploaded_file, engine="openpyxl")
        df.replace({r"_x000D_": "", r"\r": "", r"\n": ""}, regex=True, inplace=True)

        st.success("ファイルを読み込みました ✅")
        st.dataframe(df.head())

        results = []

        with st.spinner("AIで職種名のバリエーションを生成中..."):
            for i in range(len(df)):
                title = str(df.iloc[i, 0])

                for _ in range(num_copies):
                    prompt = f"""
以下の職種名をもとに、求人広告で使える自然なバリエーションを作成してください。
同じ意味を保ちつつ、言い換えに工夫を加えてください。

【言い換えの例】
- スタッフ／作業員／担当者 などの語尾を入れ替える
- 「電子部品の」→「精密パーツの」「部品の」などに置き換える
- 語順を調整する（例：部品の組立 → 組立担当（部品））

【ルール】
- バリエーションはできるだけ多様にしてください
- 「〇〇（バリエーション2）」のような表現は禁止
- 同じ単語を繰り返すだけの表現は避けてください

元の職種名: {title}
---
出力形式（1つ）:
職種名: ○○○○
"""
                    try:
                        response = client.chat.completions.create(
                            model="gpt-3.5-turbo",
                            messages=[{"role": "user", "content": prompt}],
                            temperature=0.7
                        )
                        content = response.choices[0].message.content.strip()
                        lines = content.splitlines()
                        line = next((l for l in lines if "職種名:" in l), "")
                        variation = line.replace("職種名:", "").strip()
                    except Exception as e:
                        error_msg = str(e)
                        if "quota" in error_msg.lower() or "rate limit" in error_msg.lower():
                            st.error("⚠ OpenAIの利用上限に達しています。しばらく時間をおいて再実行してください。")
                        variation = f"[ERROR] {e}"

                    results.append({"元の職種名": title, "バリエーション職種名": variation})

        df_result = pd.DataFrame(results)
        st.session_state.job_title_output = df_result

    if st.session_state.job_title_output is not None:
        st.success("✅ バリエーション生成完了！")
        st.dataframe(st.session_state.job_title_output.head(10))

        excel_data = convert_df(st.session_state.job_title_output)
        st.download_button(
            label="📥 職種名バリエーションをダウンロード",
            data=excel_data,
            file_name="job_title_variations.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


# --- 仕事内容の案内文生成（ステップ2） ---
def job_detail_rewrite():
    st.header("ステップ2: 仕事内容の言い換え・案内文生成")

    if "job_detail_output" not in st.session_state:
        st.session_state.job_detail_output = None

    # リセットボタン
    if st.button("🔄 リセット（仕事内容の言い換え）"):
        st.session_state.job_detail_output = None

    uploaded_file = st.file_uploader("① 職種名と仕事内容を含むExcelファイルを選択（A列=職種名, B列=仕事内容）", type=["xlsx"], key="detail_upload")

    if st.button("② 案内文を生成する") and uploaded_file:
        df = pd.read_excel(uploaded_file, engine="openpyxl")
        df.replace({r"_x000D_": "", r"\r": "", r"\n": ""}, regex=True, inplace=True)

        st.success("ファイルを読み込みました ✅")
        st.dataframe(df.head())

        output_rows = []

        with st.spinner("AIで案内文を生成中..."):
            for i in range(len(df)):
                title = str(df.iloc[i, 0])
                detail = str(df.iloc[i, 1])

                prompt = f"""
以下の職種名と仕事内容をもとに、単語を言い換えたり、記号を変更したり、語順を変更したりして、全く異なる表現にリライトしてください。
出力は、求人広告で使用する自然な文章で作成してください。
---
職種名: {title}
仕事内容: {detail}
---
案内文:
"""
                try:
                    response = client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.7
                    )
                    content = response.choices[0].message.content.strip()
                except Exception as e:
                    error_msg = str(e)
                    if "quota" in error_msg.lower() or "rate limit" in error_msg.lower():
                        st.error("⚠ OpenAIの利用上限に達しています。しばらく時間をおいて再実行してください。")
                    content = f"[ERROR] {e}"

                output_rows.append({"職種名": title, "仕事内容": detail, "案内文": content})

        df_result = pd.DataFrame(output_rows)
        st.session_state.job_detail_output = df_result

    if st.session_state.job_detail_output is not None:
        st.success("✅ 案内文生成完了！")
        st.dataframe(st.session_state.job_detail_output.head(10))

        excel_data = convert_df(st.session_state.job_detail_output)
        st.download_button(
            label="📥 案内文入りファイルをダウンロード",
            data=excel_data,
            file_name="job_detail_rewritten.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


# --- アプリ切り替えメニュー ---
menu = st.sidebar.radio("処理を選択してください", ["業務分割", "言い換え複製"])

# 更新日時を表示（日本時間）
st.sidebar.markdown("---")
st.sidebar.caption(f"🕒 最終更新: {datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S')}（JST）")

if menu == "業務分割":
    job_split()
elif menu == "言い換え複製":
    job_title_variation()
    job_detail_rewrite()

