"""
音频格式转换工具
webm → wav (16kHz, mono, PCM)
"""
import subprocess
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def check_ffmpeg():
    """检查ffmpeg是否可用"""
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def convert_webm_to_wav(webm_path: str, wav_path: str = None, sample_rate: int = 16000) -> str:
    """
    将webm文件转换为wav格式
    
    Args:
        webm_path: webm文件路径
        wav_path: 输出wav文件路径（如果为None，自动生成）
        sample_rate: 采样率（默认16000，Whisper推荐）
    
    Returns:
        转换后的wav文件路径
    """
    webm_path = Path(webm_path)
    
    if not webm_path.exists():
        raise FileNotFoundError(f"源文件不存在: {webm_path}")
    
    # 如果没有指定输出路径，自动生成
    if wav_path is None:
        wav_path = webm_path.with_suffix('.wav')
    else:
        wav_path = Path(wav_path)
    
    # 检查ffmpeg是否可用
    if not check_ffmpeg():
        raise RuntimeError(
            "ffmpeg未安装或不在PATH中。\n"
            "请安装ffmpeg: https://ffmpeg.org/download.html\n"
            "或使用: pip install ffmpeg-python"
        )
    
    try:
        # 使用ffmpeg转换
        # -i: 输入文件
        # -ar: 采样率
        # -ac: 声道数（1=单声道）
        # -f: 输出格式
        # -y: 覆盖已存在的文件
        cmd = [
            'ffmpeg',
            '-i', str(webm_path),
            '-ar', str(sample_rate),
            '-ac', '1',  # 单声道
            '-f', 'wav',
            '-y',  # 覆盖已存在的文件
            str(wav_path)
        ]
        
        logger.info(f"开始转换音频: {webm_path} -> {wav_path}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60  # 60秒超时
        )
        
        if result.returncode != 0:
            error_msg = f"ffmpeg转换失败: {result.stderr}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        if not wav_path.exists():
            raise FileNotFoundError(f"转换后的文件不存在: {wav_path}")
        
        file_size = wav_path.stat().st_size
        logger.info(f"转换成功: {wav_path} ({file_size} 字节)")
        
        return str(wav_path)
        
    except subprocess.TimeoutExpired:
        raise RuntimeError("音频转换超时（超过60秒）")
    except Exception as e:
        logger.error(f"音频转换失败: {e}")
        raise


def get_audio_duration(file_path: str) -> float:
    """
    获取音频文件时长（秒）
    
    Args:
        file_path: 音频文件路径
    
    Returns:
        时长（秒）
    """
    if not check_ffmpeg():
        return 0.0
    
    try:
        cmd = [
            'ffmpeg',
            '-i', str(file_path),
            '-f', 'null',
            '-'
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # 从stderr中解析时长（ffmpeg把信息输出到stderr）
        import re
        duration_match = re.search(r'Duration: (\d{2}):(\d{2}):(\d{2})\.(\d{2})', result.stderr)
        if duration_match:
            hours = int(duration_match.group(1))
            minutes = int(duration_match.group(2))
            seconds = int(duration_match.group(3))
            centiseconds = int(duration_match.group(4))
            total_seconds = hours * 3600 + minutes * 60 + seconds + centiseconds / 100.0
            return total_seconds
        
        return 0.0
    except Exception as e:
        logger.warning(f"获取音频时长失败: {e}")
        return 0.0



