import streamlit as st
import pandas as pd
from openai import OpenAI
from io import BytesIO
import fugashi

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
            return f"[ERROR] {e}"

    uploaded_file = st.file_uploader("Excelファイルを選択", type=["xlsx"])

    if uploaded_file is not None:
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

        st.success("✅ 全ステップ完了！")
        st.dataframe(df_result.head(10))

        excel_data = convert_df(df_result)
        st.download_button(
            label="📥 結果をダウンロード（Excel）",
            data=excel_data,
            file_name="ai_job_ads_output.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# --- 言い換え複製処理（改善版） ---
def job_rewrite():
    st.header("言い換え複製（職種名・仕事内容のパターン生成）")

    # セッション状態の管理
    if "run_rewrite" not in st.session_state:
        st.session_state.run_rewrite = False

    if "num_copies" not in st.session_state:
        st.session_state.num_copies = 3

    if "df_rewrite_output" not in st.session_state:
        st.session_state.df_rewrite_output = None

    # 🔁 リセットボタン
    if st.button("🔄 リセット"):
        st.session_state.run_rewrite = False
        st.session_state.df_rewrite_output = None

    uploaded_file = st.file_uploader("① Excelファイルを選択してください", type=["xlsx"], key="rewrite")

    # スライダー（処理前のみ表示）
    if not st.session_state.run_rewrite:
        st.slider(
            "② 複製数を選んでください（2〜10）", min_value=2, max_value=10, value=3, key="num_copies"
        )
    else:
        st.write(f"② 複製数（固定）: {st.session_state.num_copies}")

    # 処理開始ボタン
    if st.button("③ 処理を開始する") and not st.session_state.run_rewrite:
        st.session_state.run_rewrite = True

    # 処理開始後の処理ブロック
    if st.session_state.run_rewrite and uploaded_file is not None and st.session_state.df_rewrite_output is None:
        df = pd.read_excel(uploaded_file, engine="openpyxl")
        df.replace({r"_x000D_": "", r"\r": "", r"\n": ""}, regex=True, inplace=True)

        st.success("ファイルを読み込みました ✅")
        st.write("📄 アップロード内容（先頭5行）:")
        st.dataframe(df.head())

        output_rows = []

        with st.spinner("AIで言い換え処理を実行中です..."):
            for i in range(len(df)):
                title = str(df.iloc[i, 0])
                detail = str(df.iloc[i, 1])

                for n in range(1, st.session_state.num_copies + 1):
                    prompt = f"""
以下の職種名と仕事内容をもとに、求人広告向けの自然な言い回しに変えてください。

元の職種名: {title}
元の仕事内容: {detail}

---
出力形式:
職種名: ○○○○
仕事内容: ○○○○
"""
                    try:
                        response = client.chat.completions.create(
                            model="gpt-3.5-turbo",
                            messages=[{"role": "user", "content": prompt}],
                            temperature=0.7
                        )
                        content = response.choices[0].message.content.strip()
                        job_lines = content.splitlines()

                        if len(job_lines) >= 2:
                            new_title = job_lines[0].replace("職種名:", "").strip()
                            new_detail = job_lines[1].replace("仕事内容:", "").strip()
                        else:
                            new_title = "[ERROR] 不完全な応答"
                            new_detail = "[ERROR] 出力が不足"
                    except Exception as e:
                        new_title = f"[ERROR] {e}"
                        new_detail = "[ERROR]"

                    output_rows.append({
                        "元の職種名": title,
                        "元の仕事内容": detail,
                        f"複製{n}の職種名": new_title,
                        f"複製{n}の仕事内容": new_detail
                    })

        st.session_state.df_rewrite_output = pd.DataFrame(output_rows)

    # 出力結果の表示とダウンロード
    if st.session_state.df_rewrite_output is not None:
        st.success("✅ 複製処理が完了しました！")
        st.dataframe(st.session_state.df_rewrite_output.head(10))

        excel_data = convert_df(st.session_state.df_rewrite_output)
        st.download_button(
            label="📥 結果をダウンロード（Excel）",
            data=excel_data,
            file_name="ai_job_rewrite_output.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )



# --- アプリ切り替えメニュー ---
menu = st.sidebar.radio("処理を選択してください", ["業務分割", "言い換え複製"])

if menu == "業務分割":
    job_split()
elif menu == "言い換え複製":
    job_rewrite()
