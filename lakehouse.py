# -----------------------------------------------------------
# Activity 3 - Building a Mini Lakehouse (Datacycle, Unit 2)
# Bronze -> Silver -> Gold with pandas + SQLite
#
# How to run:  python lakehouse.py
# The raw files have to be in data_lab/bronze/ (next to this file).
# The script creates data_lab/silver/, data_lab/gold/ and
# data_lab/lakehouse.db every time it runs. Everything it prints
# is also saved in docs/output.txt.
# -----------------------------------------------------------

import json
import re
import sqlite3
import sys
from pathlib import Path

import pandas as pd

BASE = Path(__file__).parent / "data_lab"
BRONZE = BASE / "bronze"
SILVER = BASE / "silver"
GOLD = BASE / "gold"
DOCS = Path(__file__).parent / "docs"
for folder in (SILVER, GOLD, DOCS):
    folder.mkdir(exist_ok=True)


class Tee:
    """Writes what we print both on the screen and in a file."""

    def __init__(self, *streams):
        self.streams = streams

    def write(self, text):
        for s in self.streams:
            s.write(text)

    def flush(self):
        for s in self.streams:
            s.flush()


output_file = open(DOCS / "output.txt", "w", encoding="utf-8")
sys.stdout = Tee(sys.stdout, output_file)

# a sale is an outlier if it costs more than 10 times the median
# price of the same product
OUTLIER_FACTOR = 10

# products and log actions come in Spanish, we translate them
PRODUCT_NAMES = {"teclado": "keyboard", "raton": "mouse", "ratón": "mouse",
                 "monitor": "monitor"}
LOG_ACTIONS = {"compra": "purchase"}


def title(text):
    print("\n" + "=" * 60)
    print(text)
    print("=" * 60)


def is_int(value):
    """True if the value is a whole number (101, '120'...)."""
    return str(value).strip().isdigit()


# ===========================================================
# PART 1 - BRONZE (raw data: we only read it, we don't change it)
# ===========================================================
title("PART 1 - BRONZE")

# ventas.csv -> structured (CSV with header).
# dtype=str: everything is read as text, so a value like "abc" in
# the amount is kept and we can detect it later.
# skip_blank_lines removes the empty lines of the file.
sales_raw = pd.read_csv(BRONZE / "ventas.csv", dtype=str,
                        keep_default_na=False, skip_blank_lines=True)
with open(BRONZE / "ventas.csv", "rb") as f:
    raw_bytes = f.read()
blank_sales_lines = sum(1 for l in raw_bytes.splitlines() if not l.strip())
windows_endings = b"\r\n" in raw_bytes

# clientes.json -> semi-structured (list of JSON objects)
with open(BRONZE / "clientes.json", encoding="utf-8") as f:
    customers_raw = pd.DataFrame(json.load(f))

# logs.txt -> text log, one event per line: [LEVEL] user=X action=Y
# The pattern is permissive on purpose (user and action are optional)
# so broken lines are also read and we can see what is wrong with them.
log_pattern = re.compile(r"^\[(\w+)\]\s*(?:user=(\S*))?\s*(?:action=(\S*))?\s*$")
log_rows = []
blank_log_lines = 0
with open(BRONZE / "logs.txt", encoding="utf-8") as f:
    for n, line in enumerate(f, start=1):
        line = line.strip()
        if not line:
            blank_log_lines += 1
            continue
        m = log_pattern.match(line)
        if m:
            log_rows.append({"line": n, "level": m.group(1),
                             "user": m.group(2) or "", "action": m.group(3) or ""})
        else:
            log_rows.append({"line": n, "level": "", "user": "", "action": ""})
logs_raw = pd.DataFrame(log_rows)

print("\nFile types:")
print(f"  ventas.csv    -> CSV, structured        {len(sales_raw)} rows "
      f"(+{blank_sales_lines} blank lines, Windows line endings: {windows_endings})")
print(f"  clientes.json -> JSON, semi-structured  {len(customers_raw)} records")
print(f"  logs.txt      -> text log               {len(logs_raw)} events "
      f"(+{blank_log_lines} blank lines)")

print("\nventas.csv (first rows)\n", sales_raw.head(8).to_string(index=False))
print("\nclientes.json (first rows)\n", customers_raw.head(6).to_string(index=False))
print("\nlogs.txt parsed (first rows)\n", logs_raw.head(7).to_string(index=False))

# ---------- automatic checks ----------
print("\nIssues found in Bronze:")

known_ids = {int(i) for i in customers_raw["id_cliente"] if is_int(i)}
amount_num = pd.to_numeric(sales_raw["importe"], errors="coerce")

print("  Sales with empty customer id:",
      sales_raw.loc[sales_raw["id_cliente"].str.strip() == "", "id_pedido"].tolist())
unknown = sales_raw[sales_raw["id_cliente"].apply(is_int)
                    & ~sales_raw["id_cliente"].apply(lambda x: is_int(x) and int(x) in known_ids)]
print("  Sales of customers not in clientes.json:",
      unknown[["id_pedido", "id_cliente"]].values.tolist())
print("  Amount not a number:", sales_raw.loc[amount_num.isna(), "id_pedido"].tolist())
print("  Amount <= 0:", sales_raw.loc[amount_num <= 0, "id_pedido"].tolist())
print("  Product 'test':", sales_raw.loc[sales_raw["producto"] == "test", "id_pedido"].tolist())

# median price of every product, only with the amounts that make sense
medians = (sales_raw.assign(a=amount_num)
           .query("a > 0").groupby("producto")["a"].median())
print("  Median price per product:", medians.to_dict())
dup_mask = sales_raw.duplicated(subset=["id_cliente", "producto", "importe"], keep="first")
print("  Repeated orders (same customer, product, amount):",
      sales_raw.loc[dup_mask, "id_pedido"].tolist())

print("  Customer ids stored as text:",
      [i for i in customers_raw["id_cliente"] if isinstance(i, str)])
print("  Customers with empty name:",
      customers_raw.loc[customers_raw["nombre"].fillna("").str.strip() == "", "id_cliente"].tolist())
print("  Customers with no country or '??':",
      customers_raw.loc[customers_raw["pais"].isna() | (customers_raw["pais"] == "??"),
                        "id_cliente"].tolist())
print("  Possible test accounts:",
      customers_raw.loc[customers_raw["nombre"].fillna("").str.contains("test|debug", case=False),
                        ["id_cliente", "nombre"]].values.tolist())
placeholder = customers_raw["nombre"].fillna("").str.match(r"^user\d+$")
print("  Customers with placeholder name (userN):", int(placeholder.sum()))
print("  Country codes:", customers_raw["pais"].value_counts(dropna=False).to_dict())

print("  Log levels:", logs_raw["level"].value_counts().to_dict())
print("  Log lines without user:", logs_raw.loc[logs_raw["user"] == "", "line"].tolist())
print("  Log lines with empty action:", logs_raw.loc[logs_raw["action"] == "", "line"].tolist())
print("  Log users that are not a number:",
      logs_raw.loc[(logs_raw["user"] != "") & ~logs_raw["user"].apply(is_int), "user"].tolist())
print("  Log users not in clientes.json:",
      sorted({u for u in logs_raw["user"] if is_int(u) and int(u) not in known_ids}))
print("  Missing information: no dates, no currency, no quantity, no contact data")

# raw revenue, adding every amount that is a number (to compare later)
raw_revenue = amount_num.sum()
raw_top = (sales_raw.assign(a=amount_num).groupby("id_cliente")["a"].sum()
           .sort_values(ascending=False))
print(f"  Revenue if we add the raw amounts: {raw_revenue:.2f} EUR "
      f"(top 'customer': {raw_top.index[0]} with {raw_top.iloc[0]:.2f} EUR)")


# ===========================================================
# PART 2 - SILVER (cleaning, normalising and integrating)
# ===========================================================
title("PART 2 - SILVER")

rejected = []   # every rejected row is saved here with its reason

# ---------- 2.1 Customers ----------
customers = customers_raw.rename(columns={"id_cliente": "customer_id",
                                          "nombre": "name",
                                          "pais": "country_code"})
# id "120" comes as text -> everything to integer
customers["customer_id"] = customers["customer_id"].astype(int)

# test accounts (TestUser, Debug) are not real customers
is_test = customers["name"].fillna("").str.contains("test|debug", case=False)
test_ids = set(customers.loc[is_test, "customer_id"])
for _, r in customers[is_test].iterrows():
    rejected.append({"dataset": "customers", "record": r["customer_id"],
                     "data": f"{r['name']} / {r['country_code']}",
                     "reason": "test account"})
customers = customers[~is_test].copy()

# missing values are not deleted: we put "Unknown" and write a note
notes = {cid: [] for cid in customers["customer_id"]}
name = customers["name"].fillna("").str.strip()
for cid in customers.loc[name == "", "customer_id"]:
    notes[cid].append("no name")
for cid in customers.loc[name.str.match(r"^user\d+$"), "customer_id"]:
    notes[cid].append("placeholder name")
country = customers["country_code"].fillna("").str.strip().str.upper()
for cid in customers.loc[country.isin(["", "??"]), "customer_id"]:
    notes[cid].append("no country")

customers["name"] = name.replace("", "Unknown").str.title()
# UK is not an ISO 3166 code, the correct one is GB
customers["country_code"] = (country.replace({"UK": "GB"})
                             .replace({"": "Unknown", "??": "Unknown"}))
customers["quality_notes"] = customers["customer_id"].map(lambda c: "; ".join(notes[c]))
customers["missing_info"] = customers["quality_notes"] != ""
customers = (customers[["customer_id", "name", "country_code",
                        "missing_info", "quality_notes"]]
             .sort_values("customer_id").reset_index(drop=True))
valid_ids = set(customers["customer_id"])

# ---------- 2.2 Sales ----------
# Every rule is checked in order and the row gets the FIRST rule it breaks.
seen = set()


def sales_reason(row):
    cid = row["id_cliente"].strip()
    if cid == "":
        return "empty customer id"
    if not is_int(cid) or (int(cid) not in valid_ids and int(cid) not in test_ids):
        return "customer not in customer file"
    if row["producto"].strip().lower() == "test":
        return "test product"
    amount = pd.to_numeric(row["importe"], errors="coerce")
    if pd.isna(amount):
        return "amount is not a number"
    if amount <= 0:
        return "amount <= 0"
    if amount > OUTLIER_FACTOR * medians[row["producto"]]:
        return "outlier amount"
    key = (cid, row["producto"], amount)
    if key in seen:      # same customer, product and amount as before
        return "duplicated order"
    seen.add(key)
    if int(cid) in test_ids:
        return "test account"
    return None


sales_raw["reason"] = sales_raw.apply(sales_reason, axis=1)
for _, r in sales_raw[sales_raw["reason"].notna()].iterrows():
    rejected.append({"dataset": "sales", "record": r["id_pedido"],
                     "data": f"customer={r['id_cliente'] or '(empty)'} "
                             f"{r['producto']} {r['importe']}",
                     "reason": r["reason"]})

sales = (sales_raw[sales_raw["reason"].isna()]
         .drop(columns="reason")
         .rename(columns={"id_pedido": "order_id", "id_cliente": "customer_id",
                          "producto": "product", "importe": "amount_eur"}))
sales["order_id"] = sales["order_id"].astype(int)
sales["customer_id"] = sales["customer_id"].astype(int)
sales["amount_eur"] = sales["amount_eur"].astype(float).round(2)
sales["product"] = sales["product"].str.strip().str.lower().replace(PRODUCT_NAMES)
sales = sales.reset_index(drop=True)

# ---------- 2.3 Logs ----------
# ERROR = failed actions, DEBUG = technical test events -> both removed.
# WARN (timeouts) are kept because they really happened.


def log_reason(row):
    if row["level"] == "ERROR":
        return "error event"
    if row["level"] == "DEBUG":
        return "debug/test event"
    if row["user"] == "":
        return "no user"
    if row["action"] == "":
        return "empty action"
    if not is_int(row["user"]):
        return "user is not a number"
    if int(row["user"]) in test_ids:
        return "test account"
    if int(row["user"]) not in valid_ids:
        return "customer not in customer file"
    return None


logs_raw["reason"] = logs_raw.apply(log_reason, axis=1)
for _, r in logs_raw[logs_raw["reason"].notna()].iterrows():
    rejected.append({"dataset": "logs", "record": f"line {r['line']}",
                     "data": f"[{r['level']}] user={r['user']} action={r['action']}",
                     "reason": r["reason"]})

logs = (logs_raw[logs_raw["reason"].isna()]
        .drop(columns="reason")
        .rename(columns={"user": "customer_id"}))
logs["customer_id"] = logs["customer_id"].astype(int)
logs["level"] = logs["level"].str.upper()
logs["action"] = logs["action"].str.lower().replace(LOG_ACTIONS)
logs = logs.reset_index(drop=True)

# ---------- 2.4 Save Silver ----------
rejected = pd.DataFrame(rejected)
quality = (rejected.groupby(["dataset", "reason"]).size()
           .reset_index(name="rows").sort_values(["dataset", "rows"], ascending=[True, False]))

sales.to_csv(SILVER / "clean_sales.csv", index=False)
customers.to_csv(SILVER / "clean_customers.csv", index=False)
logs.drop(columns="line").to_csv(SILVER / "clean_logs.csv", index=False)
rejected.to_csv(SILVER / "rejected_records.csv", index=False)
quality.to_csv(SILVER / "quality_report.csv", index=False)

print("\nRows before and after Silver:")
for ds, before, after in [("sales", len(sales_raw), len(sales)),
                          ("customers", len(customers_raw), len(customers)),
                          ("logs", len(logs_raw), len(logs))]:
    print(f"  {ds:<10} bronze={before:<4} silver={after:<4} rejected={before - after}")

print("\nRejected sales\n",
      rejected[rejected["dataset"] == "sales"].to_string(index=False))
print("\nRejected customers\n",
      rejected[rejected["dataset"] == "customers"].to_string(index=False))
print("\nQuality report (rejected rows per rule)\n", quality.to_string(index=False))
print("\nclean_sales (first rows)\n", sales.head().to_string(index=False))
print("\nclean_customers with missing info (not placeholder)\n",
      customers[customers["missing_info"]
                & ~customers["quality_notes"].eq("placeholder name")].to_string(index=False))
print("  customers with missing_info = True:", int(customers["missing_info"].sum()))
print("\nclean_logs levels:", logs["level"].value_counts().to_dict())
print("\nSaved in silver/: clean_sales.csv, clean_customers.csv, clean_logs.csv,"
      " rejected_records.csv, quality_report.csv")


# ===========================================================
# PART 3 - GOLD (OLAP style aggregations with SQL)
# ===========================================================
title("PART 3 - GOLD")

# The Silver tables are loaded in a SQLite database (our "simulated
# database"). sales is the fact table and customers the dimension.
con = sqlite3.connect(BASE / "lakehouse.db")
sales.to_sql("sales", con, if_exists="replace", index=False)
customers.to_sql("customers", con, if_exists="replace", index=False)
logs.drop(columns="line").to_sql("logs", con, if_exists="replace", index=False)

sales_by_customer = pd.read_sql("""
    SELECT c.customer_id, c.name AS customer, c.country_code,
           COUNT(s.order_id) AS num_orders,
           SUM(s.amount_eur) AS total_sales
    FROM sales s
    JOIN customers c ON c.customer_id = s.customer_id
    GROUP BY c.customer_id, c.name, c.country_code
    ORDER BY total_sales DESC, c.customer_id
""", con)

sales_by_product = pd.read_sql("""
    SELECT product,
           COUNT(*)                  AS units_sold,
           SUM(amount_eur)           AS revenue,
           ROUND(AVG(amount_eur), 2) AS avg_price
    FROM sales
    GROUP BY product
    ORDER BY revenue DESC
""", con)

sales_by_country = pd.read_sql("""
    SELECT c.country_code,
           COUNT(DISTINCT c.customer_id) AS customers,
           COUNT(s.order_id)             AS num_orders,
           SUM(s.amount_eur)             AS revenue
    FROM sales s
    JOIN customers c ON c.customer_id = s.customer_id
    GROUP BY c.country_code
    ORDER BY revenue DESC
""", con)
con.close()

total_revenue = sales["amount_eur"].sum()
for df, col in [(sales_by_customer, "total_sales"), (sales_by_product, "revenue"),
                (sales_by_country, "revenue")]:
    df["share_pct"] = (df[col] / total_revenue * 100).round(2)

total = pd.DataFrame([{
    "total_revenue_eur": total_revenue,
    "num_orders": len(sales),
    "num_customers": sales["customer_id"].nunique(),
    "avg_order_eur": round(total_revenue / len(sales), 2),
    "raw_revenue_eur": raw_revenue,
}])

sales_by_customer.to_csv(GOLD / "sales_by_customer.csv", index=False)
sales_by_product.to_csv(GOLD / "sales_by_product.csv", index=False)
sales_by_country.to_csv(GOLD / "sales_by_country.csv", index=False)
total.to_csv(GOLD / "total_revenue.csv", index=False)

print("\nSales by customer (top 10 of", len(sales_by_customer), ")\n",
      sales_by_customer.head(10).to_string(index=False))
print("  customers tied at 210 EUR:", int((sales_by_customer["total_sales"] == 210).sum()))
print("\nSales by product\n", sales_by_product.to_string(index=False))
print("\nSales by country\n", sales_by_country.to_string(index=False))
print("\nTotal revenue\n", total.to_string(index=False))
print(f"  raw revenue is {(raw_revenue / total_revenue - 1) * 100:.1f} % higher than the clean one")

# ---------- answers ----------
top_c = sales_by_customer.iloc[0]
top_p = sales_by_product.iloc[0]
print(f"\nLargest buyer: {top_c['customer']} (id {top_c['customer_id']}) "
      f"with {top_c['total_sales']:.2f} EUR")
print(f"Product with most revenue: {top_p['product']} with {top_p['revenue']:.2f} EUR")
print("\nSaved in gold/: sales_by_customer.csv, sales_by_product.csv,"
      " sales_by_country.csv, total_revenue.csv")
