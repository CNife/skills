# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""按账户计算涨跌、仓位、持仓明细

读取 scrape_tzzb.py 抓取的 JSON 数据，按账户计算：
- 当日涨跌幅（加权）
- 仓位占比
- 持仓明细（含昨日盈亏）
- 交易记录

用法：
    uv run --script=scripts/calc_accounts.py --input output/20260414_tzzb_data.json

输出：
    JSON 格式输出到 stdout
"""

import argparse
import json
from datetime import datetime
from pathlib import Path


def calc_account_data(input_path: str) -> dict:
    """计算各账户数据"""
    with open(input_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    date = raw_data.get("date", datetime.now().strftime("%Y%m%d"))
    accounts_data = raw_data.get("accounts", {})

    result = {
        "date": date,
        "accounts": {},
        "overall": {
            "daily_return": None,
            "position_rate": None,
        },
    }

    total_asset = 0.0
    total_market_value = 0.0
    weighted_return_sum = 0.0

    for account_name, account_data in accounts_data.items():
        positions = account_data.get("positions", [])
        money_remain = float(account_data.get("money_remain", 0) or 0)
        today_trades = account_data.get("today_trades", [])

        # 计算持仓总市值
        market_value = 0.0
        daily_return_sum = 0.0
        holdings = []

        for pos in positions:
            value = float(pos.get("value", 0) or 0)
            pre_profit = float(pos.get("pre_profit", 0) or 0)

            # 计算个股当日涨跌幅 = 昨日盈亏 / (市值 - 昨日盈亏)
            if value - pre_profit != 0:
                stock_return = (pre_profit / (value - pre_profit)) * 100
            else:
                stock_return = 0.0

            market_value += value
            daily_return_sum += pre_profit

            holdings.append(
                {
                    "code": pos.get("code", ""),
                    "name": pos.get("name", ""),
                    "daily_return": round(stock_return, 2),
                    "value": round(value, 2),
                    "pre_profit": round(pre_profit, 2),
                }
            )

        # 账户总资产 = 市值 + 剩余资金
        account_total_asset = market_value + money_remain

        # 仓位比例 = 市值 / 总资产 * 100
        position_rate = (market_value / account_total_asset * 100) if account_total_asset > 0 else 0

        # 当日涨跌幅 = 昨日盈亏总额 / (市值 - 昨日盈亏总额) * 100
        cost_value = market_value - daily_return_sum
        daily_return = (daily_return_sum / cost_value * 100) if cost_value != 0 else 0

        # 账户标签映射
        label_map = {
            "stock": "股票",
            "etf": "ETF",
            "strategy": "策略",
        }

        result["accounts"][account_name] = {
            "label": label_map.get(account_name, account_name),
            "daily_return": round(daily_return, 2),
            "position_rate": round(position_rate, 2),
            "holdings": holdings,
            "trades": [
                {
                    "time": t.get("entry_time", ""),
                    "code": t.get("code", ""),
                    "name": t.get("name", ""),
                    "op_name": t.get("op_name", ""),
                    "price": t.get("entry_price", ""),
                    "count": t.get("entry_count", ""),
                    "money": t.get("entry_money", ""),
                    "fee": t.get("fee_total", "0"),
                }
                for t in today_trades
            ],
        }

        total_asset += account_total_asset
        total_market_value += market_value
        weighted_return_sum += daily_return * market_value

    # 总体数据
    overall_position_rate = (total_market_value / total_asset * 100) if total_asset > 0 else 0
    overall_daily_return = (
        (weighted_return_sum / total_market_value) if total_market_value > 0 else 0
    )

    result["overall"]["daily_return"] = round(overall_daily_return, 2)
    result["overall"]["position_rate"] = round(overall_position_rate, 2)

    return result


def main():
    parser = argparse.ArgumentParser(description="按账户计算涨跌、仓位、持仓明细")
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="抓取数据 JSON 文件路径",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"输入文件不存在: {input_path}")

    result = calc_account_data(str(input_path))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
