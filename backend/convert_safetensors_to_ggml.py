#!/usr/bin/env python3
"""
将Hugging Face格式的Whisper模型（safetensors格式）转换为ggml格式
"""
import io
import os
import sys
import struct
import json
import torch
import numpy as np
from pathlib import Path
from transformers import WhisperForConditionalGeneration, WhisperTokenizer
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SafetensorsToGGMLConverter:
    """将safetensors格式的Whisper模型转换为ggml格式"""
    
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
        tokenizer = WhisperTokenizer.from_pretrained(model_path)
        
        # 加载配置
        config_path = model_path / "config.json"
        if not config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        with open(config_path, "r", encoding="utf8") as f:
            hparams = json.load(f)
        
        # 处理max_length
        if "max_length" not in hparams or hparams["max_length"] is None:
            hparams["max_length"] = hparams.get("max_target_positions", 448)
        elif not isinstance(hparams["max_length"], int):
            try:
                hparams["max_length"] = int(hparams["max_length"])
            except ValueError:
                logger.warning(f"无效的max_length值 '{hparams['max_length']}'，使用默认值448")
                hparams["max_length"] = 448
        
        # 加载mel过滤器
        n_mels = hparams.get("num_mel_bins", 80)
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
            fout.write(struct.pack("i", hparams.get("vocab_size", 51865)))
            fout.write(struct.pack("i", hparams.get("max_source_positions", 1500)))
            fout.write(struct.pack("i", hparams.get("d_model", 768)))
            fout.write(struct.pack("i", hparams.get("encoder_attention_heads", 12)))
            fout.write(struct.pack("i", hparams.get("encoder_layers", 6)))
            fout.write(struct.pack("i", hparams.get("max_length", 448)))
            fout.write(struct.pack("i", hparams.get("d_model", 768)))
            fout.write(struct.pack("i", hparams.get("decoder_attention_heads", 12)))
            fout.write(struct.pack("i", hparams.get("decoder_layers", 6)))
            fout.write(struct.pack("i", n_mels))
            fout.write(struct.pack("i", 1 if use_f16 else 0))
            
            # 写入mel过滤器
            fout.write(struct.pack("i", filters.shape[0]))
            fout.write(struct.pack("i", filters.shape[1]))
            for i in range(filters.shape[0]):
                for j in range(filters.shape[1]):
                    fout.write(struct.pack("f", filters[i][j]))
            
            # 写入tokenizer词汇表
            byte_encoder = self._bytes_to_unicode()
            byte_decoder = {v: k for k, v in byte_encoder.items()}
            
            # 从tokenizer获取词汇表
            vocab = tokenizer.get_vocab()
            fout.write(struct.pack("i", len(vocab)))
            
            # 按索引排序并写入
            sorted_vocab = sorted(vocab.items(), key=lambda x: x[1])
            for token, idx in sorted_vocab:
                # 转换token为字节
                text = bytearray([byte_decoder[c] for c in token])
                fout.write(struct.pack("i", len(text)))
                fout.write(text)
            
            # 写入模型权重
            list_vars = model.state_dict()
            
            # 权重名称映射（与whisper.cpp保持一致）
            for name in list_vars.keys():
                # 跳过proj_out.weight，因为它在whisper.cpp中似乎不使用
                if name == "proj_out.weight":
                    logger.info(f"跳过: {name}")
                    continue
                
                src = name
                nn = name.split(".")
                
                # 处理层名称，保持与whisper.cpp一致
                if nn[1] == "layers":
                    nn[1] = "blocks"
                    name = ".".join(nn)
                
                # 特殊处理一些名称
                if name == "encoder.layer_norm.bias":
                    name = "encoder.ln_post.bias"
                elif name == "encoder.layer_norm.weight":
                    name = "encoder.ln_post.weight"
                elif name == "encoder.embed_positions.weight":
                    name = "encoder.positional_embedding"
                elif name == "decoder.layer_norm.bias":
                    name = "decoder.ln.bias"
                elif name == "decoder.layer_norm.weight":
                    name = "decoder.ln.weight"
                elif name == "decoder.embed_positions.weight":
                    name = "decoder.positional_embedding"
                elif name == "decoder.embed_tokens.weight":
                    name = "decoder.token_embedding.weight"
                
                logger.info(f"{src} -> {name}")
                
                # 获取权重数据
                data = list_vars[src].squeeze().numpy()
                
                # 处理数据类型
                if use_f16:
                    # 某些小张量需要使用float32
                    n_dims = len(data.shape)
                    if n_dims < 2 or \
                            name == "encoder.conv1.bias" or \
                            name == "encoder.conv2.bias" or \
                            name == "encoder.positional_embedding" or \
                            name == "decoder.positional_embedding":
                        logger.info(f"  转换为float32: {name}")
                        data = data.astype(np.float32)
                        ftype = 0
                    else:
                        data = data.astype(np.float16)
                        ftype = 1
                else:
                    data = data.astype(np.float32)
                    ftype = 0
                
                # 处理conv bias的形状
                if name in ["encoder.conv1.bias", "encoder.conv2.bias"]:
                    data = data.reshape(data.shape[0], 1)
                    logger.info(f"  重塑变量: {name} 形状: {data.shape}")
                
                # 写入权重头
                n_dims = len(data.shape)
                str_name = name.encode('utf-8')
                fout.write(struct.pack("iii", n_dims, len(str_name), ftype))
                for i in range(n_dims):
                    fout.write(struct.pack("i", data.shape[n_dims - 1 - i]))
                fout.write(str_name)
                
                # 写入权重数据
                data.tofile(fout)
        
        logger.info(f"转换完成: {fname_out}")
        return str(fname_out)
    
    def _bytes_to_unicode(self):
        """
        Returns list of utf-8 byte and a corresponding list of unicode strings.
        The reversible bpe codes work on unicode strings.
        This means you need a large # of unicode characters in your vocab if you want to avoid UNKs.
        When you're at something like a 10B token dataset you end up needing around 5K for decent coverage.
        This is a significant percentage of your normal, say, 32K bpe vocab.
        To avoid that, we want lookup tables between utf-8 bytes and unicode strings.
        And avoids mapping to whitespace/control characters the bpe code barfs on.
        """
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

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="将safetensors格式的Whisper模型转换为ggml格式")
    parser.add_argument("model_path", help="模型路径")
    parser.add_argument("--output-dir", help="输出目录")
    parser.add_argument("--use-f32", action="store_true", help="使用32位浮点数")
    parser.add_argument("--whisper-repo-path", help="whisper仓库路径")
    
    args = parser.parse_args()
    
    converter = SafetensorsToGGMLConverter(args.whisper_repo_path)
    output_path = converter.convert(
        args.model_path,
        args.output_dir,
        not args.use_f32
    )
    
    print(f"转换结果: {output_path}")

if __name__ == "__main__":
    main()
