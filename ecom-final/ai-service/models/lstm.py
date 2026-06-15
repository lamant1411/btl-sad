"""
AI Service — LSTM Recommendation Model
"""
import torch
import torch.nn as nn


class LSTMRec(nn.Module):
    """
    Long Short-Term Memory Recommendation Model.
    Dự đoán sản phẩm tiếp theo dựa trên lịch sử hành vi mua sắm.

    Architecture:
        Item Embedding → LSTM (Cell State) → FC → Logits (next-item prediction)
    """

    def __init__(self, num_items: int, embed_dim: int = 64, hidden_dim: int = 128,
                 num_layers: int = 1, dropout: float = 0.1):
        """
        Args:
            num_items:  Tổng số sản phẩm (vocabulary size)
            embed_dim:  Kích thước embedding vector
            hidden_dim: Kích thước hidden state của LSTM
            num_layers: Số lớp LSTM xếp chồng
            dropout:    Tỷ lệ dropout (regularization)
        """
        super(LSTMRec, self).__init__()

        # Embedding layer — chuyển product_id → dense vector
        # padding_idx=0: bỏ qua các vị trí padding
        self.item_embedding = nn.Embedding(num_items, embed_dim, padding_idx=0)

        # LSTM — nắm bắt chuỗi hành vi qua Cell State (khắc phục vanishing gradient của RNN)
        self.lstm = nn.LSTM(
            input_size=embed_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0
        )

        # Dropout regularization
        self.dropout = nn.Dropout(dropout)

        # Output layer — dự đoán xác suất cho từng sản phẩm
        self.fc = nn.Linear(hidden_dim, num_items)

        # Khởi tạo weights
        self._init_weights()

    def _init_weights(self):
        """Xavier initialization cho các tham số."""
        nn.init.xavier_uniform_(self.fc.weight)
        nn.init.zeros_(self.fc.bias)
        nn.init.normal_(self.item_embedding.weight, mean=0, std=0.01)

    def forward(self, session_seq: torch.Tensor) -> torch.Tensor:
        """
        Args:
            session_seq: Tensor [batch_size, seq_length] — chuỗi product_ids

        Returns:
            logits: Tensor [batch_size, num_items] — điểm dự đoán cho mỗi sản phẩm
        """
        # [B, L] → [B, L, embed_dim]
        emb = self.item_embedding(session_seq)
        emb = self.dropout(emb)

        # LSTM: lstm_out [B, L, H], h_n [num_layers, B, H]
        lstm_out, (h_n, c_n) = self.lstm(emb)

        # Lấy hidden state của layer cuối cùng tại bước thời gian cuối
        final_hidden = h_n[-1]  # [B, H]
        final_hidden = self.dropout(final_hidden)

        # [B, H] → [B, num_items]
        logits = self.fc(final_hidden)

        return logits

    def get_top_k(self, session_seq: torch.Tensor, k: int = 10,
                  exclude_ids: list = None) -> tuple:
        """
        Inference mode: trả về Top-K sản phẩm gợi ý.
        
        Args:
            session_seq: Input sequence tensor
            k: Số lượng gợi ý
            exclude_ids: Các product_id đã trong giỏ hàng (loại bỏ)
        """
        with torch.no_grad():
            logits = self.forward(session_seq)

            if exclude_ids:
                for pid in exclude_ids:
                    if 0 <= pid < logits.size(-1):
                        logits[:, pid] = float('-inf')

            scores, indices = torch.topk(logits, min(k, logits.size(-1)))
            return scores.squeeze(0), indices.squeeze(0)
