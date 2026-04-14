# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "tushare",
# ]
# ///
"""获取申万一级行业板块当日涨跌排行

通过 tushare 获取申万一级行业分类及当日涨跌幅，按涨跌幅排序。

用法：
    uv run -s scripts/fetch_sectors.py
    uv run -s scripts/fetch_sectors.py --date 20260414

输出：
    JSON 格式输出到 stdout
"""

import argparse
import json
from datetime import datetime

import tushare as ts


def fetch_sector_data(trade_date: str) -> dict:
    """获取申万一级行业当日涨跌排行"""
    pro = ts.pro_api()

    # 申万一级行业指数代码列表（31个一级行业）
    sw_l1_codes = {
        "801010.SI": "农林牧渔",
        "801030.SI": "基础化工",
        "801040.SI": "钢铁",
        "801050.SI": "煤炭",
        "801020.SI": "石油石化",
        "801080.SI": "电子",
        "801090.SI": "有色金属",
        "801110.SI": "食品饮料",
        "801120.SI": "纺织服饰",
        "801130.SI": "家用电器",
        "801140.SI": "轻工制造",
        "801150.SI": "医药生物",
        "801160.SI": "公用事业",
        "801170.SI": "交通运输",
        "801180.SI": "房地产",
        "801200.SI": "商贸零售",
        "801210.SI": "社会服务",
        "801230.SI": "电力设备",
        "801710.SI": "建筑材料",
        "801720.SI": "建筑装饰",
        "801730.SI": "国防军工",
        "801750.SI": "美容护理",
        "801760.SI": "传媒",
        "801770.SI": "计算机",
        "801780.SI": "银行",
        "801790.SI": "通信",
        "801880.SI": "汽车",
        "801890.SI": "机械设备",
        "801950.SI": "综合",
        "801960.SI": "环保",
        "801970.SI": "非银金融",
    }

    result = {"date": trade_date, "sectors": []}

    try:
        # 获取当日涨跌幅
        df_daily = pro.index_daily(
            ts_code=",".join(sw_l1_codes.keys()),
            start_date=trade_date,
            end_date=trade_date,
            fields="ts_code,trade_date,pct_chg",
        )

        if df_daily is not None and not df_daily.empty:
            # 按涨跌幅降序排序
            df_daily = df_daily.sort_values("pct_chg", ascending=False)

            for _, row in df_daily.iterrows():
                ts_code = row["ts_code"]
                name = sw_l1_codes.get(ts_code, ts_code)
                result["sectors"].append(
                    {
                        "name": name,
                        "pct_chg": round(float(row["pct_chg"]), 2),
                    }
                )
    except Exception as e:
        # 如果 index_daily 失败，返回空列表
        result["error"] = str(e)

    return result


def main():
    parser = argparse.ArgumentParser(description="获取申万一级行业当日涨跌排行")
    parser.add_argument(
        "--date",
        type=str,
        default=datetime.now().strftime("%Y%m%d"),
        help="交易日期，格式 YYYYMMDD（默认今天）",
    )
    args = parser.parse_args()

    result = fetch_sector_data(args.date)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
