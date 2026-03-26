from transformers import WhisperForConditionalGeneration, WhisperProcessor
import torch
import onnx
from onnxruntime.quantization import quantize_dynamic, QuantType
import os

def convert_to_onnx(model_path, output_onnx_path):
    """
    将Whisper模型转换为ONNX格式
    """
    print(f"正在加载模型: {model_path}")
    model = WhisperForConditionalGeneration.from_pretrained(model_path)
    model.eval()
    
    print("准备示例输入...")
    dummy_input = torch.randn(1, 80, 3000)
    
    print(f"正在导出ONNX模型到: {output_onnx_path}")
    torch.onnx.export(
        model,
        dummy_input,
        output_onnx_path,
        input_names=['input_features'],
        output_names=['logits'],
        dynamic_axes={
            'input_features': {2: 'sequence_length'},
            'logits': {1: 'sequence_length'}
        },
        opset_version=13,
        do_constant_folding=True,
        export_params=True
    )
    
    print("验证ONNX模型...")
    onnx_model = onnx.load(output_onnx_path)
    onnx.checker.check_model(onnx_model)
    
    print(f"ONNX模型转换完成: {output_onnx_path}")
    return output_onnx_path

def quantize_model(onnx_path, quantized_path):
    """
    量化ONNX模型为INT8格式
    """
    print(f"正在量化模型: {onnx_path}")
    quantize_dynamic(
        onnx_path,
        quantized_path,
        weight_type=QuantType.INT8
    )
    print(f"量化完成: {quantized_path}")
    return quantized_path

def get_model_size(file_path):
    """
    获取模型文件大小
    """
    size_bytes = os.path.getsize(file_path)
    size_mb = size_bytes / (1024 * 1024)
    return size_mb

def main():
    # 模型路径配置
    model_path = r'e:\project\31fangyan\models\正式常德话smalllora'
    output_dir = r'e:\project\31fangyan\shurufa\app\src\main\assets'
    
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    # 输出文件路径
    onnx_path = os.path.join(output_dir, 'model.onnx')
    quantized_path = os.path.join(output_dir, 'model_quantized.onnx')
    
    try:
        # 步骤1: 转换为ONNX格式
        print("=" * 50)
        print("步骤1: 转换为ONNX格式")
        print("=" * 50)
        convert_to_onnx(model_path, onnx_path)
        
        # 显示原始ONNX模型大小
        original_size = get_model_size(onnx_path)
        print(f"原始ONNX模型大小: {original_size:.2f} MB")
        
        # 步骤2: 量化模型
        print("\n" + "=" * 50)
        print("步骤2: 量化模型")
        print("=" * 50)
        quantize_model(onnx_path, quantized_path)
        
        # 显示量化后模型大小
        quantized_size = get_model_size(quantized_path)
        print(f"量化后模型大小: {quantized_size:.2f} MB")
        
        # 显示压缩比例
        compression_ratio = (1 - quantized_size / original_size) * 100
        print(f"压缩比例: {compression_ratio:.1f}%")
        
        print("\n" + "=" * 50)
        print("模型转换完成!")
        print("=" * 50)
        print(f"ONNX模型: {onnx_path}")
        print(f"量化模型: {quantized_path}")
        print(f"模型已准备好用于安卓输入法")
        
    except Exception as e:
        print(f"转换过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()