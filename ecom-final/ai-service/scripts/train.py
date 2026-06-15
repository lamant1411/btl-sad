"""
train.py — Script huấn luyện mô hình LSTM/DIN trên Google Colab / Local GPU.

Cách dùng trên Colab:
1. Nén thư mục `dataset/processed` và thư mục `models` rồi up lên Google Drive.
2. Mở Google Colab, chọn Runtime -> Change runtime type -> T4 GPU.
3. Mount Google Drive và chạy lệnh:
   !python train.py --data_dir /content/drive/MyDrive/processed --model din
"""

import argparse
import json
import os
from pathlib import Path

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import pandas as pd
from tqdm import tqdm

# Import models
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models.lstm import LSTMRec
from models.din import DINModel

class EcomSequenceDataset(Dataset):
    """Custom Dataset cho DataLoader."""
    def __init__(self, parquet_path, max_seq_len=10):
        print(f"Loading data from {parquet_path}...")
        self.df = pd.read_parquet(parquet_path)
        self.max_seq_len = max_seq_len
        print(f"Loaded {len(self.df)} sequences.")

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        seq = row['sequence']
        
        # Chỉ lấy product_idx làm input history
        product_seq = [item[0] for item in seq]
        
        # Padding
        if len(product_seq) >= self.max_seq_len:
            product_seq = product_seq[-self.max_seq_len:]
            mask = [1] * self.max_seq_len
        else:
            pad_len = self.max_seq_len - len(product_seq)
            mask = [0] * pad_len + [1] * len(product_seq)
            product_seq = [0] * pad_len + product_seq
            
        target = row['target_item']
        
        return (
            torch.tensor(product_seq, dtype=torch.long), 
            torch.tensor(target, dtype=torch.long),
            torch.tensor(mask, dtype=torch.float)
        )

def train_model(args):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training on device: {device} | Model: {args.model.upper()}")

    # 1. Load Metadata
    data_dir = Path(args.data_dir)
    meta_path = data_dir / "merged_meta.json"
    if not meta_path.exists():
        meta_path = data_dir / "retailrocket_meta.json"
        
    with open(meta_path, 'r') as f:
        meta = json.load(f)
        
    num_items = meta["num_items"] + 1  
    print(f"Total vocabulary size (num_items): {num_items}")

    # 2. Chuẩn bị DataLoader
    seq_file = data_dir / "merged_sequences.parquet"
    if not seq_file.exists():
        seq_file = data_dir / "retailrocket_sequences.parquet"

    dataset = EcomSequenceDataset(seq_file, max_seq_len=10)
    train_size = int(0.8 * len(dataset))
    val_size = len(dataset) - train_size
    train_dataset, val_dataset = torch.utils.data.random_split(dataset, [train_size, val_size])
    
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True, num_workers=2)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size, shuffle=False)

    # 3. Khởi tạo Model
    if args.model == "lstm":
        model = LSTMRec(num_items=num_items, embed_dim=64, hidden_dim=128).to(device)
        criterion = nn.CrossEntropyLoss(ignore_index=0)
    else:
        model = DINModel(num_items=num_items, embed_dim=64, attn_hidden=32).to(device)
        criterion = nn.BCEWithLogitsLoss()
        
    optimizer = optim.Adam(model.parameters(), lr=args.lr)

    # 4. Training Loop
    best_loss = float('inf')
    
    for epoch in range(1, args.epochs + 1):
        model.train()
        total_loss = 0
        
        progress_bar = tqdm(train_loader, desc=f"Epoch {epoch}/{args.epochs}")
        for sequences, targets, masks in progress_bar:
            sequences, targets, masks = sequences.to(device), targets.to(device), masks.to(device)
            
            optimizer.zero_grad()
            
            if args.model == "lstm":
                logits = model(sequences)
                loss = criterion(logits, targets)
            else:
                # DIN: Cần tính điểm cho target thật (Positive) và target ngẫu nhiên (Negative)
                pos_scores = model(sequences, targets, mask=masks)
                pos_labels = torch.ones_like(pos_scores)
                
                neg_targets = torch.randint(1, num_items, targets.shape, device=device)
                neg_scores = model(sequences, neg_targets, mask=masks)
                neg_labels = torch.zeros_like(neg_scores)
                
                scores = torch.cat([pos_scores, neg_scores], dim=0)
                labels = torch.cat([pos_labels, neg_labels], dim=0)
                
                loss = criterion(scores, labels)

            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
            progress_bar.set_postfix(loss=loss.item())
            
        avg_train_loss = total_loss / len(train_loader)
        
        # Validation
        model.eval()
        val_loss = 0
        correct = 0
        with torch.no_grad():
            for sequences, targets, masks in val_loader:
                sequences, targets, masks = sequences.to(device), targets.to(device), masks.to(device)
                
                if args.model == "lstm":
                    logits = model(sequences)
                    val_loss += criterion(logits, targets).item()
                    preds = logits.argmax(dim=-1)
                    correct += (preds == targets).sum().item()
                else:
                    pos_scores = model(sequences, targets, mask=masks)
                    neg_targets = torch.randint(1, num_items, targets.shape, device=device)
                    neg_scores = model(sequences, neg_targets, mask=masks)
                    
                    scores = torch.cat([pos_scores, neg_scores], dim=0)
                    labels = torch.cat([torch.ones_like(pos_scores), torch.zeros_like(neg_scores)], dim=0)
                    
                    val_loss += criterion(scores, labels).item()
                    preds = (torch.sigmoid(scores) > 0.5).float()
                    correct += (preds == labels).sum().item()
                
        avg_val_loss = val_loss / len(val_loader)
        
        # Calculate Accuracy (cách tính khác nhau do Binary vs Multi-class)
        if args.model == "lstm":
            accuracy = correct / len(val_dataset)
        else:
            accuracy = correct / (2 * len(val_dataset)) # Vì có 1 pos + 1 neg
            
        print(f"Epoch {epoch} | Train Loss: {avg_train_loss:.4f} | Val Loss: {avg_val_loss:.4f} | Val Acc: {accuracy:.4f}")
        
        # Save best model
        if avg_val_loss < best_loss:
            best_loss = avg_val_loss
            save_path = f"{args.model}_best_model.pth"
            torch.save(model.state_dict(), save_path)
            print(f"  -> Saved best model to {save_path}")

    print(f"Training Complete! Best validation loss: {best_loss:.4f}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", type=str, default="../dataset/processed")
    parser.add_argument("--model", type=str, choices=["lstm", "din"], default="lstm")
    parser.add_argument("--batch_size", type=int, default=256)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--lr", type=float, default=0.001)
    args = parser.parse_args()
    
    train_model(args)
