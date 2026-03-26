import torch
from safetensors.torch import load_file
import os
import sys

if len(sys.argv) != 3:
    print("Usage: python convert_safetensors_to_pt.py <input_safetensors> <output_pt>")
    sys.exit(1)

input_path = sys.argv[1]
output_path = sys.argv[2]

# 加载safetensors模型
print(f"Loading safetensors model from {input_path}...")
state_dict = load_file(input_path)

# 构造与原始PyTorch模型相同的结构
checkpoint = {
    "model_state_dict": state_dict,
    "dims": {
        "n_vocab": 51865,  # 假设是多语言模型
        "n_audio_ctx": 1500,  # Whisper默认值
        "n_audio_state": 1024,  # 假设是medium模型
        "n_audio_head": 16,  # 假设是medium模型
        "n_audio_layer": 24,  # 假设是medium模型
        "n_text_ctx": 448,  # Whisper默认值
        "n_text_state": 1024,  # 假设是medium模型
        "n_text_head": 16,  # 假设是medium模型
        "n_text_layer": 24,  # 假设是medium模型
        "n_mels": 80  # Whisper默认值
    }
}

# 保存为PyTorch格式
print(f"Saving PyTorch model to {output_path}...")
torch.save(checkpoint, output_path)

print("Conversion completed successfully!")
