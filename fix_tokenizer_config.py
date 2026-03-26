"""
修复所有微调模型的 tokenizer_config.json
将 extra_special_tokens 从数组格式转换为字典格式
"""

import json
from pathlib import Path

def fix_tokenizer_config(model_path: str):
    """
    修复 tokenizer_config.json 中的 extra_special_tokens 格式
    
    Args:
        model_path: 模型目录路径
    
    Returns:
        bool: 是否成功修复
    """
    model_path = Path(model_path)
    tokenizer_config_path = model_path / "tokenizer_config.json"
    
    if not tokenizer_config_path.exists():
        print(f"⚠️  tokenizer_config.json 不存在: {tokenizer_config_path}")
        return False
    
    try:
        # 读取配置
        with open(tokenizer_config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 检查 extra_special_tokens 是否为数组格式
        if "extra_special_tokens" not in config:
            print(f"ℹ️  {model_path.name}: 没有 extra_special_tokens 字段")
            return True
        
        if isinstance(config["extra_special_tokens"], list):
            print(f"🔧 {model_path.name}: 检测到数组格式，开始修复...")
            
            # 将数组转换为字典格式
            extra_special_tokens = config["extra_special_tokens"]
            config["extra_special_tokens"] = {
                token: token for token in extra_special_tokens
            }
            
            # 保存修复后的配置
            with open(tokenizer_config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            print(f"✅ {model_path.name}: 修复完成（数组 -> 字典）")
            return True
        elif isinstance(config["extra_special_tokens"], dict):
            print(f"✅ {model_path.name}: 已是字典格式，无需修复")
            return True
        else:
            print(f"⚠️  {model_path.name}: extra_special_tokens 格式未知")
            return False
            
    except Exception as e:
        print(f"❌ {model_path.name}: 修复失败 - {str(e)}")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("Whisper 模型 tokenizer_config.json 修复工具")
    print("=" * 60)
    print()
    
    # 模型目录
    models_dir = Path(__file__).parent / "models"
    
    if not models_dir.exists():
        print(f"❌ models 目录不存在: {models_dir}")
        return
    
    # 遍历所有子目录
    success_count = 0
    fail_count = 0
    
    for model_dir in sorted(models_dir.iterdir()):
        if model_dir.is_dir() and model_dir.name not in ['model', 'checkpoints']:
            print(f"\n处理: {model_dir.name}")
            print("-" * 40)
            
            if fix_tokenizer_config(str(model_dir)):
                success_count += 1
            else:
                fail_count += 1
    
    # 总结
    print()
    print("=" * 60)
    print("修复完成")
    print(f"成功: {success_count} 个模型")
    print(f"失败: {fail_count} 个模型")
    print("=" * 60)


if __name__ == "__main__":
    main()
