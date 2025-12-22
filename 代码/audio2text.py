#!/usr/bin/env python3
"""
MP4音频提取和语音识别脚本 - 支持多种识别方式
"""

import os
import sys
import argparse
import warnings
import subprocess
import json
from pathlib import Path
from tqdm import tqdm
import requests

warnings.filterwarnings("ignore")

class AudioTranscriber:
    """音频转文本工具类"""
    
    def __init__(self, model_type="whisper", model_path=None, use_local=True):
        """
        初始化转写器
        
        参数:
            model_type: 模型类型，可选 "whisper", "faster_whisper", "api", "local_gguf"
            model_path: 本地模型路径
            use_local: 是否使用本地模型
        """
        self.model_type = model_type
        self.model_path = model_path
        self.use_local = use_local
        
        if model_type == "whisper" and use_local:
            self.transcriber = self._init_whisper()
        elif model_type == "faster_whisper" and use_local:
            self.transcriber = self._init_faster_whisper()
        elif model_type == "api":
            self.transcriber = None  # 使用API不需要初始化模型
        elif model_type == "local_gguf":
            self.transcriber = self._init_local_gguf()
        else:
            self.transcriber = self._init_whisper()  # 默认使用whisper
    
    def _init_whisper(self):
        """初始化OpenAI Whisper"""
        try:
            import whisper
            print("正在加载Whisper模型...")
            
            if self.model_path and os.path.exists(self.model_path):
                # 使用指定路径的模型
                model = whisper.load_model(self.model_path)
                print(f"✓ 已加载本地模型: {self.model_path}")
            else:
                # 使用内置模型（会自动下载）
                # 可选: "tiny", "base", "small", "medium", "large"
                model = whisper.load_model("base")
                print("✓ 已加载默认模型: base")
            
            return model
        except ImportError:
            print("错误: 请先安装 whisper: pip install openai-whisper")
            return None
        except Exception as e:
            print(f"加载模型失败: {e}")
            return None
    
    def _init_faster_whisper(self):
        """初始化Faster Whisper（更快，内存更少）"""
        try:
            from faster_whisper import WhisperModel
            
            print("正在加载Faster Whisper模型...")
            
            # 设备设置
            device = "cuda" if self._has_cuda() else "cpu"
            compute_type = "float16" if device == "cuda" else "int8"
            
            if self.model_path and os.path.exists(self.model_path):
                # 使用本地模型
                model = WhisperModel(
                    self.model_path,
                    device=device,
                    compute_type=compute_type
                )
                print(f"✓ 已加载本地模型: {self.model_path}")
            else:
                # 下载模型
                model = WhisperModel(
                    "base",
                    device=device,
                    compute_type=compute_type,
                    download_root="./models"  # 模型下载目录
                )
                print("✓ 已加载模型: base")
            
            return model
        except ImportError:
            print("错误: 请安装 faster-whisper: pip install faster-whisper")
            return None
    
    def _init_local_gguf(self):
        """初始化本地GGUF模型（通过LM Studio API）"""
        # 这里我们假设LM Studio的API服务器正在运行
        # 默认地址: http://localhost:1234
        self.api_base = "http://localhost:1234"
        return None  # 不需要初始化本地模型
    
    def _has_cuda(self):
        """检查是否有CUDA"""
        try:
            import torch
            return torch.cuda.is_available()
        except:
            return False
    
    def transcribe_whisper(self, audio_path):
        """使用OpenAI Whisper转写"""
        if not self.transcriber:
            return ""
        
        try:
            result = self.transcriber.transcribe(
                str(audio_path),
                language="zh",
                fp16=False
            )
            return result["text"]
        except Exception as e:
            print(f"Whisper转写失败: {e}")
            return ""
    
    def transcribe_faster_whisper(self, audio_path):
        """使用Faster Whisper转写"""
        if not self.transcriber:
            return ""
        
        try:
            segments, info = self.transcriber.transcribe(
                str(audio_path),
                language="zh",
                beam_size=5
            )
            
            text = "".join(segment.text for segment in segments)
            return text
        except Exception as e:
            print(f"Faster Whisper转写失败: {e}")
            return ""
    
    def transcribe_local_gguf(self, audio_path):
        """通过LM Studio API转写"""
        try:
            # 首先提取音频文本（需要先将音频转换为文本）
            # 这里我们使用简单的wav转换
            wav_path = str(audio_path).replace('.mp3', '_temp.wav')
            
            # 转换为wav格式
            cmd = [
                'ffmpeg', '-i', str(audio_path),
                '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le',
                '-y', '-loglevel', 'error', wav_path
            ]
            subprocess.run(cmd, check=False)
            
            # 这里需要根据你的LM Studio模型来调整
            # 实际上，LM Studio主要用于文本生成，音频转文本需要特定模型
            print("提示: LM Studio主要用于文本生成，音频转文本建议使用专门的ASR模型")
            print("你可以下载whisper的GGUF格式模型并使用whisper.cpp")
            return ""
            
        except Exception as e:
            print(f"本地模型转写失败: {e}")
            return ""
    
    def transcribe_openai_api(self, audio_path):
        """使用OpenAI API转写（需要API key）"""
        try:
            from openai import OpenAI
            
            # 从环境变量获取API key
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                print("错误: 请设置OPENAI_API_KEY环境变量")
                return ""
            
            client = OpenAI(api_key=api_key)
            
            with open(audio_path, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="zh"
                )
            
            return transcript.text
        except ImportError:
            print("错误: 请安装openai: pip install openai")
            return ""
        except Exception as e:
            print(f"OpenAI API转写失败: {e}")
            return ""
    
    def transcribe(self, audio_path):
        """转写音频文件"""
        if not os.path.exists(audio_path):
            print(f"音频文件不存在: {audio_path}")
            return ""
        
        print(f"  正在转写: {os.path.basename(audio_path)}")
        
        if self.model_type == "whisper":
            return self.transcribe_whisper(audio_path)
        elif self.model_type == "faster_whisper":
            return self.transcribe_faster_whisper(audio_path)
        elif self.model_type == "local_gguf":
            return self.transcribe_local_gguf(audio_path)
        elif self.model_type == "api":
            return self.transcribe_openai_api(audio_path)
        else:
            return self.transcribe_whisper(audio_path)  # 默认

def extract_audio(mp4_path, audio_path):
    """提取音频"""
    try:
        # 使用ffmpeg（最稳定）
        cmd = [
            'ffmpeg', '-i', mp4_path,
            '-q:a', '0', '-map', 'a',
            '-y', '-loglevel', 'error',
            audio_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return True
        else:
            # 尝试另一种方式
            cmd = [
                'ffmpeg', '-i', mp4_path,
                '-vn', '-acodec', 'libmp3lame',
                '-ab', '192k',
                '-y', '-loglevel', 'error',
                audio_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0
            
    except Exception as e:
        print(f"提取音频失败: {e}")
        return False

def save_as_markdown(text, output_path, metadata=None):
    """保存为Markdown"""
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"# 语音识别结果\n\n")
            
            if metadata:
                f.write(f"## 文件信息\n")
                f.write(f"- 源文件: {metadata.get('source_file', '')}\n")
                f.write(f"- 处理时间: {metadata.get('timestamp', '')}\n")
                f.write(f"- 模型: {metadata.get('model', '')}\n\n")
            
            f.write(f"## 转录文本\n\n")
            f.write(text)
        
        return True
    except Exception as e:
        print(f"保存Markdown失败: {e}")
        return False

def download_whisper_model(model_name="base", download_dir="./models"):
    """下载whisper模型"""
    try:
        import whisper
        
        print(f"正在下载模型: {model_name}")
        print("第一次运行会下载模型文件，请耐心等待...")
        print(f"模型将保存到: {download_dir}")
        
        # 设置下载目录
        os.makedirs(download_dir, exist_ok=True)
        
        # 下载模型
        model = whisper.load_model(model_name, download_root=download_dir)
        
        print(f"✓ 模型下载完成!")
        return model
    except Exception as e:
        print(f"下载模型失败: {e}")
        return None

def find_gguf_models(models_dir="./models"):
    """查找GGUF格式的模型"""
    gguf_files = []
    
    if os.path.exists(models_dir):
        for root, dirs, files in os.walk(models_dir):
            for file in files:
                if file.endswith('.gguf'):
                    gguf_files.append(os.path.join(root, file))
    
    return gguf_files

def main():
    parser = argparse.ArgumentParser(description='MP4转文本工具')
    parser.add_argument('input_dir', help='输入目录')
    parser.add_argument('-o', '--output', help='输出目录')
    parser.add_argument('--model-type', default='whisper',
                       choices=['whisper', 'faster_whisper', 'api', 'local_gguf'],
                       help='模型类型')
    parser.add_argument('--model-path', help='本地模型路径')
    parser.add_argument('--model-size', default='base',
                       choices=['tiny', 'base', 'small', 'medium', 'large'],
                       help='模型大小（仅whisper）')
    parser.add_argument('--keep-audio', action='store_true', help='保留音频文件')
    
    args = parser.parse_args()
    
    # 检查输入
    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        print(f"错误: 目录不存在: {input_dir}")
        sys.exit(1)
    
    # 输出目录
    if args.output:
        output_dir = Path(args.output)
    else:
        output_dir = input_dir / "transcriptions"
    
    output_dir.mkdir(exist_ok=True)
    
    # 临时音频目录
    audio_dir = output_dir / "temp_audio"
    audio_dir.mkdir(exist_ok=True)
    
    # 查找MP4文件
    mp4_files = list(input_dir.glob("*.mp4"))
    if not mp4_files:
        print(f"没有找到MP4文件: {input_dir}")
        return
    
    print(f"找到 {len(mp4_files)} 个MP4文件")
    
    # 下载或加载模型
    if args.model_type in ['whisper', 'faster_whisper'] and not args.model_path:
        print(f"\n使用 {args.model_type} 模型，模型大小: {args.model_size}")
        print("注意: 第一次运行会下载模型文件，可能需要几分钟...")
    
    # 初始化转写器
    transcriber = AudioTranscriber(
        model_type=args.model_type,
        model_path=args.model_path,
        use_local=True
    )
    
    if transcriber.transcriber is None and args.model_type != 'api':
        print("初始化模型失败，请检查模型路径或安装依赖")
        sys.exit(1)
    
    # 处理文件
    processed = 0
    for mp4_file in tqdm(mp4_files, desc="处理进度"):
        print(f"\n处理: {mp4_file.name}")
        
        # 准备路径
        base_name = mp4_file.stem
        audio_file = audio_dir / f"{base_name}.mp3"
        md_file = output_dir / f"{base_name}.md"
        
        # 跳过已处理的
        if md_file.exists():
            print(f"  已存在，跳过")
            continue
        
        # 1. 提取音频
        print(f"  提取音频...")
        if not extract_audio(str(mp4_file), str(audio_file)):
            print(f"  音频提取失败，跳过")
            continue
        
        # 检查音频文件
        if not os.path.exists(audio_file) or os.path.getsize(audio_file) == 0:
            print(f"  音频文件无效，跳过")
            continue
        
        # 2. 转写
        print(f"  语音识别中...")
        text = transcriber.transcribe(str(audio_file))
        
        if not text or len(text.strip()) < 5:  # 至少5个字符
            print(f"  识别结果为空或太短，跳过")
            continue
        
        # 3. 保存
        print(f"  保存结果...")
        metadata = {
            'source_file': mp4_file.name,
            'model': args.model_type,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        if save_as_markdown(text, str(md_file), metadata):
            print(f"  ✓ 已保存: {md_file.name}")
            processed += 1
        
        # 4. 清理
        if not args.keep_audio and os.path.exists(audio_file):
            os.remove(audio_file)
    
    # 清理空目录
    if os.path.exists(audio_dir) and not os.listdir(audio_dir):
        os.rmdir(audio_dir)
    
    print(f"\n✓ 处理完成! 成功处理 {processed}/{len(mp4_files)} 个文件")
    print(f"输出目录: {output_dir}")

if __name__ == "__main__":
    from datetime import datetime
    main()