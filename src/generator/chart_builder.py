"""图表生成器 - 自动生成数据可视化图表"""

import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # 非交互式后端

import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class ChartBuilder:
    """图表生成器"""

    # 颜色配置
    COLORS = {
        "水电": "#1E88E5",    # 蓝色
        "风电": "#43A047",    # 绿色
        "光伏": "#FB8C00",    # 橙色
        "火电": "#E53935",    # 红色
        "合计": "#5E35B1",    # 紫色
        "primary": "#1565C0",
        "secondary": "#42A5F5",
        "accent": "#FFB74D"
    }

    def __init__(self, output_dir: str = "data/charts"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        # 设置中文字体
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
        plt.rcParams['axes.unicode_minus'] = False

    def bar_chart(
        self,
        data: Dict[str, float],
        title: str,
        xlabel: str = "",
        ylabel: str = "",
        filename: Optional[str] = None,
        horizontal: bool = False
    ) -> str:
        """
        生成柱状图

        Args:
            data: {标签: 数值}
            title: 图表标题
            xlabel: X轴标签
            ylabel: Y轴标签
            filename: 输出文件名
            horizontal: 是否水平柱状图

        Returns:
            文件路径
        """
        fig, ax = plt.subplots(figsize=(10, 6))

        labels = list(data.keys())
        values = list(data.values())

        # 根据标签选择颜色
        colors = [self.COLORS.get(label, self.COLORS["primary"]) for label in labels]

        if horizontal:
            bars = ax.barh(labels, values, color=colors)
            ax.set_xlabel(ylabel)
            ax.set_ylabel(xlabel)
            # 添加数值标签
            for bar, val in zip(bars, values):
                ax.text(bar.get_width() + max(values) * 0.01,
                       bar.get_y() + bar.get_height() / 2,
                       f'{val:,.2f}',
                       va='center', fontsize=10)
        else:
            bars = ax.bar(labels, values, color=colors)
            ax.set_xlabel(xlabel)
            ax.set_ylabel(ylabel)
            # 添加数值标签
            for bar, val in zip(bars, values):
                ax.text(bar.get_x() + bar.get_width() / 2,
                       bar.get_height() + max(values) * 0.01,
                       f'{val:,.2f}',
                       ha='center', va='bottom', fontsize=10)

        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.grid(axis='y', alpha=0.3)

        plt.tight_layout()

        # 保存
        if filename is None:
            filename = f"bar_{title.replace(' ', '_')}.png"
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return str(filepath)

    def pie_chart(
        self,
        data: Dict[str, float],
        title: str,
        filename: Optional[str] = None,
        show_legend: bool = True
    ) -> str:
        """
        生成饼图

        Args:
            data: {标签: 数值}
            title: 图表标题
            filename: 输出文件名
            show_legend: 是否显示图例

        Returns:
            文件路径
        """
        fig, ax = plt.subplots(figsize=(8, 8))

        labels = list(data.keys())
        values = list(data.values())
        colors = [self.COLORS.get(label, self.COLORS["primary"]) for label in labels]

        # 计算百分比
        total = sum(values)
        percentages = [v / total * 100 for v in values]

        wedges, texts, autotexts = ax.pie(
            values,
            labels=None if show_legend else labels,
            colors=colors,
            autopct='%1.1f%%',
            startangle=90,
            pctdistance=0.75
        )

        # 设置百分比标签字体
        for autotext in autotexts:
            autotext.set_fontsize(10)

        if show_legend:
            ax.legend(wedges, labels,
                     title="能源类型",
                     loc="center left",
                     bbox_to_anchor=(1, 0, 0.5, 1))

        ax.set_title(title, fontsize=14, fontweight='bold')

        plt.tight_layout()

        # 保存
        if filename is None:
            filename = f"pie_{title.replace(' ', '_')}.png"
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return str(filepath)

    def line_chart(
        self,
        data: List[Dict],
        title: str,
        xlabel: str = "",
        ylabel: str = "",
        filename: Optional[str] = None,
        show_points: bool = True
    ) -> str:
        """
        生成折线图（多周趋势）

        Args:
            data: [{week: int, value: float, label: str}]
            title: 图表标题
            xlabel: X轴标签
            ylabel: Y轴标签
            filename: 输出文件名
            show_points: 是否显示数据点

        Returns:
            文件路径
        """
        fig, ax = plt.subplots(figsize=(12, 6))

        # 按标签分组
        grouped = {}
        for item in data:
            label = item.get("label", "default")
            if label not in grouped:
                grouped[label] = {"weeks": [], "values": []}
            grouped[label]["weeks"].append(item["week"])
            grouped[label]["values"].append(item["value"])

        # 绘制每组折线
        for label, group in grouped.items():
            color = self.COLORS.get(label, self.COLORS["primary"])
            ax.plot(group["weeks"], group["values"],
                   label=label, color=color,
                   linewidth=2, marker='o' if show_points else None)

        ax.set_xlabel(xlabel, fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.legend(loc='best')
        ax.grid(alpha=0.3)

        plt.tight_layout()

        # 保存
        if filename is None:
            filename = f"line_{title.replace(' ', '_')}.png"
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return str(filepath)

    def comparison_chart(
        self,
        data: Dict[str, Dict[str, float]],
        title: str,
        ylabel: str = "",
        filename: Optional[str] = None
    ) -> str:
        """
        生成对比图（多组织对比）

        Args:
            data: {组织名: {指标名: 数值}}
            title: 图表标题
            ylabel: Y轴标签
            filename: 输出文件名

        Returns:
            文件路径
        """
        fig, ax = plt.subplots(figsize=(12, 6))

        orgs = list(data.keys())
        metrics = list(set(m for org_data in data.values() for m in org_data.keys()))

        x = np.arange(len(orgs))
        width = 0.8 / len(metrics)  # 每组柱子宽度

        for i, metric in enumerate(metrics):
            values = [data[org].get(metric, 0) for org in orgs]
            color = self.COLORS.get(metric, self.COLORS["primary"])
            bars = ax.bar(x + i * width, values, width, label=metric, color=color)

        ax.set_xlabel("组织", fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xticks(x + width * (len(metrics) - 1) / 2)
        ax.set_xticklabels(orgs, rotation=15, ha='right')
        ax.legend(loc='upper right')
        ax.grid(axis='y', alpha=0.3)

        plt.tight_layout()

        # 保存
        if filename is None:
            filename = f"comparison_{title.replace(' ', '_')}.png"
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        return str(filepath)

    def generate_weekly_charts(self, week_data: Dict) -> Dict[str, str]:
        """
        为周报生成全套图表

        Args:
            week_data: 周数据 JSON

        Returns:
            {图表名称: 文件路径}
        """
        charts = {}

        organizations = week_data.get("organizations", {})

        # 1. 各组织电量柱状图
        electricity_data = {}
        for org_name, org_data in organizations.items():
            metrics = org_data.get("metrics", {})
            if "合计" in metrics and "电量" in metrics["合计"]:
                electricity_data[org_name] = metrics["合计"]["电量"].get("value", 0)

        if electricity_data:
            charts["electricity_bar"] = self.bar_chart(
                electricity_data,
                title="各组织上网电量对比",
                ylabel="电量（万千瓦时）",
                filename="electricity_bar.png"
            )

        # 2. 能源类型占比饼图（汇总）
        energy_totals = {}
        for org_data in organizations.values():
            for energy_type, energy_metrics in org_data.get("metrics", {}).items():
                if energy_type != "合计":
                    value = energy_metrics.get("电量", {}).get("value", 0)
                    if energy_type in energy_totals:
                        energy_totals[energy_type] += value
                    else:
                        energy_totals[energy_type] = value

        if energy_totals:
            charts["energy_pie"] = self.pie_chart(
                energy_totals,
                title="能源类型电量占比",
                filename="energy_pie.png"
            )

        # 3. 各组织电价对比
        price_data = {}
        for org_name, org_data in organizations.items():
            metrics = org_data.get("metrics", {})
            if "合计" in metrics and "电价" in metrics["合计"]:
                price_data[org_name] = metrics["合计"]["电价"].get("value", 0)

        if price_data:
            charts["price_bar"] = self.bar_chart(
                price_data,
                title="各组织上网电价对比",
                ylabel="电价（元/千瓦时）",
                filename="price_bar.png",
                horizontal=True
            )

        # 4. 组织内部能源类型对比
        for org_name, org_data in organizations.items():
            metrics = org_data.get("metrics", {})
            org_energy_data = {}
            for energy_type, energy_metrics in metrics.items():
                if energy_type != "合计":
                    value = energy_metrics.get("电量", {}).get("value", 0)
                    if value:
                        org_energy_data[energy_type] = value

            if org_energy_data:
                charts[f"{org_name}_energy"] = self.bar_chart(
                    org_energy_data,
                    title=f"{org_name}各能源类型电量",
                    ylabel="电量（万千瓦时）",
                    filename=f"{org_name}_energy.png"
                )

        return charts


def main():
    """测试"""
    builder = ChartBuilder()

    # 测试柱状图
    test_data = {
        "长江电力": 550544,
        "三峡能源": 125680,
        "湖北能源": 89200
    }
    path = builder.bar_chart(test_data, title="电量对比测试", ylabel="万千瓦时")
    print(f"柱状图: {path}")

    # 测试饼图
    pie_data = {
        "水电": 550544,
        "风电": 98500,
        "光伏": 27180
    }
    path = builder.pie_chart(pie_data, title="能源占比测试")
    print(f"饼图: {path}")


if __name__ == "__main__":
    main()