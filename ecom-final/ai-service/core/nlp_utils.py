import pickle
import re
import os

def normalize_string(s):
    """Chuẩn hóa văn bản: Chữ thường, tách dấu câu."""
    s = str(s).lower().strip()
    s = re.sub(r"([.!?])", r" \1", s)
    s = re.sub(r"[^a-zA-Zàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ0-9.!?]+", r" ", s)
    s = re.sub(r"\s+", r" ", s).strip()
    return s

def load_pickle(filepath):
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, 'rb') as f:
            return pickle.load(f)
    except Exception as e:
        print(f"[NLP Utils] Lỗi khi load {filepath}: {e}")
        return None

def text_to_sequence(text, vocab_dict, max_length=50, padding_idx=0, unk_idx=1):
    """Chuyển câu văn thành mảng số nguyên dựa trên vocab_dict và pad cho đủ độ dài."""
    if not vocab_dict:
        return [padding_idx] * max_length
        
    text = normalize_string(text)
    tokens = text.split()
    
    sequence = [vocab_dict.get(word, unk_idx) for word in tokens]
    
    if len(sequence) > max_length:
        sequence = sequence[:max_length]
    else:
        sequence = sequence + [padding_idx] * (max_length - len(sequence))
        
    return sequence
