import torch
import torch.nn as nn
import os

class IntentLSTM(nn.Module):
    def __init__(self, vocab_size, num_classes, embed_dim=64, hidden_dim=64):
        super(IntentLSTM, self).__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
        self.lstm = nn.LSTM(embed_dim, hidden_dim, batch_first=True)
        self.dropout = nn.Dropout(0.4)
        self.fc1 = nn.Linear(hidden_dim, 64)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(64, num_classes)
        
    def forward(self, x):
        embedded = self.embedding(x)
        output, (hidden, cell) = self.lstm(embedded)
        # Lấy hidden state của bước thời gian cuối cùng
        last_hidden = hidden[-1]
        out = self.dropout(last_hidden)
        out = self.relu(self.fc1(out))
        logits = self.fc2(out)
        return logits

class IntentChatbotWrapper:
    """Wrapper quản lý quá trình khởi tạo, load weights và inference."""
    def __init__(self, vocab_size, num_classes, device="cpu"):
        self.device = torch.device(device)
        self.model = IntentLSTM(vocab_size, num_classes).to(self.device)
        self.is_trained = False
        
    def load_weights(self, filepath):
        if os.path.exists(filepath):
            try:
                # Load toàn bộ state dict
                self.model.load_state_dict(torch.load(filepath, map_location=self.device))
                self.model.eval()
                self.is_trained = True
                print(f"[IntentLSTM] Đã tải weights từ {filepath}")
            except Exception as e:
                print(f"[IntentLSTM] Lỗi khi tải weights: {e}")
        else:
            print(f"[IntentLSTM] Không tìm thấy file {filepath}.")

    def predict_intent(self, sequence_indices):
        self.model.eval()
        with torch.no_grad():
            input_tensor = torch.tensor([sequence_indices], dtype=torch.long, device=self.device)
            logits = self.model(input_tensor)
            # Vì không dùng Softmax ở output, giá trị lớn nhất của logit chính là class có xác suất cao nhất
            predicted_class = torch.argmax(logits, dim=1).item()
            return predicted_class
