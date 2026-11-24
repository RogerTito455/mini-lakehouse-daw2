# -----------------------------------------------------------
# Activity 3 - Mini Lakehouse: charts for the report
# Reads the Silver / Gold tables made by lakehouse.py and saves
# the charts as PNG in docs/img/.
#
# How to run (after lakehouse.py):  python charts.py
# -----------------------------------------------------------

from pathlib import Path

import matplotlib
matplotlib.use("Agg")          # no window, we only save the images
import matplotlib.pyplot as plt
import pandas as pd

BASE = Path(__file__).parent
SILVER = BASE / "data_lab" / "silver"
GOLD = BASE / "data_lab" / "gold"
IMG = BASE / "docs" / "img"
IMG.mkdir(parents=True, exist_ok=True)

BLUE = "#2f5d8a"
GREY = "#b8c4d0"
RED = "#c0504d"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False})


def save(fig, name):
    fig.tight_layout()
    fig.savefig(IMG / f"{name}.png", dpi=150)
    plt.close(fig)
    print("saved", IMG / f"{name}.png")


# 1) rejected records by dataset and reason
quality = pd.read_csv(SILVER / "quality_report.csv")
quality["label"] = quality["dataset"] + ": " + quality["reason"]
quality = quality.sort_values("rows")
fig, ax = plt.subplots(figsize=(7, 4.2))
ax.barh(quality["label"], quality["rows"], color=BLUE)
for y, v in enumerate(quality["rows"]):
    ax.text(v + 0.4, y, str(v), va="center")
ax.set_xlabel("Rejected rows")
ax.set_title("Records rejected in the Silver layer")
save(fig, "rejected_records")

# 2) top 10 customers by total sales
top = pd.read_csv(GOLD / "sales_by_customer.csv").head(10).iloc[::-1]
labels = top["customer"] + " (" + top["customer_id"].astype(str) + ")"
fig, ax = plt.subplots(figsize=(7, 4))
ax.barh(labels, top["total_sales"], color=[GREY] * 9 + [BLUE])
for y, v in enumerate(top["total_sales"]):
    ax.text(v + 3, y, f"{v:.0f}", va="center")
ax.set_xlabel("Total sales (EUR)")
ax.set_title("Top 10 customers by total sales")
save(fig, "top_customers")

# 3) total revenue before and after cleaning
total = pd.read_csv(GOLD / "total_revenue.csv").iloc[0]
values = [total["raw_revenue_eur"], total["total_revenue_eur"]]
fig, ax = plt.subplots(figsize=(5.5, 3.8))
bars = ax.bar(["Raw data (Bronze)", "Clean data (Silver/Gold)"], values,
              color=[RED, BLUE], width=0.5)
for b, v in zip(bars, values):
    ax.text(b.get_x() + b.get_width() / 2, v + 300, f"{v:,.0f} EUR", ha="center")
ax.set_ylabel("Revenue (EUR)")
ax.set_ylim(0, max(values) * 1.15)
ax.set_title("Total revenue before and after cleaning")
save(fig, "revenue_raw_vs_clean")

# 4) revenue by product
prod = pd.read_csv(GOLD / "sales_by_product.csv")
pct = prod["revenue"] / prod["revenue"].sum() * 100
fig, ax = plt.subplots(figsize=(6.5, 3.8))
bars = ax.bar(prod["product"], prod["revenue"], color=[BLUE, GREY, GREY], width=0.5)
for b, v, p in zip(bars, prod["revenue"], pct):
    ax.text(b.get_x() + b.get_width() / 2, v + 250, f"{v:,.0f} EUR\n({p:.1f} %)",
            ha="center")
ax.set_ylabel("Revenue (EUR)")
ax.set_ylim(0, prod["revenue"].max() * 1.25)
ax.set_xlim(-0.6, 2.6)
ax.set_title("Revenue by product")
save(fig, "sales_by_product")
