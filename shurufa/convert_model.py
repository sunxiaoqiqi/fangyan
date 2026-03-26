from transformers import WhisperForConditionalGeneration, WhisperProcessor
import torch
import onnx
from onnxruntime.quantization import quantize_dynamic, QuantType
import os

class WhisperWrapper(torch.nn.Module):
    """
    Whisper模型的包装器，简化ONNX导出
    """
    def __init__(self, model):
        super().__init__()
        self.model = model
    
    def forward(self, input_features):
        # 内部处理decoder_input_ids
        decoder_input_ids = torch.tensor([[1]], device=input_features.device)  # 起始token
        return self.model(input_features, decoder_input_ids=decoder_input_ids).logits

def convert_to_onnx(model_path, output_onnx_path):
    """
    将Whisper模型转换为ONNX格式
    """
    print(f"正在加载模型: {model_path}")
    model = WhisperForConditionalGeneration.from_pretrained(model_path)
    model.eval()
    
    # 创建包装器
    wrapper = WhisperWrapper(model)
    
    print("准备示例输入...")
    dummy_input = torch.randn(1, 80, 3000)
    
    print(f"正在导出ONNX模型到: {output_onnx_path}")
    # 说明：
    # onnxruntime-android:1.17.1 最高支持 IR version = 9
    # Android 是否能加载取决于导出出来的 ONNX IR version，而不是只看 opset_version。
    #
    # 但这份模型导出里包含 `aten::scaled_dot_product_attention`：
    # 该算子在较低 opset 下会导出失败（提示 opset 需要 >= 14）。
    #
    # 因此这里使用 opset_version=14 保证导出算子可用，
    # 同时依赖你在环境里使用较老的 onnx（建议 onnx==1.14.1）
    # 来尽可能让导出的 ONNX IR version 落在 <= 9 范围。
    target_opset_version = 14
    torch.onnx.export(
        wrapper,
        dummy_input,
        output_onnx_path,
        input_names=['input_features'],
        output_names=['logits'],
        # 使用静态形状，避免动态轴的问题
        opset_version=target_opset_version,
        do_constant_folding=True,
        export_params=True,
        # 禁用dynamo，使用传统的导出方式
        dynamic_axes=None,
        # 确保IR版本兼容
        verbose=False
    )
    
    print("验证ONNX模型...")
    onnx_model = onnx.load(output_onnx_path)
    print(f"导出后 ONNX IR version: {onnx_model.ir_version}")
    # 这里只做提示，不做强制转换：强制转换可能需要额外的转换工具/流程。
    if onnx_model.ir_version > 9:
        print(
            f"警告：导出后的 IR version={onnx_model.ir_version}，Android 端 onnxruntime-android(1.17.1) 最高支持 9。"
        )
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
        # 关键点：
        # 你在 Android 端遇到的是 ORT_NOT_IMPLEMENTED: ConvInteger
        # 这通常是因为动态量化把 Conv 也量化成了 ConvInteger 节点，
        # 但 onnxruntime-android(1.17.1) 在该节点上缺少实现。
        #
        # 解决思路：先只量化线性层（MatMul/Gemm），避开 ConvInteger。
        weight_type=QuantType.QInt8,
        op_types_to_quantize=["MatMul", "Gemm"],
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

        # 步骤3：快速检查量化结果里是否仍存在 ConvInteger
        # 如果仍存在，说明还有 Conv 被量化，需要进一步排查量化配置。
        print("\n" + "=" * 50)
        print("步骤3: 检查 ConvInteger 节点")
        print("=" * 50)
        q_model = onnx.load(quantized_path)
        conv_integer_count = 0
        for node in q_model.graph.node:
            if node.op_type == "ConvInteger":
                conv_integer_count += 1
        print(f"ConvInteger 节点数量: {conv_integer_count}")
        
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