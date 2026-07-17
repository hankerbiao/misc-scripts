import akshare as ak
import pandas as pd

# 设置 Pandas 显示选项，方便在控制台查看完整数据
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)


def get_etf_info_demo():
    print("====== 1. 获取全市场所有场内 ETF 的最新实时行情 ======")
    try:
        # 该接口获取东方财富网-场内交易基金的实时行情
        etf_spot_df = ak.fund_etf_spot_em()
        print(f"成功获取到 {len(etf_spot_df)} 只 ETF 的实时数据。")
        print("前 5 行数据示例：")
        print(etf_spot_df.head())

        # 筛选示例：找出当天涨幅前 5 的 ETF
        # 注意：部分版本返回的涨跌幅可能是字符串或数值，建议先转换为数值型再排序
        etf_spot_df['涨跌幅'] = pd.to_numeric(etf_spot_df['涨跌幅'], errors='coerce')
        top_5_gainers = etf_spot_df.sort_values(by='涨跌幅', ascending=False).head(5)
        print("\n当天涨幅前 5 的 ETF：")
        print(top_5_gainers[['代码', '名称', '最新价', '涨跌幅', '成交额']])

    except Exception as e:
        print(f"获取 ETF 实时行情失败: {e}")

    print("\n====== 2. 获取单只 ETF 的历史行情数据（以沪深300ETF 510300 为例） ======")
    try:
        # symbol: ETF代码
        # period: daily (日线), weekly (周线), monthly (月线)
        # start_date / end_date: 格式为 YYYYMMDD
        # adjust: qfq (前复权), hfq (后复权), "" (不复权)
        etf_hist_df = ak.fund_etf_hist_em(
            symbol="510300",
            period="daily",
            start_date="20250101",
            end_date="20260615",
            adjust="qfq"
        )
        print(f"成功获取 510300 历史数据，共 {len(etf_hist_df)} 个交易日。")
        print("最新 5 个交易日的数据：")
        print(etf_hist_df.tail())

    except Exception as e:
        print(f"获取单只 ETF 历史数据失败: {e}")

    print("\n====== 3. 获取场外开放式基金（含指数基金）的最新净值及开放状态 ======")
    try:
        # 获取滚动更新的开放式基金净值表
        open_fund_df = ak.fund_open_fund_daily_em()
        print(f"成功获取到 {len(open_fund_df)} 只场外开放式基金的数据。")
        print("前 5 行数据示例：")
        print(open_fund_df.head())

    except Exception as e:
        print(f"获取开放式基金数据失败: {e}")


if __name__ == "__main__":
    get_etf_info_demo()