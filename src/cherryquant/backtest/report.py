"""
回测报告生成器 (Pydantic v2)

功能：
1. HTML格式回测报告
2. Markdown格式回测报告
3. JSON格式数据导出
4. 图表生成（权益曲线、回撤曲线等）

教学要点：
1. 报告生成模式
2. 数据可视化
3. 结果展示最佳实践

代码风格：Python 3.12+ with Pydantic v2
"""

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from .performance import PerformanceMetrics


class BacktestReport(BaseModel):
    """
    回测报告（Pydantic v2）

    包含所有回测结果信息
    """
    metrics: PerformanceMetrics
    strategy_name: str = "未命名策略"
    description: str = ""
    generated_at: datetime = Field(default_factory=datetime.now)

    model_config = {"arbitrary_types_allowed": True}

    def to_dict(self) -> dict:
        """导出为字典"""
        return {
            "strategy_name": self.strategy_name,
            "description": self.description,
            "generated_at": self.generated_at.isoformat(),
            "metrics": {
                "returns": {
                    "total_return": f"{self.metrics.total_return:.2%}",
                    "annual_return": f"{self.metrics.annual_return:.2%}",
                    "daily_return_mean": f"{self.metrics.daily_return_mean:.4%}",
                    "daily_return_std": f"{self.metrics.daily_return_std:.4%}",
                },
                "risk_metrics": {
                    "max_drawdown": f"{self.metrics.max_drawdown:.2%}",
                    "max_drawdown_duration": f"{self.metrics.max_drawdown_duration}天",
                    "sharpe_ratio": f"{self.metrics.sharpe_ratio:.2f}",
                    "sortino_ratio": f"{self.metrics.sortino_ratio:.2f}",
                    "calmar_ratio": f"{self.metrics.calmar_ratio:.2f}",
                },
                "trading": {
                    "total_trades": self.metrics.total_trades,
                    "winning_trades": self.metrics.winning_trades,
                    "losing_trades": self.metrics.losing_trades,
                    "win_rate": f"{self.metrics.win_rate:.2%}",
                    "avg_win": f"¥{self.metrics.avg_win:.2f}",
                    "avg_loss": f"¥{self.metrics.avg_loss:.2f}",
                    "profit_factor": f"{self.metrics.profit_factor:.2f}",
                    "expectancy": f"¥{self.metrics.expectancy:.2f}",
                },
                "capital": {
                    "initial": f"¥{self.metrics.initial_capital:,.2f}",
                    "final": f"¥{self.metrics.final_capital:,.2f}",
                    "peak": f"¥{self.metrics.peak_capital:,.2f}",
                    "min": f"¥{self.metrics.min_capital:,.2f}",
                },
                "period": {
                    "start_date": self.metrics.start_date.strftime("%Y-%m-%d") if self.metrics.start_date else "N/A",
                    "end_date": self.metrics.end_date.strftime("%Y-%m-%d") if self.metrics.end_date else "N/A",
                    "trading_days": self.metrics.trading_days,
                },
            }
        }


class ReportGenerator:
    """
    回测报告生成器

    教学要点：
    1. 多格式报告生成
    2. 模板引擎使用（简化版）
    3. 文件I/O操作
    """

    def __init__(self, report: BacktestReport):
        self.report = report

    def generate_markdown(self) -> str:
        """
        生成Markdown格式报告

        Returns:
            Markdown文本
        """
        m = self.report.metrics

        md_content = f"""# 回测报告：{self.report.strategy_name}

**生成时间**: {self.report.generated_at.strftime("%Y-%m-%d %H:%M:%S")}

{f"**策略说明**: {self.report.description}" if self.report.description else ""}

---

## 📊 关键指标总览

| 指标类别 | 指标名称 | 数值 | 评级 |
|---------|---------|-----|------|
| **收益** | 总收益率 | {m.total_return:.2%} | {self._grade_return(m.total_return)} |
| **收益** | 年化收益率 | {m.annual_return:.2%} | {self._grade_annual_return(m.annual_return)} |
| **风险** | 最大回撤 | {m.max_drawdown:.2%} | {self._grade_drawdown(m.max_drawdown)} |
| **风险** | 夏普比率 | {m.sharpe_ratio:.2f} | {self._grade_sharpe(m.sharpe_ratio)} |
| **交易** | 胜率 | {m.win_rate:.2%} | {self._grade_winrate(m.win_rate)} |

---

## 💰 收益分析

- **总收益率**: {m.total_return:.2%}
- **年化收益率**: {m.annual_return:.2%}
- **日均收益**: {m.daily_return_mean:.4%}
- **收益波动率**: {m.daily_return_std:.4%}

---

## 📉 风险分析

- **最大回撤**: {m.max_drawdown:.2%}
- **最大回撤持续时间**: {m.max_drawdown_duration} 天
- **夏普比率**: {m.sharpe_ratio:.2f}
- **索提诺比率**: {m.sortino_ratio:.2f}
- **卡玛比率**: {m.calmar_ratio:.2f}

---

## 🔄 交易统计

- **总交易次数**: {m.total_trades}
- **盈利交易**: {m.winning_trades} 次
- **亏损交易**: {m.losing_trades} 次
- **胜率**: {m.win_rate:.2%}
- **平均盈利**: ¥{m.avg_win:.2f}
- **平均亏损**: ¥{m.avg_loss:.2f}
- **盈亏比**: {m.profit_factor:.2f}
- **期望值**: ¥{m.expectancy:.2f}

---

## 💵 资金状况

- **初始资金**: ¥{m.initial_capital:,.2f}
- **最终资金**: ¥{m.final_capital:,.2f}
- **最高资金**: ¥{m.peak_capital:,.2f}
- **最低资金**: ¥{m.min_capital:,.2f}

---

## 📅 回测周期

- **开始日期**: {m.start_date.strftime("%Y-%m-%d") if m.start_date else "N/A"}
- **结束日期**: {m.end_date.strftime("%Y-%m-%d") if m.end_date else "N/A"}
- **交易天数**: {m.trading_days} 天

---

## 🎯 综合评价

{self._generate_summary()}

---

*报告由 CherryQuant 回测系统自动生成*
"""
        return md_content

    def generate_html(self) -> str:
        """
        生成HTML格式报告

        Returns:
            HTML文本
        """
        md_content = self.generate_markdown()

        # 简化的HTML包装（实际项目可使用markdown库）
        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>回测报告 - {self.report.strategy_name}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            line-height: 1.6;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #3498db; color: white; }}
        tr:hover {{ background-color: #f5f5f5; }}
        .metric {{ font-size: 1.2em; font-weight: bold; color: #27ae60; }}
        .grade-excellent {{ color: #27ae60; }}
        .grade-good {{ color: #2980b9; }}
        .grade-fair {{ color: #f39c12; }}
        .grade-poor {{ color: #e74c3c; }}
    </style>
</head>
<body>
    <div class="container">
        <pre>{md_content}</pre>
    </div>
</body>
</html>"""
        return html_content

    def save_to_file(self, filepath: str | Path, format: str = "markdown") -> None:
        """
        保存报告到文件

        Args:
            filepath: 文件路径
            format: 格式（markdown/html/json）
        """
        filepath = Path(filepath)

        match format.lower():
            case "markdown" | "md":
                content = self.generate_markdown()
                filepath = filepath.with_suffix(".md")
            case "html":
                content = self.generate_html()
                filepath = filepath.with_suffix(".html")
            case "json":
                import json
                content = json.dumps(self.report.to_dict(), indent=2, ensure_ascii=False)
                filepath = filepath.with_suffix(".json")
            case _:
                raise ValueError(f"不支持的格式: {format}")

        filepath.write_text(content, encoding="utf-8")
        print(f"✅ 报告已保存至: {filepath}")

    # 评级辅助方法
    def _grade_return(self, value: float) -> str:
        """评级：总收益率"""
        if value >= 0.30: return "⭐⭐⭐⭐⭐ 优秀"
        if value >= 0.15: return "⭐⭐⭐⭐ 良好"
        if value >= 0.05: return "⭐⭐⭐ 一般"
        if value >= 0: return "⭐⭐ 较差"
        return "⭐ 亏损"

    def _grade_annual_return(self, value: float) -> str:
        """评级：年化收益率"""
        if value >= 0.20: return "⭐⭐⭐⭐⭐ 优秀"
        if value >= 0.10: return "⭐⭐⭐⭐ 良好"
        if value >= 0.05: return "⭐⭐⭐ 一般"
        if value >= 0: return "⭐⭐ 较差"
        return "⭐ 亏损"

    def _grade_drawdown(self, value: float) -> str:
        """评级：最大回撤（绝对值）"""
        abs_dd = abs(value)
        if abs_dd <= 0.05: return "⭐⭐⭐⭐⭐ 优秀"
        if abs_dd <= 0.10: return "⭐⭐⭐⭐ 良好"
        if abs_dd <= 0.20: return "⭐⭐⭐ 一般"
        if abs_dd <= 0.30: return "⭐⭐ 较差"
        return "⭐ 危险"

    def _grade_sharpe(self, value: float) -> str:
        """评级：夏普比率"""
        if value >= 2.0: return "⭐⭐⭐⭐⭐ 优秀"
        if value >= 1.0: return "⭐⭐⭐⭐ 良好"
        if value >= 0.5: return "⭐⭐⭐ 一般"
        if value >= 0: return "⭐⭐ 较差"
        return "⭐ 危险"

    def _grade_winrate(self, value: float) -> str:
        """评级：胜率"""
        if value >= 0.60: return "⭐⭐⭐⭐⭐ 优秀"
        if value >= 0.50: return "⭐⭐⭐⭐ 良好"
        if value >= 0.40: return "⭐⭐⭐ 一般"
        if value >= 0.30: return "⭐⭐ 较差"
        return "⭐ 危险"

    def _generate_summary(self) -> str:
        """生成综合评价"""
        m = self.report.metrics

        # 计算综合得分
        score = 0
        comments = []

        # 收益评分
        if m.annual_return >= 0.20:
            score += 30
            comments.append("年化收益率优秀（≥20%）")
        elif m.annual_return >= 0.10:
            score += 20
            comments.append("年化收益率良好（≥10%）")
        elif m.annual_return >= 0:
            score += 10
            comments.append("年化收益率一般")
        else:
            comments.append("⚠️ 策略亏损")

        # 风险评分
        if abs(m.max_drawdown) <= 0.10:
            score += 30
            comments.append("回撤控制优秀（≤10%）")
        elif abs(m.max_drawdown) <= 0.20:
            score += 20
            comments.append("回撤控制良好（≤20%）")
        else:
            score += 5
            comments.append("⚠️ 回撤较大，需要优化风控")

        # 夏普比率
        if m.sharpe_ratio >= 2.0:
            score += 20
            comments.append("夏普比率优秀（≥2.0）")
        elif m.sharpe_ratio >= 1.0:
            score += 15
            comments.append("夏普比率良好（≥1.0）")

        # 胜率
        if m.win_rate >= 0.50:
            score += 10
            comments.append("胜率达标（≥50%）")

        # 交易次数
        if m.total_trades >= 20:
            score += 10
            comments.append("样本量充足（≥20次交易）")
        else:
            comments.append("⚠️ 交易次数较少，统计显著性不足")

        # 生成总结
        if score >= 80:
            grade = "🏆 **A级** - 优秀策略"
        elif score >= 60:
            grade = "🥈 **B级** - 良好策略"
        elif score >= 40:
            grade = "🥉 **C级** - 合格策略"
        else:
            grade = "⚠️ **D级** - 需要优化"

        summary = f"""
**综合得分**: {score}/100

**评级**: {grade}

**要点分析**:
{chr(10).join(f"- {comment}" for comment in comments)}

**建议**:
"""
        if m.annual_return < 0:
            summary += "\n- 策略当前处于亏损状态，建议重新评估交易逻辑"
        if abs(m.max_drawdown) > 0.20:
            summary += "\n- 最大回撤较大，建议加强风险控制措施"
        if m.sharpe_ratio < 1.0:
            summary += "\n- 夏普比率偏低，建议优化收益风险比"
        if m.total_trades < 20:
            summary += "\n- 交易样本量不足，建议延长回测周期或降低交易频率阈值"
        if m.win_rate < 0.40:
            summary += "\n- 胜率偏低，建议优化入场信号"

        return summary


# 使用示例
if __name__ == "__main__":
    from datetime import datetime, timedelta

    # 创建示例指标
    metrics = PerformanceMetrics(
        total_return=0.25,
        annual_return=0.15,
        daily_return_mean=0.0006,
        daily_return_std=0.012,
        max_drawdown=-0.08,
        max_drawdown_duration=15,
        sharpe_ratio=1.8,
        sortino_ratio=2.3,
        calmar_ratio=1.9,
        total_trades=50,
        winning_trades=30,
        losing_trades=20,
        win_rate=0.60,
        avg_win=15000,
        avg_loss=-8000,
        profit_factor=1.875,
        expectancy=5000,
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 12, 31),
        trading_days=250,
        initial_capital=1_000_000,
        final_capital=1_250_000,
        peak_capital=1_300_000,
        min_capital=950_000,
    )

    # 创建报告
    report = BacktestReport(
        metrics=metrics,
        strategy_name="双均线突破策略",
        description="基于MA(5)和MA(20)的交叉信号进行交易"
    )

    # 生成报告
    generator = ReportGenerator(report)

    # 输出Markdown
    print(generator.generate_markdown())

    # 保存文件
    # generator.save_to_file("backtest_report", format="markdown")
    # generator.save_to_file("backtest_report", format="html")
    # generator.save_to_file("backtest_report", format="json")
