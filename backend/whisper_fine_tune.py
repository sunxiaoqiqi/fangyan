"""
Whisper模型微调模块
"""
import torch
import torch.nn as nn
from transformers import (
    WhisperForConditionalGeneration,
    WhisperProcessor,
    WhisperConfig,
    TrainingArguments,
    Trainer,
    Seq2SeqTrainer,
    Seq2SeqTrainingArguments,
    EarlyStoppingCallback,
    TrainerCallback
)
from peft import LoraConfig, get_peft_model, PeftModel
from datasets import Dataset
from dataclasses import dataclass
from typing import Any, Dict, List, Union
import numpy as np
import os
import logging
from pathlib import Path
import librosa

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class DataCollatorSpeechSeq2SeqWithPadding:
    """
    数据整理器：将音频和文本整理为批次
    """
    processor: Any

    def __call__(self, features: List[Dict[str, Union[List[int], torch.Tensor]]]) -> Dict[str, torch.Tensor]:
        # 分离输入和标签
        input_features = [feature["input_features"] for feature in features]
        label_features = [feature["labels"] for feature in features]

        # 填充输入特征
        batch = self.processor.feature_extractor.pad(
            {"input_features": input_features},
            return_tensors="pt"
        )

        # 填充标签
        labels_batch = self.processor.tokenizer.pad(
            {"input_ids": label_features},
            return_tensors="pt"
        )

        # 将填充的标签替换为-100（忽略损失计算）
        labels = labels_batch["input_ids"].masked_fill(
            labels_batch.attention_mask.ne(1), -100
        )

        batch["labels"] = labels

        return batch


class WhisperFineTuner:
    """Whisper模型微调器"""
    
    def __init__(self, model_name="openai/whisper-small", output_dir="./models", task_name=None, fine_tune_type="full"):
        self.model_name = model_name
        # 使用绝对路径，确保模型保存到项目根目录的models文件夹
        self.output_dir = Path(__file__).parent.parent / "models"
        self.task_name = task_name
        self.fine_tune_type = fine_tune_type  # full 或 lora
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 检查GPU可用性
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"使用设备: {self.device}")
        logger.info(f"微调类型: {fine_tune_type}")
        logger.info(f"模型保存目录: {self.output_dir}")
        logger.info(f"微调事件名称: {task_name}")
        
        # 加载模型和处理器
        try:
            logger.info(f"正在加载模型和处理器: {model_name}")
            self.processor = WhisperProcessor.from_pretrained(model_name)
            self.model = WhisperForConditionalGeneration.from_pretrained(model_name)
            
            # 如果是 LoRA 微调，配置 LoRA
            if self.fine_tune_type == "lora":
                logger.info("配置 LoRA 微调...")
                lora_config = LoraConfig(
                    r=8,
                    lora_alpha=16,
                    target_modules=["q_proj", "v_proj"],
                    bias="none",
                    lora_dropout=0.1
                )
                self.model = get_peft_model(self.model, lora_config)
                self.model.print_trainable_parameters()
            
            self.model.to(self.device)
            logger.info(f"模型加载完成: {model_name}")
        except Exception as e:
            logger.error(f"模型加载失败: {str(e)}")
            # 尝试清理缓存并重新加载
            logger.info("尝试清理缓存并重新加载...")
            import shutil
            from transformers import cache_utils
            cache_dir = cache_utils.default_cache_path
            if cache_dir.exists():
                model_cache_dir = cache_dir / f"models--{model_name.replace('/', '--')}"
                if model_cache_dir.exists():
                    logger.info(f"删除缓存目录: {model_cache_dir}")
                    shutil.rmtree(model_cache_dir)
            
            # 重新尝试加载
            self.processor = WhisperProcessor.from_pretrained(model_name)
            self.model = WhisperForConditionalGeneration.from_pretrained(model_name)
            
            # 如果是 LoRA 微调，配置 LoRA
            if self.fine_tune_type == "lora":
                logger.info("配置 LoRA 微调...")
                lora_config = LoraConfig(
                    r=8,
                    lora_alpha=16,
                    target_modules=["q_proj", "v_proj"],
                    bias="none",
                    lora_dropout=0.1
                )
                self.model = get_peft_model(self.model, lora_config)
                self.model.print_trainable_parameters()
            
            self.model.to(self.device)
            logger.info(f"模型重新加载完成: {model_name}")
        
        # 禁用语言检测，强制使用中文
        self.model.config.forced_decoder_ids = self.processor.get_decoder_prompt_ids(
            language="zh", task="transcribe"
        )
    
    def prepare_dataset(self, audio_paths, texts, pack_ids=None):
        """
        准备训练数据集
        
        Args:
            audio_paths: 音频文件路径列表
            texts: 对应的文本列表
            pack_ids: 语料包ID列表（可选）
        """
        logger.info(f"准备数据集，共 {len(audio_paths)} 条数据")
        
        # 创建数据集字典
        dataset_dict = {
            "audio_path": audio_paths,
            "text": texts
        }
        
        # 如果提供了语料包信息，添加到数据集中
        if pack_ids:
            dataset_dict["pack_id"] = pack_ids
        
        # 创建数据集
        dataset = Dataset.from_dict(dataset_dict)
        
        # 预处理函数
        def preprocess_function(examples):
            """预处理函数"""
            try:
                # 加载音频
                audio, sampling_rate = librosa.load(examples["audio_path"], sr=16000)
                
                # 处理音频
                input_features = self.processor(
                    audio, 
                    sampling_rate=sampling_rate, 
                    return_tensors="pt"
                ).input_features[0]
                
                # 处理文本
                labels = self.processor.tokenizer(
                    examples["text"], 
                    return_tensors="pt",
                    padding="longest",
                    max_length=448,
                    truncation=True
                ).input_ids[0]
                
                # 构建返回结果
                result = {
                    "input_features": input_features,
                    "labels": labels
                }
                
                # 如果有pack_id信息，保留它
                if "pack_id" in examples:
                    result["pack_id"] = examples["pack_id"]
                
                return result
            except Exception as e:
                logger.error(f"处理数据失败: {examples['audio_path']}, 错误: {e}")
                # 返回空数据，后续会被过滤
                result = {
                    "input_features": np.array([], dtype=np.float32),
                    "labels": np.array([], dtype=np.int64)
                }
                # 如果有pack_id信息，保留它
                if "pack_id" in examples:
                    result["pack_id"] = examples["pack_id"]
                return result
        
        # 应用预处理函数
        logger.info("开始预处理数据...")
        
        # 确定要移除的列
        columns_to_remove = ["audio_path", "text"]
        # 保留pack_id列用于评估
        if "pack_id" in dataset.column_names:
            pass  # 不移除pack_id列
        
        processed_dataset = dataset.map(
            preprocess_function,
            remove_columns=columns_to_remove,
            num_proc=1  # 禁用多进程，避免子进程死亡错误
        )
        
        # 过滤空数据
        processed_dataset = processed_dataset.filter(
            lambda x: len(x["input_features"]) > 0 and len(x["labels"]) > 0
        )
        
        logger.info(f"预处理完成，共 {len(processed_dataset)} 条有效数据")
        return processed_dataset
    
    def compute_metrics(self, eval_pred):
        """
        计算评估指标
        """
        import numpy as np
        
        pred_ids = eval_pred.predictions
        label_ids = eval_pred.label_ids
        
        # 处理预测ID
        if isinstance(pred_ids, tuple) and len(pred_ids) == 1:
            pred_ids = pred_ids[0]
        
        # 处理预测ID：如果是三维的（batch_size, num_beams, seq_len），取第一个beam
        if isinstance(pred_ids, np.ndarray) and len(pred_ids.shape) == 3:
            pred_ids = pred_ids[:, 0, :]  # 取第一个beam
        
        # 确保是二维数组 (batch_size, seq_len)
        if isinstance(pred_ids, np.ndarray) and len(pred_ids.shape) != 2:
            logger.warning(f"预测ID形状异常: {pred_ids.shape}，尝试reshape")
            # 如果是1维，添加batch维度
            if len(pred_ids.shape) == 1:
                pred_ids = pred_ids.reshape(1, -1)
            else:
                # 其他情况，尝试flatten后reshape
                batch_size = pred_ids.shape[0] if len(pred_ids.shape) > 0 else 1
                pred_ids = pred_ids.reshape(batch_size, -1)
        
        # 将预测的ID转换为文本
        try:
            # 确保pred_ids是列表或numpy数组
            if isinstance(pred_ids, np.ndarray):
                # 对于numpy数组，确保是二维的
                if len(pred_ids.shape) == 2:
                    pred_str = self.processor.batch_decode(pred_ids, skip_special_tokens=True)
                else:
                    # 对于其他形状，尝试处理
                    batch_size = pred_ids.shape[0] if len(pred_ids.shape) > 0 else 1
                    pred_str = [""] * batch_size
            elif isinstance(pred_ids, list):
                # 对于列表，直接使用batch_decode
                pred_str = self.processor.batch_decode(pred_ids, skip_special_tokens=True)
            else:
                # 其他类型，返回空字符串列表
                batch_size = len(pred_ids) if hasattr(pred_ids, '__len__') else 1
                pred_str = [""] * batch_size
        except Exception as e:
            logger.error(f"batch_decode失败: {str(e)}")
            # 如果失败，返回空字符串列表
            batch_size = len(pred_ids) if hasattr(pred_ids, '__len__') else 1
            pred_str = [""] * batch_size
        
        # 将标签ID转换为文本
        label_ids = np.array(label_ids)
        label_ids[label_ids == -100] = self.processor.tokenizer.pad_token_id
        label_str = self.processor.batch_decode(label_ids, skip_special_tokens=True)
        
        # 计算WER（词错误率）和CER（字符错误率）
        from jiwer import wer, cer
        
        wer_value = 1.0
        cer_value = 1.0
        
        try:
            # 计算整体WER
            wer_value = wer(label_str, pred_str)
            # 计算整体CER
            cer_value = cer(label_str, pred_str)
            
            # 确保返回单个浮点数
            if isinstance(wer_value, np.ndarray):
                wer_value = float(wer_value.mean())
            elif isinstance(wer_value, (list, tuple)):
                wer_value = float(np.mean(wer_value))
            else:
                wer_value = float(wer_value)
            
            if isinstance(cer_value, np.ndarray):
                cer_value = float(cer_value.mean())
            elif isinstance(cer_value, (list, tuple)):
                cer_value = float(np.mean(cer_value))
            else:
                cer_value = float(cer_value)
            
            # 记录每条数据的详细信息
            wer_detail_list = []
            cer_detail_list = []
            logger.info("\n=== WER & CER 详细信息 ===")
            for i, (label, pred) in enumerate(zip(label_str, pred_str)):
                # 计算单条数据的WER和CER
                try:
                    single_wer = wer([label], [pred])
                    single_cer = cer([label], [pred])
                    # 保存详细信息
                    wer_detail = {
                        "index": i + 1,
                        "label": label,
                        "prediction": pred,
                        "wer": float(single_wer)
                    }
                    cer_detail = {
                        "index": i + 1,
                        "label": label,
                        "prediction": pred,
                        "cer": float(single_cer)
                    }
                    wer_detail_list.append(wer_detail)
                    cer_detail_list.append(cer_detail)
                    # 打印详细信息
                    logger.info(f"样本 {i+1}:")
                    logger.info(f"  真实文本: {label}")
                    logger.info(f"  预测文本: {pred}")
                    logger.info(f"  单样本WER: {single_wer:.4f}")
                    logger.info(f"  单样本CER: {single_cer:.4f}")
                    logger.info("  --")
                except Exception as e:
                    logger.warning(f"计算单样本指标失败: {str(e)}")
            logger.info("=== WER & CER 详细信息结束 ===")
            
            # 尝试将WER和CER详细信息保存到回调对象中
            import inspect
            frame = inspect.currentframe()
            while frame:
                if 'report_callback' in frame.f_locals:
                    frame.f_locals['report_callback'].wer_details.append({
                        "epoch": frame.f_locals.get('state', {}).epoch if 'state' in frame.f_locals else None,
                        "wer_details": wer_detail_list
                    })
                    # 确保cer_details属性存在
                    if not hasattr(frame.f_locals['report_callback'], 'cer_details'):
                        frame.f_locals['report_callback'].cer_details = []
                    frame.f_locals['report_callback'].cer_details.append({
                        "epoch": frame.f_locals.get('state', {}).epoch if 'state' in frame.f_locals else None,
                        "cer_details": cer_detail_list
                    })
                    break
                frame = frame.f_back
            
            logger.info(f"计算指标: WER={wer_value:.4f}, CER={cer_value:.4f}")
            
        except Exception as e:
            logger.warning(f"计算指标失败: {str(e)}")
            wer_value = 1.0  # 返回最大错误率
            cer_value = 1.0  # 返回最大错误率
        
        return {"wer": wer_value, "cer": cer_value}
    
    def fine_tune(
        self,
        train_audio_paths=None,
        train_texts=None,
        eval_audio_paths=None,
        eval_texts=None,
        test_audio_paths=None,
        test_texts=None,
        pack_ids=None,
        test_pack_ids=None,
        epochs=3,
        batch_size=8,
        learning_rate=1e-5,
        warmup_steps=500,
        gradient_accumulation_steps=1,
        eval_steps=100,
        save_steps=500,
        logging_steps=50,
        pack_info=None  # 语料包信息
    ):
        """
        执行微调
        
        Args:
            train_audio_paths: 训练集音频文件路径列表
            train_texts: 训练集对应的文本列表
            eval_audio_paths: 验证集音频文件路径列表
            eval_texts: 验证集对应的文本列表
            test_audio_paths: 评估集音频文件路径列表
            test_texts: 评估集对应的文本列表
            pack_ids: 训练集语料包ID列表
            test_pack_ids: 评估集语料包ID列表
            epochs: 训练轮数
            batch_size: 批次大小
            learning_rate: 学习率
            warmup_steps: 预热步数
            gradient_accumulation_steps: 梯度累积步数
            eval_steps: 评估步数
            save_steps: 保存步数
            logging_steps: 日志步数
            pack_info: 语料包信息，字典格式 {pack_id: pack_name}
        
        Returns:
            model_path: 保存的模型路径
        """
        logger.info("开始微调...")
        logger.info(f"训练参数: epochs={epochs}, batch_size={batch_size}, learning_rate={learning_rate}")
        
        # 准备数据集
        train_dataset = None
        eval_dataset = None
        test_dataset = None
        
        # 检查是否提供了训练数据
        if not (train_audio_paths and train_texts):
            raise ValueError("训练数据不能为空，请确保提供了train_audio_paths和train_texts")
        
        # 准备训练集
        logger.info(f"准备训练集，共 {len(train_audio_paths)} 条数据")
        train_dataset = self.prepare_dataset(train_audio_paths, train_texts, pack_ids)
        
        # 准备验证集
        if eval_audio_paths and eval_texts:
            logger.info(f"准备验证集，共 {len(eval_audio_paths)} 条数据")
            eval_dataset = self.prepare_dataset(eval_audio_paths, eval_texts, None)  # 验证集不需要pack_ids
        
        # 准备评估集
        if test_audio_paths and test_texts:
            logger.info(f"准备评估集，共 {len(test_audio_paths)} 条数据")
            # 使用评估集的pack_ids
            test_dataset = self.prepare_dataset(test_audio_paths, test_texts, test_pack_ids)
        
        # 确保至少有训练集
        if not train_dataset:
            raise ValueError("训练集不能为空")
        
        logger.info(f"训练集大小: {len(train_dataset)}")
        if eval_dataset:
            logger.info(f"验证集大小: {len(eval_dataset)}")
        if test_dataset:
            logger.info(f"评估集大小: {len(test_dataset)}")
        
        # 创建数据整理器
        data_collator = DataCollatorSpeechSeq2SeqWithPadding(processor=self.processor)
        
        # 训练参数
        training_args = Seq2SeqTrainingArguments(
            output_dir=str(self.output_dir / "checkpoints"),
            per_device_train_batch_size=batch_size,
            per_device_eval_batch_size=batch_size,
            learning_rate=learning_rate,
            num_train_epochs=epochs,
            save_steps=save_steps,
            logging_steps=10,  # 每10步记录一次训练损失
            save_total_limit=2,
            eval_strategy="epoch" if eval_dataset else "no",  # 当没有评估数据集时，设置为no
            save_strategy="epoch" if eval_dataset else "steps",  # 当没有评估数据集时，使用steps策略
            eval_steps=eval_steps,
            load_best_model_at_end=bool(eval_dataset),  # 当没有评估数据集时，不加载最佳模型
            metric_for_best_model="eval_wer" if eval_dataset else "eval_loss",
            greater_is_better=False,  # 损失越小越好
            predict_with_generate=True,  # 对于序列到序列模型，需要设置为True
            generation_max_length=448,  # 限制生成长度
            generation_num_beams=1,  # 使用贪婪搜索，加快速度
            logging_first_step=True,  # 记录第一步的日志
            report_to="none",  # 不使用外部报告工具
            logging_strategy="steps"  # 按步骤记录日志
        )
        
        # 创建生成配置，强制使用中文
        generation_kwargs = {
            "forced_decoder_ids": self.processor.get_decoder_prompt_ids(language="zh", task="transcribe"),
            "language": "zh",
            "task": "transcribe"
        }
        
        # 自定义回调函数，用于生成详细报告
        class TrainingReportCallback(TrainerCallback):
            def __init__(self):
                self.best_val_loss = float('inf')
                self.best_wer = float('inf')
                self.best_cer = float('inf')
                self.best_epoch = 0
                self.epoch_reports = []
                self.wer_details = []  # 存储WER详细信息
                self.cer_details = []  # 存储CER详细信息
                self.current_epoch = 0
                self.epoch_train_losses = []  # 存储当前轮的训练损失
            
            def on_epoch_start(self, args, state, control, **kwargs):
                # 每轮开始时重置损失列表
                self.current_epoch = state.epoch
                self.epoch_train_losses = []
            
            def on_step_end(self, args, state, control, **kwargs):
                # 记录训练步骤的损失
                if hasattr(state, 'log_history') and state.log_history:
                    last_log = state.log_history[-1]
                    if 'loss' in last_log:
                        loss = last_log['loss']
                        self.epoch_train_losses.append(loss)
                        # 打印训练步骤的损失，用于调试
                        if state.global_step % args.logging_steps == 0:
                            logger.info(f"Step {state.global_step}: Train Loss = {loss:.4f}")
            
            def on_log(self, args, state, control, logs=None, **kwargs):
                # 当有评估结果时记录
                if logs and 'eval_loss' in logs:
                    current_epoch = state.epoch
                    val_loss = logs.get('eval_loss', float('inf'))
                    wer = logs.get('eval_wer', float('inf'))
                    cer = logs.get('eval_cer', float('inf'))
                    # 计算当前轮的平均训练损失
                    if self.epoch_train_losses:
                        train_loss = sum(self.epoch_train_losses) / len(self.epoch_train_losses)
                    else:
                        train_loss = logs.get('train_loss', None)
                    current_lr = logs.get('learning_rate', learning_rate)
                    
                    # 检查是否是最佳模型
                    is_best = False
                    if wer < self.best_wer:
                        self.best_wer = wer
                        self.best_cer = cer
                        self.best_val_loss = val_loss
                        self.best_epoch = current_epoch
                        is_best = True
                    elif val_loss < self.best_val_loss:
                        self.best_val_loss = val_loss
                        self.best_cer = cer
                        self.best_epoch = current_epoch
                        is_best = True
                    
                    # 生成报告
                    report = {
                        "epoch": current_epoch,
                        "train_loss": train_loss,
                        "val_loss": val_loss,
                        "wer": wer,
                        "cer": cer,
                        "learning_rate": current_lr,
                        "is_best": is_best
                    }
                    self.epoch_reports.append(report)
                    
                    # 打印报告
                    logger.info(f"Epoch {current_epoch:.1f}:")
                    if train_loss is not None:
                        logger.info(f"  Train Loss: {train_loss:.4f}")
                    else:
                        logger.info(f"  Train Loss: - (无训练损失数据)")
                    logger.info(f"  Val Loss: {val_loss:.4f}")
                    logger.info(f"  WER: {wer:.4f}")
                    logger.info(f"  CER: {cer:.4f}")
                    logger.info(f"  Learning Rate: {current_lr:.6f}")
                    logger.info(f"  Is Best Model: {'Yes' if is_best else 'No'}")
                    logger.info("---")
        
        # 创建回调实例
        report_callback = TrainingReportCallback()
        
        # 创建训练器
        trainer = Seq2SeqTrainer(
            args=training_args,
            model=self.model,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            data_collator=data_collator,
            compute_metrics=self.compute_metrics,
            callbacks=[EarlyStoppingCallback(early_stopping_patience=3, early_stopping_threshold=0.001), report_callback]
        )
        
        # 确定最终模型路径
        # 使用 task_name 作为最终模型目录名称
        if self.task_name:
            final_model_path = self.output_dir / self.task_name
        else:
            # 如果没有 task_name，使用随机名称
            import uuid
            final_model_path = self.output_dir / f"fine_tune_{uuid.uuid4().hex[:8]}"
        
        # 确保目录存在
        final_model_path.mkdir(parents=True, exist_ok=True)
        
        # 开始训练
        logger.info("开始训练...")
        train_result = trainer.train()
        
        # 生成训练总结
        logger.info("\n=== 训练总结 ===")
        logger.info(f"总共跑了: {trainer.state.epoch:.1f} 轮")
        logger.info(f"最佳轮数: 第 {report_callback.best_epoch:.1f} 轮")
        logger.info(f"最佳 Val Loss: {report_callback.best_val_loss:.4f}")
        logger.info(f"最佳 WER: {report_callback.best_wer:.4f}")
        logger.info(f"最佳 CER: {report_callback.best_cer:.4f}")
        logger.info(f"模型保存路径: {final_model_path}")
        
        # 确定停止原因
        stop_reason = "正常结束"
        logger.info(f"停止原因: {stop_reason}")
        logger.info("=== 训练总结结束 ===")
        
        # 保存最终模型
        logger.info("保存模型...")
        
        # 根据微调类型保存模型
        if self.fine_tune_type == "lora":
            # 保存 LoRA 模型
            logger.info("保存 LoRA 模型...")
            self.model.save_pretrained(str(final_model_path))
            self.processor.save_pretrained(str(final_model_path))
        else:
            # 保存全微调模型
            logger.info("保存全微调模型...")
            trainer.save_model(str(final_model_path))
            self.processor.save_pretrained(str(final_model_path))
        
        logger.info(f"模型已保存到: {final_model_path}")
        
        # 评估集评估
        test_wer = None
        test_cer = None
        test_wer_details = []
        test_cer_details = []
        test_pack_stats = {}  # 按语料包统计
        if test_dataset:
            logger.info("\n=== 评估集评估 ===")
            logger.info(f"对评估集的 {len(test_dataset)} 条数据进行评估...")
            try:
                # 导入WER和CER计算函数
                from jiwer import wer, cer
                
                # 使用训练器评估评估集
                test_results = trainer.evaluate(eval_dataset=test_dataset)
                test_wer = test_results.get('eval_wer', None)
                test_cer = test_results.get('eval_cer', None)
                
                # 生成详细的评估报告
                logger.info(f"评估集整体WER: {test_wer:.4f}")
                logger.info(f"评估集整体CER: {test_cer:.4f}")
                
                # 计算详细的WER和CER信息
                # 手动获取预测结果
                predictions = trainer.predict(test_dataset)
                pred_ids = predictions.predictions
                label_ids = predictions.label_ids
                
                # 处理预测ID
                if isinstance(pred_ids, tuple) and len(pred_ids) == 1:
                    pred_ids = pred_ids[0]
                
                # 处理预测ID：如果是三维的（batch_size, num_beams, seq_len），取第一个beam
                if isinstance(pred_ids, np.ndarray) and len(pred_ids.shape) == 3:
                    pred_ids = pred_ids[:, 0, :]  # 取第一个beam
                
                # 确保是二维数组 (batch_size, seq_len)
                if isinstance(pred_ids, np.ndarray) and len(pred_ids.shape) != 2:
                    logger.warning(f"预测ID形状异常: {pred_ids.shape}，尝试reshape")
                    # 如果是1维，添加batch维度
                    if len(pred_ids.shape) == 1:
                        pred_ids = pred_ids.reshape(1, -1)
                    else:
                        # 其他情况，尝试flatten后reshape
                        batch_size = pred_ids.shape[0] if len(pred_ids.shape) > 0 else 1
                        pred_ids = pred_ids.reshape(batch_size, -1)
                
                # 将预测的ID转换为文本
                try:
                    # 确保pred_ids是列表或numpy数组
                    if isinstance(pred_ids, np.ndarray):
                        # 对于numpy数组，确保是二维的
                        if len(pred_ids.shape) == 2:
                            pred_str = self.processor.batch_decode(pred_ids, skip_special_tokens=True)
                        else:
                            # 对于其他形状，尝试处理
                            batch_size = pred_ids.shape[0] if len(pred_ids.shape) > 0 else 1
                            pred_str = [""] * batch_size
                    elif isinstance(pred_ids, list):
                        # 对于列表，直接使用batch_decode
                        pred_str = self.processor.batch_decode(pred_ids, skip_special_tokens=True)
                    else:
                        # 其他类型，返回空字符串列表
                        batch_size = len(pred_ids) if hasattr(pred_ids, '__len__') else 1
                        pred_str = [""] * batch_size
                except Exception as e:
                    logger.error(f"batch_decode失败: {str(e)}")
                    # 如果失败，返回空字符串列表
                    batch_size = len(pred_ids) if hasattr(pred_ids, '__len__') else 1
                    pred_str = [""] * batch_size
                
                # 将标签ID转换为文本
                label_ids = np.array(label_ids)
                label_ids[label_ids == -100] = self.processor.tokenizer.pad_token_id
                label_str = self.processor.batch_decode(label_ids, skip_special_tokens=True)
                
                # 记录每条数据的详细信息
                logger.info("\n=== 评估集WER & CER详细信息 ===")
                for i, (label, pred) in enumerate(zip(label_str, pred_str)):
                    # 计算单条数据的WER和CER
                    try:
                        single_wer = wer([label], [pred])
                        single_cer = cer([label], [pred])
                        
                        # 尝试从数据集中获取语料包信息
                        pack_id = "default"
                        pack_name = "默认包"
                        
                        # 检查test_dataset是否包含pack_id信息
                        if hasattr(test_dataset, 'features') and 'pack_id' in test_dataset.features:
                            # 从数据集中获取pack_id
                            if i < len(test_dataset):
                                pack_id = test_dataset[i]['pack_id']
                                pack_name = pack_info.get(pack_id, pack_id) if pack_info else pack_id
                        
                        # 保存详细信息
                        wer_detail = {
                            "index": i + 1,
                            "label": label,
                            "prediction": pred,
                            "wer": float(single_wer),
                            "cer": float(single_cer),
                            "pack_id": pack_id,
                            "pack_name": pack_name
                        }
                        test_wer_details.append(wer_detail)
                        
                        # 更新语料包统计
                        if pack_id not in test_pack_stats:
                            test_pack_stats[pack_id] = {
                                "pack_name": pack_name,
                                "total": 0,
                                "wer_sum": 0,
                                "cer_sum": 0,
                                "details": []
                            }
                        test_pack_stats[pack_id]["total"] += 1
                        test_pack_stats[pack_id]["wer_sum"] += single_wer
                        test_pack_stats[pack_id]["cer_sum"] += single_cer
                        test_pack_stats[pack_id]["details"].append(wer_detail)
                        
                        # 打印详细信息
                        logger.info(f"样本 {i+1} (包: {pack_name}):")
                        logger.info(f"  真实文本: {label}")
                        logger.info(f"  预测文本: {pred}")
                        logger.info(f"  单样本WER: {single_wer:.4f}")
                        logger.info(f"  单样本CER: {single_cer:.4f}")
                        logger.info("  --")
                    except Exception as e:
                        logger.warning(f"计算单样本指标失败: {str(e)}")
                logger.info("=== 评估集WER & CER详细信息结束 ===")
                
                # 打印按语料包统计的结果
                logger.info("\n=== 按语料包统计 ===")
                for pack_id, stats in test_pack_stats.items():
                    if stats["total"] > 0:
                        avg_wer = stats["wer_sum"] / stats["total"]
                        avg_cer = stats["cer_sum"] / stats["total"]
                        logger.info(f"包 {pack_id} ({stats['pack_name']}):")
                        logger.info(f"  样本数: {stats['total']}")
                        logger.info(f"  平均WER: {avg_wer:.4f}")
                        logger.info(f"  平均CER: {avg_cer:.4f}")
                        logger.info("  --")
                logger.info("=== 按语料包统计结束 ===")
                
            except Exception as e:
                logger.error(f"评估集评估失败: {str(e)}")
        
        # 返回模型路径和训练报告
        return {
            "model_path": str(final_model_path),
            "total_epochs": trainer.state.epoch,
            "best_epoch": report_callback.best_epoch,
            "best_val_loss": report_callback.best_val_loss if report_callback.best_val_loss != float('inf') else None,
            "best_wer": report_callback.best_wer if report_callback.best_wer != float('inf') else None,
            "best_cer": report_callback.best_cer if hasattr(report_callback, 'best_cer') and report_callback.best_cer != float('inf') else None,
            "epoch_reports": report_callback.epoch_reports,
            "wer_details": report_callback.wer_details,  # 包含WER详细信息
            "cer_details": report_callback.cer_details if hasattr(report_callback, 'cer_details') else [],  # 包含CER详细信息
            "test_wer": test_wer,  # 评估集WER
            "test_cer": test_cer,  # 评估集CER
            "test_wer_details": test_wer_details,  # 评估集WER详细信息
            "test_cer_details": test_cer_details,  # 评估集CER详细信息
            "test_pack_stats": test_pack_stats,  # 按语料包统计
            "stop_reason": stop_reason
        }
    
    def load_model(self, model_path):
        """
        加载微调后的模型
        
        Args:
            model_path: 模型路径
        """
        logger.info(f"加载模型: {model_path}")
        
        try:
            # 检查是否为 LoRA 模型
            model_path = Path(model_path)
            if (model_path / "adapter_config.json").exists():
                logger.info("加载 LoRA 模型...")
                # 加载基础模型
                self.model = WhisperForConditionalGeneration.from_pretrained(self.model_name)
                # 加载 LoRA 适配器
                self.model = PeftModel.from_pretrained(self.model, model_path)
                # 合并 LoRA 权重
                self.model = self.model.merge_and_unload()
            else:
                logger.info("加载全微调模型...")
                # 加载全微调模型
                self.model = WhisperForConditionalGeneration.from_pretrained(model_path)
            
            # 加载处理器
            self.processor = WhisperProcessor.from_pretrained(model_path)
            
            # 禁用语言检测，强制使用中文
            self.model.config.forced_decoder_ids = self.processor.get_decoder_prompt_ids(
                language="zh", task="transcribe"
            )
            
            self.model.to(self.device)
            logger.info("模型加载完成")
        except Exception as e:
            logger.error(f"模型加载失败: {str(e)}")
            raise
    
    def transcribe(self, audio_path):
        """
        转录音频文件
        
        Args:
            audio_path: 音频文件路径
        
        Returns:
            dict: 转录结果
        """
        logger.info(f"转录音频: {audio_path}")
        
        try:
            # 加载音频
            audio, sampling_rate = librosa.load(audio_path, sr=16000)
            
            # 处理音频
            input_features = self.processor(
                audio, 
                sampling_rate=sampling_rate, 
                return_tensors="pt"
            ).input_features.to(self.device)
            
            # 生成转录结果
            with torch.no_grad():
                predicted_ids = self.model.generate(
                    input_features,
                    max_new_tokens=440,
                    num_beams=5,
                    temperature=0.0
                )
            
            # 解码结果
            transcription = self.processor.batch_decode(
                predicted_ids, 
                skip_special_tokens=True
            )[0]
            
            logger.info(f"转录结果: {transcription}")
            
            return {
                "text": transcription,
                "language": "zh"
            }
        except Exception as e:
            logger.error(f"转录失败: {str(e)}")
            raise