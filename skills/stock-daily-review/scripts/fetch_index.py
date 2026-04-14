# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "tushare",
# ]
# ///
"""获取主要指数当日涨跌幅

通过 tushare 获取上证、深成指、创业板指、中证全指的当日涨跌幅。

用法：
    uv run --script=scripts/fetch_index.py
    uv run --script=scripts/fetch_index.py --date 20260414

输出：
    JSON 格式输出到 stdout
"""

import argparse
import json
from datetime import datetime

import tushare as ts


def fetch_index_data(trade_date: str) -> dict:
    """获取主要指数当日涨跌幅"""
    pro = ts.pro_api()

    # 主要指数代码
    indices = {
        "000001.SH": "上证指数",
        "399001.SZ": "深证成指",
        "399006.SZ": "创业板指",
        "000985.CSI": "中证全指",
    }

    result = {"date": trade_date, "indices": {}}

    for ts_code, name in indices.items():
        try:
            df = pro.index_daily(
                ts_code=ts_code,
                start_date=trade_date,
                end_date=trade_date,
                fields="ts_code,trade_date,pct_chg",
            )

            if df is not None and not df.empty:
                pct_chg = round(float(df.iloc[0]["pct_chg"]), 2)
            else:
                pct_chg = None
        except Exception:
            pct_chg = None

        result["indices"][ts_code] = {
            "name": name,
            "pct_chg": pct_chg,
        }

    return result


def main():
    parser = argparse.ArgumentParser(description="获取主要指数当日涨跌幅")
    parser.add_argument(
        "--date",
        type=str,
        default=datetime.now().strftime("%Y%m%d"),
        help="交易日期，格式 YYYYMMDD（默认今天）",
    )
    args = parser.parse_args()

    result = fetch_index_data(args.date)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
