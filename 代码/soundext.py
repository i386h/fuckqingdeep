#!/usr/bin/env python3
"""
MP4音频提取和语音识别脚本
将指定文件夹中的所有MP4文件的音频提取出来，并进行语音识别，保存为Markdown文件
"""

import os
import sys
import argparse
import warnings
from pathlib import Path
from tqdm import tqdm
import subprocess

# 忽略一些警告信息
warnings.filterwarnings("ignore")

def extract_audio_from_mp4(mp4_path, audio_path):
    """
    从MP4文件中提取音频并保存为MP3
    
    参数:
        mp4_path: MP4文件路径
        audio_path: 输出的音频文件路径
    """
    try:
        # 方法1: 使用moviepy
        try:
            from moviepy.editor import VideoFileClip
            
            video = VideoFileClip(mp4_path)
            audio = video.audio
            audio.write_audiofile(audio_path, verbose=False, logger=None)
            audio.close()
            video.close()
            return True
            
        except ImportError:
            # 方法2: 使用ffmpeg命令行（如果moviepy不可用）
            print("moviepy不可用，尝试使用ffmpeg...")
            cmd = ['ffmpeg', '-i', mp4_path, '-q:a', '0', '-map', 'a', audio_path, '-y', '-loglevel', 'error']
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0
            
    except Exception as e:
        print(f"提取音频失败 {mp4_path}: {e}")
        return False

def transcribe_audio_with_whisper(audio_path):
    """
    使用OpenAI Whisper进行语音识别
    
    参数:
        audio_path: 音频文件路径
    
    返回:
        识别的文本
    """
    try:
        import whisper
        
        # 加载模型，可以选择 'tiny', 'base', 'small', 'medium', 'large'
        # 模型越大精度越高但速度越慢
        model = whisper.load_model("base")
        
        # 转录音频
        result = model.transcribe(audio_path, language='zh')
        
        return result["text"]
        
    except ImportError:
        print("Whisper未安装，尝试使用其他方法...")
        return transcribe_audio_with_speech_recognition(audio_path)
    except Exception as e:
        print(f"Whisper识别失败: {e}")
        return ""

def transcribe_audio_with_speech_recognition(audio_path):
    """
    使用speech_recognition进行语音识别（需要网络连接）
    
    参数:
        audio_path: 音频文件路径
    
    返回:
        识别的文本
    """
    try:
        import speech_recognition as sr
        
        # 初始化识别器
        recognizer = sr.Recognizer()
        
        # 加载音频文件
        with sr.AudioFile(audio_path) as source:
            audio_data = recognizer.record(source)
            
            # 尝试使用Google语音识别（需要网络）
            try:
                text = recognizer.recognize_google(audio_data, language='zh-CN')
                return text
            except sr.RequestError:
                print("网络连接问题，无法使用Google语音识别")
            except sr.UnknownValueError:
                print("无法识别音频内容")
                
    except Exception as e:
        print(f"语音识别失败: {e}")
    
    return ""

def save_text_as_markdown(text, output_path):
    """
    将文本保存为Markdown文件
    
    参数:
        text: 要保存的文本
        output_path: 输出文件路径
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"# 语音识别结果\n\n")
            f.write(f"## 转录文本\n\n")
            f.write(text)
        return True
    except Exception as e:
        print(f"保存Markdown文件失败 {output_path}: {e}")
        return False

def process_mp4_files(input_dir, output_dir=None, keep_audio=False, use_whisper=True):
    """
    处理目录中的所有MP4文件
    
    参数:
        input_dir: 输入目录路径
        output_dir: 输出目录路径（可选）
        keep_audio: 是否保留提取的音频文件
        use_whisper: 是否使用Whisper进行识别
    """
    # 转换为Path对象
    input_path = Path(input_dir)
    
    # 设置输出目录
    if output_dir:
        output_path = Path(output_dir)
    else:
        output_path = input_path / "transcriptions"
    
    # 创建输出目录
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 创建临时音频目录
    audio_dir = output_path / "temp_audio"
    audio_dir.mkdir(exist_ok=True)
    
    # 查找所有MP4文件
    mp4_files = list(input_path.glob("*.mp4"))
    if not mp4_files:
        print(f"在 {input_dir} 中未找到MP4文件")
        return
    
    print(f"找到 {len(mp4_files)} 个MP4文件")
    
    # 处理每个MP4文件
    for mp4_file in tqdm(mp4_files, desc="处理文件中"):
        print(f"\n处理文件: {mp4_file.name}")
        
        # 设置输出文件路径
        base_name = mp4_file.stem
        audio_file = audio_dir / f"{base_name}.mp3"
        md_file = output_path / f"{base_name}.md"
        
        # 跳过已处理的文件
        if md_file.exists():
            print(f"跳过已处理的文件: {base_name}")
            continue
        
        # 步骤1: 提取音频
        print(f"  提取音频...")
        if not extract_audio_from_mp4(str(mp4_file), str(audio_file)):
            print(f"  音频提取失败，跳过此文件")
            continue
        
        # 步骤2: 语音识别
        print(f"  语音识别中...")
        if use_whisper:
            text = transcribe_audio_with_whisper(str(audio_file))
        else:
            text = transcribe_audio_with_speech_recognition(str(audio_file))
        
        if not text:
            print(f"  语音识别失败，跳过此文件")
            continue
        
        # 步骤3: 保存为Markdown
        print(f"  保存文本...")
        if save_text_as_markdown(text, str(md_file)):
            print(f"  ✓ 已保存: {md_file.name}")
        
        # 步骤4: 清理临时音频文件
        if not keep_audio and audio_file.exists():
            audio_file.unlink()
    
    # 清理临时音频目录
    if not keep_audio and audio_dir.exists():
        try:
            audio_dir.rmdir()  # 只删除空目录
        except:
            pass  # 目录非空，不删除
    
    print(f"\n处理完成！所有文件已保存到: {output_path}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='提取MP4音频并转换为文本')
    parser.add_argument('input_dir', help='包含MP4文件的目录')
    parser.add_argument('-o', '--output', help='输出目录（默认为输入目录下的transcriptions文件夹）')
    parser.add_argument('-k', '--keep-audio', action='store_true', help='保留提取的音频文件')
    parser.add_argument('--no-whisper', action='store_true', help='不使用Whisper（使用在线识别）')
    
    args = parser.parse_args()
    
    # 检查输入目录
    if not os.path.exists(args.input_dir):
        print(f"错误: 目录不存在: {args.input_dir}")
        sys.exit(1)
    
    # 处理文件
    use_whisper = not args.no_whisper
    process_mp4_files(
        input_dir=args.input_dir,
        output_dir=args.output,
        keep_audio=args.keep_audio,
        use_whisper=use_whisper
    )

if __name__ == "__main__":
    main()