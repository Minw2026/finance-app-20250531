from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import streamlit as st
import numpy_financial as npf

st.set_page_config(page_title="借貸與投資模擬", layout="wide")

# --------------------------
# 📌 全局可調參數
# --------------------------
st.sidebar.header("基本參數設定")
loan_amount = st.sidebar.number_input("借貸金額", value=3000000, step=100000)
annual_rate = st.sidebar.number_input("年利率 (%)", value=2.6) / 100
loan_years = st.sidebar.number_input("貸款年期", value=10, step=1)
months = loan_years * 12
start_date = st.sidebar.date_input("開始還款年月", value=datetime(2025, 7, 1))
initial_available_fund = st.sidebar.number_input("初始可支配金額", value=loan_amount, step=100000)

monthly_rate = annual_rate / 12
monthly_payment = np.ceil(npf.pmt(monthly_rate, months, -loan_amount))

# --------------------------
# 📄 頁籤選擇
# --------------------------
tab1, tab2, tab3, tab4 = st.tabs(["📄 頁一：本息攤還", "📈 頁二：股票投資", "💰 頁三：單筆收支", "📊 頁四：總結報表"])

# --------------------------
# 📄 頁一：本息攤還表
# --------------------------
with tab1:
    st.header("📄 頁一：本息平均攤還表")

    balance = loan_amount
    data = []

    for i in range(1, months + 1):
        interest = np.ceil(balance * monthly_rate)
        principal = np.ceil(monthly_payment - interest)
        if balance < principal:
            principal = balance
            monthly_payment = principal + interest
        balance -= principal
        data.append([i, monthly_payment, principal, interest, max(balance, 0)])

    amort_df = pd.DataFrame(data, columns=["期數", "每期還款金額", "本金", "利息", "剩餘本金"])
    st.dataframe(amort_df, use_container_width=True)

    st.subheader("本金與利息分佈圖")
    chart_df = amort_df[["本金", "利息"]]
    st.bar_chart(chart_df)

# --------------------------
# 📈 頁二：股票投資模擬
# --------------------------
with tab2:
    st.header("📈 頁二：股票投資模擬")

    freq_map = {"月配": 1, "季配": 3, "年配": 12}
    invest_df = st.data_editor(
        pd.DataFrame({
            "股票名稱": [],
            "投資金額": [],
            "股數": [],
            "每次配息": [],
            "配息頻率": [],
            "開始年月": pd.to_datetime([]),
        }),
        column_config={
            "配息頻率": st.column_config.SelectboxColumn("配息頻率", options=list(freq_map.keys())),
            "開始年月": st.column_config.DateColumn("開始年月")
        },
        num_rows="dynamic",
        use_container_width=True
    )

    if st.button("📊 計算與模擬", key="simulate_investment"):
        merged_df = amort_df.copy()
        merged_df["可支配金額"] = 0
        merged_df["股票投資利息"] = 0
        merged_df["可支配金額（含投資）"] = 0

        # 日期欄位對應
        merged_df["年月"] = [start_date + pd.DateOffset(months=i - 1) for i in merged_df["期數"]]

        # 扣除投資金額
        invested_total = invest_df["投資金額"].sum()
        merged_df.at[0, "可支配金額（含投資）"] = initial_available_fund - invested_total - merged_df.at[0, "本金"] - merged_df.at[0, "利息"]

        # 計算每期股息收入
        for _, row in invest_df.iterrows():
            freq = freq_map.get(row["配息頻率"], 12)
            div_date = row["開始年月"]
            while div_date <= merged_df["年月"].iloc[-1]:
                mask = merged_df["年月"] == div_date
                if mask.any():
                    idx = merged_df[mask].index[0]
                    merged_df.at[idx, "股票投資利息"] += np.ceil(row["每次配息"] * row["股數"])
                div_date += pd.DateOffset(months=freq)

        # 計算累積可支配金額
        for i in range(1, len(merged_df)):
            merged_df.at[i, "可支配金額（含投資）"] = (
                merged_df.at[i - 1, "可支配金額（含投資）"]
                - merged_df.at[i, "本金"]
                - merged_df.at[i, "利息"]
                + merged_df.at[i, "股票投資利息"]
            )

        st.dataframe(merged_df, use_container_width=True)
        st.line_chart(merged_df[["可支配金額（含投資）"]])

# --------------------------
# 💰 頁三：單筆收支模擬
# --------------------------
with tab3:
    st.header("💰 頁三：單筆收支模擬")

    income_expense_df = st.data_editor(
        pd.DataFrame({
            "項目名稱": [],
            "金額": [],
            "類型": [],
            "開始年月": pd.to_datetime([]),
        }),
        column_config={
            "類型": st.column_config.SelectboxColumn("類型", options=["支出", "收入"]),
            "開始年月": st.column_config.DateColumn("開始年月")
        },
        num_rows="dynamic",
        use_container_width=True
    )

    if st.button("📊 計算與模擬", key="simulate_income_expense"):
        # 重用頁二結果
        merged_df = amort_df.copy()
        merged_df["可支配金額"] = 0
        merged_df["股票投資利息"] = 0
        merged_df["可支配金額（含投資）"] = 0
        merged_df["年月"] = [start_date + pd.DateOffset(months=i - 1) for i in merged_df["期數"]]

        # 投資利息與投資金額扣除
        invested_total = invest_df["投資金額"].sum()
        for _, row in invest_df.iterrows():
            freq = freq_map.get(row["配息頻率"], 12)
            div_date = row["開始年月"]
            while div_date <= merged_df["年月"].iloc[-1]:
                mask = merged_df["年月"] == div_date
                if mask.any():
                    idx = merged_df[mask].index[0]
                    merged_df.at[idx, "股票投資利息"] += np.ceil(row["每次配息"] * row["股數"])
                div_date += pd.DateOffset(months=freq)

        # 處理收支事件
        merged_df["收支調整"] = 0
        for _, row in income_expense_df.iterrows():
            amount = np.ceil(row["金額"])
            if row["類型"] == "支出":
                amount = -amount
            mask = merged_df["年月"] == row["開始年月"]
            if mask.any():
                idx = merged_df[mask].index[0]
                merged_df.at[idx, "收支調整"] += amount

        # 初始可支配金額
        merged_df.at[0, "可支配金額（含投資）"] = (
            initial_available_fund
            - invested_total
            - merged_df.at[0, "本金"]
            - merged_df.at[0, "利息"]
            + merged_df.at[0, "股票投資利息"]
            + merged_df.at[0, "收支調整"]
        )

        for i in range(1, len(merged_df)):
            merged_df.at[i, "可支配金額（含投資）"] = (
                merged_df.at[i - 1, "可支配金額（含投資）"]
                - merged_df.at[i, "本金"]
                - merged_df.at[i, "利息"]
                + merged_df.at[i, "股票投資利息"]
                + merged_df.at[i, "收支調整"]
            )

        st.dataframe(merged_df, use_container_width=True)
        st.line_chart(merged_df[["可支配金額（含投資）"]])

        # 保存結果給頁四使用
        st.session_state["final_df"] = merged_df
        st.session_state["invested_total"] = invested_total

# --------------------------
# 📊 頁四：總結報表
# --------------------------
with tab4:
    st.header("📊 頁四：投資與現金流總結")

    if "final_df" in st.session_state:
        df = st.session_state["final_df"]
        invested_total = st.session_state["invested_total"]

        final_cash = df.iloc[-1]["可支配金額（含投資）"]
        profit = final_cash - invested_total

        st.metric("📌 投資總額", f"${invested_total:,.0f}")
        st.metric("💰 最終可支配金額（含投資）", f"${final_cash:,.0f}")
        st.metric("📈 投資成果", f"${profit:,.0f}", delta_color="normal")

        if profit >= 0:
            st.success("✅ 投資成功，整體為正報酬")
        else:
            st.error("❌ 投資虧損，需評估資金調度")
    else:
        st.info("請先至頁三模擬一次，以產生統計結果")
