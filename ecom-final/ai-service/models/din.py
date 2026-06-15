"""
AI Service — Deep Interest Network (DIN) Model
Tái tạo chính xác kiến trúc khớp với weights đã train (din.pth).

Architecture khôi phục từ state_dict:
  - item_embedding: [num_items=515, embed_dim=64]
  - attention.attention_mlp: Linear(256→32) → ReLU → Linear(32→1)
      input = [query_emb; candidate_emb; query*candidate; query-candidate] = 4×64 = 256
  - fc: Linear(128→64) → ReLU → Linear(64→1)
      input = [weighted_history_emb(64) + candidate_emb(64)] = 128

Cách dùng (inference):
  - Input:  history_ids [B, L], candidate_id [B, 1]
  - Output: score tensor [B, 1]  (điểm tương quan candidate với user)
"""
import torch
import torch.nn as nn
import torch.nn.functional as F


class AttentionUnit(nn.Module):
    """
    Attention Activation Unit — cốt lõi của DIN.
    Học điểm quan trọng (relevance score) của từng item trong lịch sử
    so với item đang xét (candidate).

    Input:  cat([query_emb, candidate_emb, query*candidate, query-candidate])  → dim 4*E
    Output: scalar attention weight per history item
    """

    def __init__(self, embed_dim: int, hidden_dim: int = 32):
        super().__init__()
        self.attention_mlp = nn.Sequential(
            nn.Linear(4 * embed_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, query: torch.Tensor, keys: torch.Tensor) -> torch.Tensor:
        """
        Args:
            query: candidate item embedding  [B, E]
            keys:  history item embeddings   [B, L, E]

        Returns:
            weights: attention scores         [B, L, 1]
        """
        # Expand query để broadcast theo L
        query_exp = query.unsqueeze(1).expand_as(keys)          # [B, L, E]

        # Concat 4 features: q, k, q*k, q-k
        interaction = torch.cat([
            query_exp,
            keys,
            query_exp * keys,
            query_exp - keys,
        ], dim=-1)                                              # [B, L, 4E]

        weights = self.attention_mlp(interaction)               # [B, L, 1]
        return weights


class DINModel(nn.Module):
    """
    Deep Interest Network for Recommendation.
    Khớp chính xác với din.pth:
      num_items=515, embed_dim=64, attn_hidden=32, fc_dims=[128,64,1]
    """

    def __init__(
        self,
        num_items:   int = 515,
        embed_dim:   int = 64,
        attn_hidden: int = 32,
    ):
        super().__init__()
        self.embed_dim = embed_dim

        # Embedding dùng chung cho cả history lẫn candidate
        self.item_embedding = nn.Embedding(num_items, embed_dim, padding_idx=0)

        # Attention activation unit
        self.attention = AttentionUnit(embed_dim, attn_hidden)

        # Fully-connected scoring: [weighted_hist_emb | candidate_emb] → score
        self.fc = nn.Sequential(
            nn.Linear(2 * embed_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
        )

    def forward(
        self,
        history_ids:  torch.Tensor,    # [B, L]  — lịch sử sản phẩm đã xem
        candidate_id: torch.Tensor,    # [B]     — sản phẩm cần tính điểm
        mask:         torch.Tensor = None,   # [B, L] — 1 = hợp lệ, 0 = padding
    ) -> torch.Tensor:
        """
        Returns:
            score: [B, 1]  — điểm tương quan của candidate với user context
        """
        # Embed
        hist_emb  = self.item_embedding(history_ids)       # [B, L, E]
        cand_emb  = self.item_embedding(candidate_id)      # [B, E]

        # Attention weights
        attn_w = self.attention(cand_emb, hist_emb)        # [B, L, 1]

        # Áp mask trước softmax (padding về -inf)
        if mask is not None:
            attn_w = attn_w.squeeze(-1)                    # [B, L]
            attn_w = attn_w.masked_fill(mask == 0, float("-inf"))
            attn_w = F.softmax(attn_w, dim=-1)             # [B, L]
            attn_w = attn_w.unsqueeze(-1)                  # [B, L, 1]
        else:
            attn_w = F.softmax(attn_w, dim=1)              # [B, L, 1]

        # Weighted sum of history embeddings
        weighted_hist = (attn_w * hist_emb).sum(dim=1)    # [B, E]

        # Concat và score
        combined = torch.cat([weighted_hist, cand_emb], dim=-1)  # [B, 2E]
        score    = self.fc(combined)                               # [B, 1]
        return score

    @torch.no_grad()
    def rank_candidates(
        self,
        history_ids:   torch.Tensor,   # [L]  lịch sử 1 user
        candidate_ids: list,           # List[int] — danh sách item cần rank
        device:        str = "cpu",
        top_k:         int = 10,
    ) -> list:
        """
        Rank danh sách candidate items theo điểm DIN cho 1 user.

        Returns:
            List[dict]: [{"product_id": int, "score": float}, ...]
        """
        self.eval()

        if not candidate_ids:
            return []

        hist_tensor = history_ids.unsqueeze(0).to(device)          # [1, L]

        results = []
        for pid in candidate_ids:
            cand_tensor = torch.tensor([pid], dtype=torch.long).to(device)  # [1]
            score = self.forward(hist_tensor, cand_tensor)          # [1, 1]
            results.append({"product_id": pid, "score": float(score.item())})

        # Sắp xếp giảm dần và lấy top_k
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
