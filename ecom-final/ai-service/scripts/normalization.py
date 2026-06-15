"""
normalization.py — Data Normalization Pipeline
Chuẩn hóa 2 bộ dữ liệu ecommerce thành định dạng thống nhất cho training DIN/LSTM.

Datasets:
  - RetailRocket: events.csv + item_properties_part1/2.csv + category_tree.csv
  - Cosmetics Shop: 2019-Dec.csv (hoặc các tháng khác)

Output format (chung):
  DataFrame với các cột:
    user_idx      int  — ID user đã compact (bắt đầu từ 1)
    product_idx   int  — ID sản phẩm đã compact (bắt đầu từ 1)
    action_id     int  — 1=view, 3=cart, 5=purchase
    timestamp     int  — Unix timestamp (giây)
    sequence      list — Chuỗi (product_idx, action_id, timestamp) quá khứ
    target_item   int  — Sản phẩm mục tiêu cần dự đoán
    target_action int  — Action của mục tiêu

Usage:
    python normalization.py --dataset retailrocket --input dataset/ --output dataset/processed/
    python normalization.py --dataset cosmetics    --input dataset/2019-Dec.csv --output dataset/processed/
"""
import argparse
import os
import pickle
import json
from pathlib import Path

import numpy as np
import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

# Trọng số hành vi (dùng để lọc & tính điểm khi merge datasets)
ACTION_WEIGHT = {"view": 1, "addtocart": 3, "cart": 3, "transaction": 5, "purchase": 5,
                 "remove_from_cart": -1}

# Tối thiểu số tương tác của 1 sản phẩm để giữ lại
MIN_ITEM_INTERACTIONS = 50

# Tối thiểu độ dài lịch sử của 1 user để giữ lại
MIN_USER_INTERACTIONS = 3


# ─────────────────────────────────────────────────────────────────────────────
# BƯỚC 0: TIỆN ÍCH DÙNG CHUNG
# ─────────────────────────────────────────────────────────────────────────────

def compact_ids(df: pd.DataFrame, col: str, new_col: str) -> tuple:
    """
    Tái index ID liên tục từ 1 (tránh lãng phí embedding slots).
    Trả về (df_updated, mapping_dict) để có thể reverse-map sau này.
    """
    categories = df[col].astype("category")
    df[new_col] = categories.cat.codes + 1          # 0 dành cho <PAD>
    mapping = dict(enumerate(categories.cat.categories, start=1))
    return df, mapping


def filter_cold_items(df: pd.DataFrame, item_col: str, min_count: int) -> pd.DataFrame:
    """Loại bỏ cold-start items (ít tương tác)."""
    counts = df[item_col].value_counts()
    valid  = counts[counts >= min_count].index
    before = len(df)
    df     = df[df[item_col].isin(valid)].copy()
    print(f"  [filter_cold_items] {before:,} → {len(df):,} rows (giữ items >= {min_count} interactions)")
    return df


def filter_cold_users(df: pd.DataFrame, user_col: str, min_count: int) -> pd.DataFrame:
    """Loại bỏ cold-start users (ít lịch sử)."""
    counts = df[user_col].value_counts()
    valid  = counts[counts >= min_count].index
    before = len(df)
    df     = df[df[user_col].isin(valid)].copy()
    print(f"  [filter_cold_users] {before:,} → {len(df):,} rows (giữ users >= {min_count} actions)")
    return df


def generate_sliding_windows(df: pd.DataFrame, seq_length: int = 10) -> pd.DataFrame:
    """
    Áp dụng thuật toán Sliding Window để tạo chuỗi đầu vào cho mô hình DL.

    Với mỗi user có lịch sử [a, b, c, d, e], seq_length=3, tạo ra:
      sequence=[a,b,c] → target=d
      sequence=[b,c,d] → target=e
    """
    print(f"  [windowing] Tạo sequences (L={seq_length}) từ {df['user_idx'].nunique():,} users...")

    df = df.sort_values(["user_idx", "timestamp"])

    # Gom nhóm theo user
    user_histories = (
        df.groupby("user_idx")
        .apply(lambda g: list(zip(g["product_idx"], g["action_id"], g["timestamp"])))
        .reset_index(name="history")
    )

    records = []
    for _, row in user_histories.iterrows():
        hist = row["history"]
        uid  = row["user_idx"]
        if len(hist) <= 2:
            continue
        for i in range(1, len(hist)):
            start    = max(0, i - seq_length)
            seq      = hist[start:i]
            target   = hist[i]
            records.append({
                "user_idx":     uid,
                "sequence":     seq,                # List[(product_idx, action_id, ts)]
                "target_item":  target[0],          # product_idx
                "target_action": target[1],         # action_id
            })

    result = pd.DataFrame(records)
    print(f"  [windowing] ✅ {len(result):,} sequences tạo thành công.")
    return result


def save_outputs(
    df_raw:     pd.DataFrame,
    df_windows: pd.DataFrame,
    item_map:   dict,
    user_map:   dict,
    out_dir:    Path,
    prefix:     str,
):
    """Lưu tất cả output: raw normalized, windows, mappings."""
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Raw normalized interactions
    raw_path = out_dir / f"{prefix}_interactions.parquet"
    df_raw.to_parquet(raw_path, index=False)
    print(f"  💾 Saved raw interactions → {raw_path}  ({len(df_raw):,} rows)")

    # 2. Sliding window sequences
    win_path = out_dir / f"{prefix}_sequences.parquet"
    df_windows.to_parquet(win_path, index=False)
    print(f"  💾 Saved sequences       → {win_path}  ({len(df_windows):,} rows)")

    # 3. ID mappings (JSON để dễ đọc)
    maps = {
        "num_items":  int(df_raw["product_idx"].max()),
        "num_users":  int(df_raw["user_idx"].max()),
        "action_map": {"view": 1, "cart/addtocart": 3, "purchase/transaction": 5},
        "item_map_sample": {str(k): v for k, v in list(item_map.items())[:5]},
    }
    map_path = out_dir / f"{prefix}_meta.json"
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump(maps, f, ensure_ascii=False, indent=2)
    print(f"  💾 Saved metadata        → {map_path}")

    # 4. Full mappings (pickle cho training)
    pkl_path = out_dir / f"{prefix}_mappings.pkl"
    with open(pkl_path, "wb") as f:
        pickle.dump({"item_map": item_map, "user_map": user_map}, f)
    print(f"  💾 Saved full mappings   → {pkl_path}")

    return {
        "num_items": int(df_raw["product_idx"].max()),
        "num_users": int(df_raw["user_idx"].max()),
        "num_sequences": len(df_windows),
    }


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE 1: RETAILROCKET
# ─────────────────────────────────────────────────────────────────────────────

def etl_retailrocket(input_dir: str, output_dir: str, seq_length: int = 10) -> pd.DataFrame:
    """
    Pipeline chuẩn hóa đầy đủ cho RetailRocket dataset.

    Files cần có trong input_dir:
      - events.csv               (bắt buộc)
      - item_properties_part1.csv (tuỳ chọn — để lấy category)
      - item_properties_part2.csv (tuỳ chọn)
      - category_tree.csv        (tuỳ chọn — để build category hierarchy)
    """
    print("\n" + "="*60)
    print("[PIPELINE 1] RetailRocket ETL")
    print("="*60)

    in_dir = Path(input_dir)

    # ── Bước 1: Load events ─────────────────────────────────────
    events_path = in_dir / "events.csv"
    print(f"\n[1/6] Loading events từ {events_path} ...")
    df = pd.read_csv(events_path, dtype={
        "timestamp":     "int64",
        "visitorid":     "int64",
        "event":         "str",
        "itemid":        "int64",
        "transactionid": "float64",
    })
    print(f"  Raw: {len(df):,} events | {df.visitorid.nunique():,} users | {df.itemid.nunique():,} items")
    print(f"  Event distribution: {df.event.value_counts().to_dict()}")

    # ── Bước 2: Chuẩn hóa cấu trúc ──────────────────────────────
    print("\n[2/6] Structural mapping...")
    df = df.rename(columns={
        "visitorid": "user_id",
        "itemid":    "product_id",
        "event":     "action",
    })
    # RetailRocket timestamp: milliseconds → seconds
    df["timestamp"] = (df["timestamp"] / 1000).astype("int64")

    # ── Bước 3: Mã hóa hành vi ─────────────────────────────────
    print("\n[3/6] Action encoding...")
    action_map = {"view": 1, "addtocart": 3, "transaction": 5}
    df["action_id"] = df["action"].map(action_map)
    invalid = df["action_id"].isna().sum()
    if invalid > 0:
        print(f"  Warning: {invalid} hàng có action không nhận dạng được, bỏ qua.")
    df = df.dropna(subset=["action_id"])
    df["action_id"] = df["action_id"].astype("int8")

    # ── Bước 4: Load category (nếu có item_properties) ──────────
    print("\n[4/6] Enriching with category info (nếu có)...")
    item_category = {}
    props_paths = [in_dir / "item_properties_part1.csv", in_dir / "item_properties_part2.csv"]
    existing_props = [p for p in props_paths if p.exists()]

    if existing_props:
        dfs_props = []
        for pp in existing_props:
            tmp = pd.read_csv(pp, usecols=["itemid", "property", "value"],
                              dtype={"itemid": "int64", "property": "str", "value": "str"})
            dfs_props.append(tmp)
        props = pd.concat(dfs_props, ignore_index=True)
        cat_props = props[props["property"] == "categoryid"].copy()
        cat_props["categoryid"] = pd.to_numeric(cat_props["value"], errors="coerce")
        cat_props = cat_props.dropna(subset=["categoryid"])
        # Lấy category mới nhất của mỗi item
        cat_latest = cat_props.sort_values("itemid").groupby("itemid").last().reset_index()
        item_category = dict(zip(cat_latest["itemid"].astype(int),
                                 cat_latest["categoryid"].astype(int)))
        print(f"  Success: Loaded categories cho {len(item_category):,} items")
        df["category_id"] = df["product_id"].map(item_category).fillna(-1).astype("int64")
    else:
        print("  Warning: Không tìm thấy item_properties files. Bỏ qua category enrichment.")
        df["category_id"] = -1

    # ── Bước 5: Lọc cold-start ──────────────────────────────────
    print("\n[5/6] Filtering cold-start...")
    df = filter_cold_items(df, "product_id", MIN_ITEM_INTERACTIONS)
    df = filter_cold_users(df, "user_id",    MIN_USER_INTERACTIONS)

    # ── Bước 6: Compact IDs ─────────────────────────────────────
    print("\n[6/6] Compacting IDs...")
    df, item_map = compact_ids(df, "product_id", "product_idx")
    df, user_map = compact_ids(df, "user_id",    "user_idx")

    num_items = int(df["product_idx"].max())
    num_users = int(df["user_idx"].max())
    print(f"  num_items={num_items:,} | num_users={num_users:,}")

    # ── Sliding Window ──────────────────────────────────────────
    print("\n[Windowing]")
    df_windows = generate_sliding_windows(df, seq_length)

    # ── Lưu output ──────────────────────────────────────────────
    print("\n[Saving]")
    stats = save_outputs(df, df_windows, item_map, user_map,
                         Path(output_dir), "retailrocket")

    print("  [OK] RetailRocket ETL hoan tat!")
    return df_windows


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE 2: COSMETICS SHOP
# ─────────────────────────────────────────────────────────────────────────────

def etl_cosmetics(input_path: str, output_dir: str, seq_length: int = 10,
                  sample_rows: int = None) -> pd.DataFrame:
    """
    Pipeline chuẩn hóa đầy đủ cho Cosmetics Shop dataset.

    Hỗ trợ load nhiều tháng bằng cách truyền glob pattern hoặc thư mục.
    Ví dụ: input_path='dataset/2019-*.csv' hoặc 'dataset/2019-Dec.csv'

    Args:
        sample_rows: Số dòng lấy mẫu (None = load toàn bộ). Dùng khi test.
    """
    print("\n" + "="*60)
    print("[PIPELINE 2] Cosmetics Shop ETL")
    print("="*60)

    # ── Bước 1: Load CSV (hỗ trợ nhiều file) ────────────────────
    print(f"\n[1/6] Loading từ {input_path} ...")

    input_p = Path(input_path)
    if input_p.is_dir():
        files = sorted(input_p.glob("*.csv"))
    elif "*" in str(input_path):
        import glob as _glob
        files = sorted(_glob.glob(str(input_path)))
    else:
        files = [input_p]

    if not files:
        raise FileNotFoundError(f"Không tìm thấy CSV file tại: {input_path}")

    print(f"  Found {len(files)} file(s): {[f.name for f in files]}")
    dfs = []
    for f in files:
        chunk = pd.read_csv(f, nrows=sample_rows, dtype={
            "event_time":  "str",
            "event_type":  "str",
            "product_id":  "int64",
            "category_id": "int64",
            "price":       "float64",
            "user_id":     "int64",
        }, low_memory=False)
        dfs.append(chunk)
    df = pd.concat(dfs, ignore_index=True)
    print(f"  Raw: {len(df):,} events | {df.user_id.nunique():,} users | "
          f"{df.product_id.nunique():,} items")
    print(f"  Event types: {df.event_type.value_counts().to_dict()}")

    # ── Bước 2: Chuẩn hóa cấu trúc ──────────────────────────────
    print("\n[2/6] Structural mapping...")
    df = df.rename(columns={
        "event_time":  "timestamp",
        "event_type":  "action",
        "user_id":     "user_id",
        "product_id":  "product_id",
    })

    # Chuyển đổi timestamp string → unix seconds
    # Format: "2019-12-01 00:00:00 UTC"
    df["timestamp"] = (
        pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        .astype("int64") // 10**9
    )
    invalid_ts = df["timestamp"].isna().sum()
    if invalid_ts > 0:
        print(f"  Warning: {invalid_ts} hàng có timestamp không hợp lệ, bỏ qua.")
    df = df.dropna(subset=["timestamp"])
    df["timestamp"] = df["timestamp"].astype("int64")

    # ── Bước 3: Mã hóa hành vi ─────────────────────────────────
    print("\n[3/6] Action encoding...")
    # Cosmetics có 4 action types
    action_map = {
        "view":             1,
        "cart":             3,
        "remove_from_cart": 2,   # Encode riêng để không xóa dữ liệu
        "purchase":         5,
    }
    df["action_id"] = df["action"].map(action_map)
    invalid = df["action_id"].isna().sum()
    if invalid > 0:
        print(f"  Warning: {invalid} hàng có action không nhận dạng được → bỏ qua.")
    df = df.dropna(subset=["action_id"])
    df["action_id"] = df["action_id"].astype("int8")

    # ── Bước 4: Xử lý thông tin bổ sung ─────────────────────────
    print("\n[4/6] Enriching with product metadata...")
    # Chuẩn hóa category_code (nhiều hàng bị NaN)
    if "category_code" in df.columns:
        df["category_code"] = df["category_code"].fillna("unknown")
        # Lấy top-level category từ "electronics.smartphone" → "electronics"
        df["category_top"] = df["category_code"].apply(
            lambda x: str(x).split(".")[0] if pd.notna(x) else "unknown"
        )
    # Normalize price
    if "price" in df.columns:
        df["price"] = df["price"].fillna(0.0).clip(lower=0)
        print(f"  Price range: {df['price'].min():.2f} – {df['price'].max():.2f}")

    # ── Bước 5: Lọc cold-start ──────────────────────────────────
    print("\n[5/6] Filtering cold-start...")
    # Loại bỏ remove_from_cart (action_id=2) khỏi cold-start count
    # vì chúng không phản ánh intent mua hàng
    df_positive = df[df["action_id"] != 2]
    df = filter_cold_items(df_positive, "product_id", MIN_ITEM_INTERACTIONS)
    df = filter_cold_users(df,          "user_id",    MIN_USER_INTERACTIONS)

    # ── Bước 6: Compact IDs ─────────────────────────────────────
    print("\n[6/6] Compacting IDs...")
    df, item_map = compact_ids(df, "product_id", "product_idx")
    df, user_map = compact_ids(df, "user_id",    "user_idx")

    num_items = int(df["product_idx"].max())
    num_users = int(df["user_idx"].max())
    print(f"  num_items={num_items:,} | num_users={num_users:,}")

    # ── Sliding Window ──────────────────────────────────────────
    print("\n[Windowing]")
    df_windows = generate_sliding_windows(df, seq_length)

    # ── Lưu output ──────────────────────────────────────────────
    print("\n[Saving]")
    stats = save_outputs(df, df_windows, item_map, user_map,
                         Path(output_dir), "cosmetics")

    print("  [OK] Cosmetics ETL hoan tat!")
    return df_windows


# ─────────────────────────────────────────────────────────────────────────────
# MERGE: KẾT HỢP 2 BỘ DỮ LIỆU (OPTIONAL)
# ─────────────────────────────────────────────────────────────────────────────

def merge_datasets(out_dir: str):
    """
    Kết hợp RetailRocket và Cosmetics thành 1 tập dữ liệu unified.
    Compact lại toàn bộ IDs sau khi merge để tránh xung đột index.
    """
    print("\n" + "="*60)
    print("[MERGE] Ket hop 2 bo du lieu")
    print("="*60)

    out = Path(out_dir)
    rr_path  = out / "retailrocket_interactions.parquet"
    cos_path = out / "cosmetics_interactions.parquet"

    if not rr_path.exists() or not cos_path.exists():
        print("  Warning: Cần chạy cả 2 pipeline trước khi merge.")
        return

    df_rr  = pd.read_parquet(rr_path)
    df_cos = pd.read_parquet(cos_path)

    # Thêm nguồn gốc để phân biệt
    df_rr["source"]  = "retailrocket"
    df_cos["source"] = "cosmetics"

    # Chọn cột chung
    common = ["user_id", "product_id", "action_id", "timestamp", "source"]
    df_merged = pd.concat([
        df_rr[common],
        df_cos[common],
    ], ignore_index=True)

    # Compact lại toàn bộ IDs trong không gian mới
    df_merged, item_map = compact_ids(df_merged, "product_id", "product_idx")
    df_merged, user_map = compact_ids(df_merged, "user_id",    "user_idx")

    df_windows = generate_sliding_windows(df_merged, seq_length=10)
    save_outputs(df_merged, df_windows, item_map, user_map, out, "merged")

    print(f"Success: Merged {len(df_merged):,} interactions | "
          f"{df_merged['product_idx'].max():,} items | {df_windows.shape[0]:,} sequences")
    return df_windows


# ─────────────────────────────────────────────────────────────────────────────
# CLI ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Data Normalization Pipeline cho RetailRocket & Cosmetics Shop",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--dataset", choices=["retailrocket", "cosmetics", "both", "merge"],
        required=True,
        help=(
            "retailrocket — chạy pipeline RetailRocket\n"
            "cosmetics    — chạy pipeline Cosmetics\n"
            "both         — chạy cả 2 pipeline\n"
            "merge        — kết hợp output của 2 pipeline"
        ),
    )
    parser.add_argument(
        "--input", default="dataset/",
        help="Thư mục chứa dataset (cho retailrocket) hoặc file CSV (cho cosmetics)",
    )
    parser.add_argument(
        "--output", default="dataset/processed/",
        help="Thư mục lưu kết quả",
    )
    parser.add_argument(
        "--seq-length", type=int, default=10,
        help="Độ dài chuỗi Sliding Window (default: 10)",
    )
    parser.add_argument(
        "--sample", type=int, default=None,
        help="Lấy mẫu N dòng (dùng để test nhanh, default: None = toàn bộ)",
    )
    args = parser.parse_args()

    if args.dataset in ("retailrocket", "both"):
        etl_retailrocket(args.input, args.output, args.seq_length)

    if args.dataset in ("cosmetics", "both"):
        cos_input = args.input
        # Nếu là thư mục → tìm file cosmetics tự động
        if Path(cos_input).is_dir():
            candidates = list(Path(cos_input).glob("20*.csv"))
            if candidates:
                cos_input = str(candidates[0])
                print(f"  Auto-detected cosmetics file: {cos_input}")
            else:
                print("  Warning: Không tìm thấy file Cosmetics CSV trong thư mục.")
        etl_cosmetics(cos_input, args.output, args.seq_length, args.sample)

    if args.dataset == "merge":
        merge_datasets(args.output)

    print("\n[DONE] Pipeline hoan thanh!")


if __name__ == "__main__":
    main()
