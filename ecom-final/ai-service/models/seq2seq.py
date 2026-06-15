import torch
import torch.nn as nn
import torch.nn.functional as F
import os

from core.nlp_utils import SOS_token, EOS_token, PAD_token

class EncoderRNN(nn.Module):
    def __init__(self, input_size, hidden_size, dropout_p=0.1):
        super(EncoderRNN, self).__init__()
        self.hidden_size = hidden_size
        self.embedding = nn.Embedding(input_size, hidden_size, padding_idx=PAD_token)
        self.lstm = nn.LSTM(hidden_size, hidden_size, batch_first=True)
        self.dropout = nn.Dropout(dropout_p)

    def forward(self, input_seq):
        # input_seq: [batch_size, seq_length]
        embedded = self.embedding(input_seq)
        embedded = self.dropout(embedded)
        output, (hidden, cell) = self.lstm(embedded)
        return output, hidden, cell


class Attention(nn.Module):
    def __init__(self, hidden_size):
        super(Attention, self).__init__()
        self.Wa = nn.Linear(hidden_size, hidden_size)
        self.Ua = nn.Linear(hidden_size, hidden_size)
        self.Va = nn.Linear(hidden_size, 1)

    def forward(self, hidden, encoder_outputs):
        # hidden: [1, batch_size, hidden_size]
        # encoder_outputs: [batch_size, seq_len, hidden_size]
        
        # [batch_size, 1, hidden_size]
        query = hidden.transpose(0, 1)
        
        # Calculate attention scores
        scores = self.Va(torch.tanh(self.Wa(query) + self.Ua(encoder_outputs))) # [batch_size, seq_len, 1]
        scores = scores.squeeze(2) # [batch_size, seq_len]
        
        weights = F.softmax(scores, dim=-1)
        
        # [batch_size, 1, seq_len] * [batch_size, seq_len, hidden_size] -> [batch_size, 1, hidden_size]
        context = torch.bmm(weights.unsqueeze(1), encoder_outputs)
        
        return context, weights


class AttnDecoderRNN(nn.Module):
    def __init__(self, hidden_size, output_size, dropout_p=0.1):
        super(AttnDecoderRNN, self).__init__()
        self.hidden_size = hidden_size
        self.embedding = nn.Embedding(output_size, hidden_size, padding_idx=PAD_token)
        self.attention = Attention(hidden_size)
        self.lstm = nn.LSTM(hidden_size * 2, hidden_size, batch_first=True)
        self.out = nn.Linear(hidden_size, output_size)
        self.dropout = nn.Dropout(dropout_p)

    def forward(self, input_step, hidden, cell, encoder_outputs):
        # input_step: [batch_size, 1]
        embedded = self.embedding(input_step)
        embedded = self.dropout(embedded)
        
        context, attn_weights = self.attention(hidden, encoder_outputs)
        
        # Combine embedded input word and attention context
        rnn_input = torch.cat((embedded, context), dim=2)
        
        output, (hidden, cell) = self.lstm(rnn_input, (hidden, cell))
        
        prediction = self.out(output.squeeze(1)) # [batch_size, output_size]
        
        return prediction, hidden, cell, attn_weights


class Seq2SeqChatbot:
    """Wrapper class để nạp, lưu, và sinh văn bản từ Encoder/Decoder."""
    def __init__(self, vocab_size, hidden_size=256, device="cpu"):
        self.device = torch.device(device)
        self.encoder = EncoderRNN(vocab_size, hidden_size).to(self.device)
        self.decoder = AttnDecoderRNN(hidden_size, vocab_size).to(self.device)
        self.vocab_size = vocab_size
        self.hidden_size = hidden_size
        self.is_trained = False

    def load_weights(self, filepath):
        if os.path.exists(filepath):
            try:
                checkpoint = torch.load(filepath, map_location=self.device)
                self.encoder.load_state_dict(checkpoint['encoder'])
                self.decoder.load_state_dict(checkpoint['decoder'])
                self.is_trained = True
                print(f"[Seq2Seq] Đã tải weights từ {filepath}")
            except Exception as e:
                print(f"[Seq2Seq] Lỗi khi tải weights: {e}")
        else:
            print(f"[Seq2Seq] Không tìm thấy file {filepath}. Mô hình sẽ trả lời ngẫu nhiên.")

    def save_weights(self, filepath):
        torch.save({
            'encoder': self.encoder.state_dict(),
            'decoder': self.decoder.state_dict()
        }, filepath)

    def evaluate(self, vocab, sentence, max_length=50):
        from core.nlp_utils import indexes_from_sentence
        
        self.encoder.eval()
        self.decoder.eval()

        with torch.no_grad():
            input_indexes = indexes_from_sentence(vocab, sentence)
            input_tensor = torch.tensor(input_indexes, dtype=torch.long, device=self.device).unsqueeze(0)
            
            encoder_outputs, hidden, cell = self.encoder(input_tensor)
            
            decoder_input = torch.tensor([[SOS_token]], device=self.device)
            
            decoded_words = []
            
            for _ in range(max_length):
                decoder_output, hidden, cell, _ = self.decoder(
                    decoder_input, hidden, cell, encoder_outputs
                )
                
                _, topi = decoder_output.topk(1)
                idx = topi.item()
                
                if idx == EOS_token:
                    break
                elif idx != SOS_token and idx != PAD_token:
                    decoded_words.append(vocab.index2word.get(idx, "<UNK>"))
                    
                decoder_input = torch.tensor([[idx]], device=self.device)

            return " ".join(decoded_words)
