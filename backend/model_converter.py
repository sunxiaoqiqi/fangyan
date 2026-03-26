#!/usr/bin/env python3
"""
模型转换和量化工具
将Hugging Face格式的Whisper模型转换为ggml格式并进行量化
"""
import os
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ModelConverter:
    """模型转换器"""
    
    def __init__(self, whisper_cpp_path=None):
        """
        初始化模型转换器
        
        Args:
            whisper_cpp_path: whisper.cpp的路径，如果为None则自动查找
        """
        self.whisper_cpp_path = whisper_cpp_path or self._find_whisper_cpp()
        # 转换脚本在models目录中
        self.convert_script = self.whisper_cpp_path / "models" / "convert-h5-to-ggml.py" if (self.whisper_cpp_path / "models" / "convert-h5-to-ggml.py").exists() else None
        # 量化工具在根目录或build目录中
        self.quantize_script = None
        if (self.whisper_cpp_path / "quantize").exists():
            self.quantize_script = self.whisper_cpp_path / "quantize"
        elif (self.whisper_cpp_path / "build" / "Release" / "quantize.exe").exists():
            self.quantize_script = self.whisper_cpp_path / "build" / "Release" / "quantize.exe"
        elif (self.whisper_cpp_path / "build" / "bin" / "Release" / "whisper-quantize.exe").exists():
            self.quantize_script = self.whisper_cpp_path / "build" / "bin" / "Release" / "whisper-quantize.exe"
        
        logger.info(f"Whisper.cpp路径: {self.whisper_cpp_path}")
        logger.info(f"转换脚本: {self.convert_script}")
        logger.info(f"量化工具: {self.quantize_script}")
    
    def _find_whisper_cpp(self):
        """查找whisper.cpp的路径"""
        # 尝试在项目根目录查找
        project_root = Path(__file__).parent.parent
        whisper_cpp_dir = project_root / "whisper.cpp"
        if whisper_cpp_dir.exists():
            return whisper_cpp_dir
        
        # 尝试在当前目录查找
        current_dir = Path.cwd()
        whisper_cpp_dir = current_dir / "whisper.cpp"
        if whisper_cpp_dir.exists():
            return whisper_cpp_dir
        
        # 尝试在用户目录查找
        user_dir = Path.home()
        whisper_cpp_dir = user_dir / "whisper.cpp"
        if whisper_cpp_dir.exists():
            return whisper_cpp_dir
        
        # 如果找不到，返回None
        logger.warning("未找到whisper.cpp目录，请确保已克隆并编译whisper.cpp")
        return None
    
    def convert_to_ggml(self, model_path, output_dir=None):
        """
        将Hugging Face格式的模型转换为ggml格式
        
        Args:
            model_path: 模型路径
            output_dir: 输出目录，如果为None则在模型目录下创建ggml目录
        
        Returns:
            str: 转换后的ggml模型路径
        """
        model_path = Path(model_path)
        if not model_path.exists():
            raise FileNotFoundError(f"模型路径不存在: {model_path}")
        
        if output_dir:
            output_dir = Path(output_dir)
        else:
            output_dir = model_path / "ggml"
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 使用我们自己的转换脚本
        convert_script = Path(__file__).parent / "convert_safetensors_to_ggml.py"
        
        # 运行转换脚本
        try:
            logger.info(f"开始转换模型: {model_path} -> {output_dir}")
            result = subprocess.run(
                [sys.executable, str(convert_script), str(model_path), "--output-dir", str(output_dir)],
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"转换成功: {result.stdout}")
            
            # 查找生成的ggml模型文件
            ggml_files = list(output_dir.glob("ggml-model*.bin"))
            if not ggml_files:
                raise FileNotFoundError("转换失败，未生成ggml模型文件")
            
            return str(ggml_files[0])
        except subprocess.CalledProcessError as e:
            logger.error(f"转换失败: {e.stderr}")
            raise
    
    def quantize_model(self, ggml_model_path, output_path=None, quantization_type="q4_0"):
        """
        量化ggml模型
        
        Args:
            ggml_model_path: ggml模型路径
            output_path: 输出路径，如果为None则在原路径基础上添加量化类型后缀
            quantization_type: 量化类型，默认为q4_0
        
        Returns:
            str: 量化后的模型路径
        """
        if not self.quantize_script or not self.quantize_script.exists():
            raise FileNotFoundError(f"量化工具不存在: {self.quantize_script}")
        
        ggml_model_path = Path(ggml_model_path)
        if not ggml_model_path.exists():
            raise FileNotFoundError(f"ggml模型路径不存在: {ggml_model_path}")
        
        if output_path:
            output_path = Path(output_path)
        else:
            # 生成默认输出路径
            base_name = ggml_model_path.stem
            output_path = ggml_model_path.parent / f"{base_name}_{quantization_type}.bin"
        
        # 运行量化工具
        try:
            logger.info(f"开始量化模型: {ggml_model_path} -> {output_path} (类型: {quantization_type})")
            result = subprocess.run(
                [str(self.quantize_script), str(ggml_model_path), str(output_path), quantization_type],
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"量化成功: {result.stdout}")
            return str(output_path)
        except subprocess.CalledProcessError as e:
            logger.error(f"量化失败: {e.stderr}")
            raise
    
    def convert_and_quantize(self, model_path, output_dir=None, quantization_type="q4_0"):
        """
        转换并量化模型
        
        Args:
            model_path: 模型路径
            output_dir: 输出目录
            quantization_type: 量化类型
        
        Returns:
            dict: 包含转换和量化结果的字典
        """
        # 转换为ggml格式
        ggml_model = self.convert_to_ggml(model_path, output_dir)
        
        # 量化模型
        quantized_model = self.quantize_model(ggml_model, quantization_type=quantization_type)
        
        return {
            "ggml_model": ggml_model,
            "quantized_model": quantized_model,
            "quantization_type": quantization_type
        }

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="模型转换和量化工具")
    parser.add_argument("model_path", help="模型路径")
    parser.add_argument("--output-dir", help="输出目录")
    parser.add_argument("--quantization-type", default="q4_0", help="量化类型")
    parser.add_argument("--whisper-cpp-path", help="whisper.cpp路径")
    
    args = parser.parse_args()
    
    converter = ModelConverter(args.whisper_cpp_path)
    result = converter.convert_and_quantize(
        args.model_path,
        args.output_dir,
        args.quantization_type
    )
    
    print(f"转换结果:")
    print(f"GGML模型: {result['ggml_model']}")
    print(f"量化模型: {result['quantized_model']}")
    print(f"量化类型: {result['quantization_type']}")

if __name__ == "__main__":
    main()
