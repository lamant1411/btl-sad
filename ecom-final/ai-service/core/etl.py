"""
AI Service — ETL Pipeline
Xử lý dữ liệu hành vi người dùng thành sequences cho LSTM.
"""
import pandas as pd
import numpy as np
from typing import List, Tuple


def generate_sliding_windows(
    df: pd.DataFrame,
    seq_length: int = 10
) -> pd.DataFrame:
    """
    Chuyển đổi log hành vi người dùng thành các chuỗi tuần tự
    sử dụng kỹ thuật Sliding Window.

    Args:
        df: DataFrame với cột ['user_idx', 'product_idx', 'action_id', 'timestamp']
        seq_length: Độ dài chuỗi tối đa

    Returns:
        DataFrame với cột ['user_idx', 'sequence', 'target_item']
    """
    df = df.sort_values(by=['user_idx', 'timestamp'])

    user_sequences = df.groupby('user_idx').apply(
        lambda x: list(zip(
            x['product_idx'].tolist(),
            x['action_id'].tolist(),
            x['timestamp'].tolist()
        ))
    ).reset_index(name='history')

    final_dataset = []
    for _, row in user_sequences.iterrows():
        user = row['user_idx']
        hist = row['history']

        if len(hist) > 2:
            for i in range(1, len(hist)):
                start_idx = max(0, i - seq_length)
                seq    = [item[0] for item in hist[start_idx:i]]   # product_ids
                target = hist[i][0]                                  # next product_id

                # Padding sequences ngắn hơn seq_length
                padded = [0] * (seq_length - len(seq)) + seq

                final_dataset.append({
                    'user_idx':    user,
                    'sequence':    padded,
                    'target_item': target,
                    'seq_len':     len(seq)
                })

    return pd.DataFrame(final_dataset)


def encode_product_descriptions(products: List[dict]) -> Tuple[np.ndarray, List[int]]:
    """
    Tạo text mô tả cho từng sản phẩm để embed vào FAISS.
    
    Returns:
        Tuple (text_list, product_ids)
    """
    texts       = []
    product_ids = []

    for p in products:
        # Kết hợp name + description + attributes thành 1 text
        attrs_text = ' '.join(str(v) for v in p.get('attributes', {}).values())
        text = f"{p['name']} {p.get('description', '')} {attrs_text} {p.get('category', '')}"
        texts.append(text)
        product_ids.append(p['id'])

    return texts, product_ids


def mock_user_behavior_data(num_users: int = 100, num_items: int = 50) -> pd.DataFrame:
    """Tạo dữ liệu hành vi giả lập để test ETL pipeline."""
    import random
    from datetime import datetime, timedelta

    records = []
    for user_id in range(1, num_users + 1):
        n_actions = random.randint(5, 20)
        ts = datetime.now() - timedelta(days=30)
        for _ in range(n_actions):
            records.append({
                'user_idx':    user_id,
                'product_idx': random.randint(1, num_items),
                'action_id':   random.choice([1, 2, 3]),  # 1=view, 2=cart, 3=buy
                'timestamp':   ts
            })
            ts += timedelta(hours=random.uniform(1, 48))

    return pd.DataFrame(records)
