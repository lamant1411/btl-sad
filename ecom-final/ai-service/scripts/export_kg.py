import pandas as pd
import os
from pathlib import Path

def export_kg_csv(parquet_path: str, out_dir: str):
    print(f"Reading data from {parquet_path}...")
    df = pd.read_parquet(parquet_path)
    
    # Tạo thư mục đầu ra
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    
    # 1. Export Users Node
    print("Exporting users.csv...")
    users = pd.DataFrame({'user_idx': df['user_idx'].unique()})
    users.to_csv(out / 'users.csv', index=False)
    
    # 2. Export Products Node
    print("Exporting products.csv...")
    products = pd.DataFrame({'product_idx': df['product_idx'].unique()})
    products.to_csv(out / 'products.csv', index=False)
    
    # 3. Mappings cho các loại Relationships
    # Theo merged_meta.json: 1: view, 3: cart, 5: purchase
    action_mapping = {
        1: 'views.csv',
        3: 'adds_to_cart.csv',
        5: 'purchases.csv'
    }
    
    print("Exporting relationships...")
    for action_id, filename in action_mapping.items():
        rel_df = df[df['action_id'] == action_id][['user_idx', 'product_idx', 'timestamp']]
        if not rel_df.empty:
            # Xóa trùng lặp để graph bớt nặng (nếu user view cùng 1 SP nhiều lần, giữ lần mới nhất)
            rel_df = rel_df.sort_values('timestamp').drop_duplicates(subset=['user_idx', 'product_idx'], keep='last')
            rel_df.to_csv(out / filename, index=False)
            print(f"  -> {filename}: {len(rel_df)} edges")

    print(f"\n✅ All Knowledge Graph CSVs have been exported to: {out_dir}")

if __name__ == "__main__":
    parquet_file = "ai-service/dataset/processed/merged_interactions.parquet"
    output_directory = "ai-service/dataset/kg_data"
    
    if os.path.exists(parquet_file):
        export_kg_csv(parquet_file, output_directory)
    else:
        print(f"Lỗi: Không tìm thấy file {parquet_file}. Vui lòng chạy lệnh gộp (merge) dataset trước!")
