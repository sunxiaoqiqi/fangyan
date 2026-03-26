#!/usr/bin/env python3
"""
将Hugging Face格式的Whisper模型（safetensors格式）转换为ggml格式
使用与whisper.cpp相同的参数和权重名称
"""
import io
import os
import sys
import struct
import json
import torch
import numpy as np
from pathlib import Path
from transformers import WhisperForConditionalGeneration
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HFToGGMLConverter:
    """将Hugging Face格式的Whisper模型转换为ggml格式"""
    
    def __init__(self, whisper_repo_path=None):
        """
        初始化转换器
        
        Args:
            whisper_repo_path: whisper仓库路径
        """
        self.whisper_repo_path = Path(whisper_repo_path) if whisper_repo_path else self._find_whisper_repo()
        logger.info(f"Whisper仓库路径: {self.whisper_repo_path}")
    
    def _find_whisper_repo(self):
        """查找whisper仓库路径"""
        # 尝试在项目根目录查找
        project_root = Path(__file__).parent.parent
        if (project_root / "whisper").exists():
            return project_root / "whisper"
        
        # 尝试在当前目录查找
        current_dir = Path.cwd()
        if (current_dir / "whisper").exists():
            return current_dir / "whisper"
        
        # 尝试在用户目录查找
        user_dir = Path.home()
        if (user_dir / "whisper").exists():
            return user_dir / "whisper"
        
        # 如果找不到，返回None
        logger.warning("未找到whisper仓库，请确保已克隆https://github.com/openai/whisper.git")
        return None
    
    def convert(self, model_path, output_dir=None, use_f16=True):
        """
        转换模型
        
        Args:
            model_path: 模型路径
            output_dir: 输出目录
            use_f16: 是否使用16位浮点数
        
        Returns:
            str: 转换后的ggml模型路径
        """
        if not self.whisper_repo_path:
            raise FileNotFoundError("未找到whisper仓库，请手动克隆https://github.com/openai/whisper.git")
        
        model_path = Path(model_path)
        if not model_path.exists():
            raise FileNotFoundError(f"模型路径不存在: {model_path}")
        
        if output_dir:
            output_dir = Path(output_dir)
        else:
            output_dir = model_path / "ggml"
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 加载模型
        logger.info(f"加载模型: {model_path}")
        model = WhisperForConditionalGeneration.from_pretrained(model_path)
        
        # 加载配置
        config_path = model_path / "config.json"
        if not config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        with open(config_path, "r", encoding="utf8") as f:
            hparams = json.load(f)
        
        # 映射Hugging Face参数到whisper.cpp参数
        ggml_hparams = {
            "n_vocab": hparams.get("vocab_size", 51865),
            "n_audio_ctx": hparams.get("max_source_positions", 1500),
            "n_audio_state": hparams.get("d_model", 768),
            "n_audio_head": hparams.get("encoder_attention_heads", 12),
            "n_audio_layer": hparams.get("encoder_layers", 6),
            "n_text_ctx": hparams.get("max_length", 448),
            "n_text_state": hparams.get("d_model", 768),
            "n_text_head": hparams.get("decoder_attention_heads", 12),
            "n_text_layer": hparams.get("decoder_layers", 6),
            "n_mels": hparams.get("num_mel_bins", 80)
        }
        
        logger.info(f"模型参数: {ggml_hparams}")
        
        # 加载mel过滤器
        n_mels = ggml_hparams["n_mels"]
        mel_filters_path = self.whisper_repo_path / "whisper" / "assets" / "mel_filters.npz"
        if not mel_filters_path.exists():
            raise FileNotFoundError(f"mel过滤器文件不存在: {mel_filters_path}")
        
        with np.load(mel_filters_path) as f:
            filters = torch.from_numpy(f[f"mel_{n_mels}"])
        
        # 准备输出文件名
        if use_f16:
            fname_out = output_dir / "ggml-model.bin"
        else:
            fname_out = output_dir / "ggml-model-f32.bin"
        
        # 写入ggml文件
        logger.info(f"开始转换模型: {model_path} -> {fname_out}")
        
        with open(fname_out, "wb") as fout:
            # 写入魔法数字
            fout.write(struct.pack("i", 0x67676d6c))  # magic: ggml in hex
            
            # 写入模型参数（与whisper.cpp保持一致）
            fout.write(struct.pack("i", ggml_hparams["n_vocab"]))
            fout.write(struct.pack("i", ggml_hparams["n_audio_ctx"]))
            fout.write(struct.pack("i", ggml_hparams["n_audio_state"]))
            fout.write(struct.pack("i", ggml_hparams["n_audio_head"]))
            fout.write(struct.pack("i", ggml_hparams["n_audio_layer"]))
            fout.write(struct.pack("i", ggml_hparams["n_text_ctx"]))
            fout.write(struct.pack("i", ggml_hparams["n_text_state"]))
            fout.write(struct.pack("i", ggml_hparams["n_text_head"]))
            fout.write(struct.pack("i", ggml_hparams["n_text_layer"]))
            fout.write(struct.pack("i", ggml_hparams["n_mels"]))
            fout.write(struct.pack("i", 1 if use_f16 else 0))
            
            # 写入mel过滤器
            fout.write(struct.pack("i", filters.shape[0]))
            fout.write(struct.pack("i", filters.shape[1]))
            for i in range(filters.shape[0]):
                for j in range(filters.shape[1]):
                    fout.write(struct.pack("f", filters[i][j]))
            
            # 写入tokenizer词汇表
            # 使用whisper.cpp的tokenizer
            multilingual = ggml_hparams["n_vocab"] >= 51865
            tokenizer_path = self.whisper_repo_path / "whisper" / "assets" / (multilingual and "multilingual.tiktoken" or "gpt2.tiktoken")
            tokenizer_type = "tiktoken"
            
            if not tokenizer_path.exists():
                tokenizer_path = self.whisper_repo_path / "whisper" / "assets" / (multilingual and "multilingual" or "gpt2") / "vocab.json"
                tokenizer_type = "hf_transformers"
                if not tokenizer_path.exists():
                    raise FileNotFoundError(f"未找到tokenizer文件: {tokenizer_path}")
            
            # 加载tokenizer
            tokens = {}
            if tokenizer_type == "tiktoken":
                import base64
                with open(tokenizer_path, "rb") as f:
                    contents = f.read()
                    tokens = {base64.b64decode(token): int(rank) for token, rank in (line.split() for line in contents.splitlines() if line)}
            elif tokenizer_type == "hf_transformers":
                # 实现bytes_to_unicode函数
                def bytes_to_unicode():
                    bs = list(range(ord("!"), ord("~")+1))+list(range(ord("¡"), ord("¬")+1))+list(range(ord("®"), ord("ÿ")+1))
                    cs = bs[:]
                    n = 0
                    for b in range(2**8):
                        if b not in bs:
                            bs.append(b)
                            cs.append(2**8+n)
                            n += 1
                    cs = [chr(n) for n in cs]
                    return dict(zip(bs, cs))
                
                byte_encoder = bytes_to_unicode()
                byte_decoder = {v: k for k, v in byte_encoder.items()}
                
                with open(tokenizer_path, "r", encoding="utf8") as f:
                    _tokens_raw = json.load(f)
                    if '<|endoftext|>' in _tokens_raw:
                        del _tokens_raw['<|endoftext|>']
                    tokens = {bytes([byte_decoder[c] for c in token]): int(idx) for token, idx in _tokens_raw.items()}
            
            # 写入tokenizer
            fout.write(struct.pack("i", len(tokens)))
            for key in tokens:
                fout.write(struct.pack("i", len(key)))
                fout.write(key)
            
            # 写入模型权重
            list_vars = model.state_dict()
            
            # 权重名称映射
            def map_weight_name(name):
                # 移除前缀 "model."
                if name.startswith("model."):
                    name = name[6:]
                
                # 替换 layers 为 blocks
                name = name.replace(".layers.", ".blocks.")
                
                # 处理编码器和解码器的自注意力层
                if ".self_attn." in name:
                    name = name.replace(".self_attn.k_proj", ".attn.key")
                    name = name.replace(".self_attn.q_proj", ".attn.query")
                    name = name.replace(".self_attn.v_proj", ".attn.value")
                    name = name.replace(".self_attn.out_proj", ".attn.out")
                if ".self_attn_layer_norm" in name:
                    name = name.replace(".self_attn_layer_norm", ".attn_ln")
                
                # 处理解码器的交叉注意力层
                if ".encoder_attn." in name:
                    name = name.replace(".encoder_attn.k_proj", ".cross_attn.key")
                    name = name.replace(".encoder_attn.q_proj", ".cross_attn.query")
                    name = name.replace(".encoder_attn.v_proj", ".cross_attn.value")
                    name = name.replace(".encoder_attn.out_proj", ".cross_attn.out")
                if ".encoder_attn_layer_norm" in name:
                    name = name.replace(".encoder_attn_layer_norm", ".cross_attn_ln")
                
                # 处理MLP层
                if ".fc1." in name:
                    name = name.replace(".fc1", ".mlp.0")
                if ".fc2." in name:
                    name = name.replace(".fc2", ".mlp.2")
                if ".final_layer_norm" in name:
                    name = name.replace(".final_layer_norm", ".mlp_ln")
                
                # 处理其他特殊情况
                if name == "encoder.layer_norm.weight":
                    name = "encoder.ln_post.weight"
                elif name == "encoder.layer_norm.bias":
                    name = "encoder.ln_post.bias"
                elif name == "decoder.layer_norm.weight":
                    name = "decoder.ln.weight"
                elif name == "decoder.layer_norm.bias":
                    name = "decoder.ln.bias"
                elif name == "decoder.embed_positions.weight":
                    name = "decoder.positional_embedding"
                elif name == "decoder.embed_tokens.weight":
                    name = "decoder.token_embedding.weight"
                elif name == "encoder.embed_positions.weight":
                    name = "encoder.positional_embedding"
                
                return name
            
            for name in list_vars.keys():
                # 跳过proj_out.weight，因为它在whisper.cpp中似乎不使用
                if name == "model.proj_out.weight":
                    logger.info(f"跳过: {name}")
                    continue
                
                src = name
                mapped_name = map_weight_name(name)
                
                logger.info(f"{src} -> {mapped_name}")
                
                # 获取权重数据
                data = list_vars[src].squeeze().numpy()
                
                # 处理数据类型
                if use_f16:
                    # 某些小张量需要使用float32
                    n_dims = len(data.shape)
                    if n_dims < 2 or \
                            mapped_name == "encoder.conv1.bias" or \
                            mapped_name == "encoder.conv2.bias" or \
                            mapped_name == "encoder.positional_embedding" or \
                            mapped_name == "decoder.positional_embedding":
                        logger.info(f"  转换为float32: {mapped_name}")
                        data = data.astype(np.float32)
                        ftype = 0
                    else:
                        data = data.astype(np.float16)
                        ftype = 1
                else:
                    data = data.astype(np.float32)
                    ftype = 0
                
                # 处理conv bias的形状
                if mapped_name in ["encoder.conv1.bias", "encoder.conv2.bias"]:
                    data = data.reshape(data.shape[0], 1)
                    logger.info(f"  重塑变量: {mapped_name} 形状: {data.shape}")
                
                # 写入权重头
                n_dims = len(data.shape)
                str_name = mapped_name.encode('utf-8')
                fout.write(struct.pack("iii", n_dims, len(str_name), ftype))
                for i in range(n_dims):
                    fout.write(struct.pack("i", data.shape[n_dims - 1 - i]))
                fout.write(str_name)
                
                # 写入权重数据
                data.tofile(fout)
        
        logger.info(f"转换完成: {fname_out}")
        return str(fname_out)

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="将Hugging Face格式的Whisper模型转换为ggml格式")
    parser.add_argument("model_path", help="模型路径")
    parser.add_argument("--output-dir", help="输出目录")
    parser.add_argument("--use-f32", action="store_true", help="使用32位浮点数")
    parser.add_argument("--whisper-repo-path", help="whisper仓库路径")
    
    args = parser.parse_args()
    
    converter = HFToGGMLConverter(args.whisper_repo_path)
    output_path = converter.convert(
        args.model_path,
        args.output_dir,
        not args.use_f32
    )
    
    print(f"转换结果: {output_path}")

if __name__ == "__main__":
    main()