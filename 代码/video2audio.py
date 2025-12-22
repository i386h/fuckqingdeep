#!/usr/bin/env python3
"""
视频批量转音频工具 (Video2Audio)
使用ffmpeg将指定文件夹中的所有视频文件转换为音频文件
支持多种视频格式和音频编码格式
"""

import os
import sys
import argparse
import subprocess
import concurrent.futures
from pathlib import Path
from typing import List, Tuple, Dict
from datetime import datetime
from tqdm import tqdm
import shutil

class VideoToAudioConverter:
    """视频转音频转换器"""
    
    # 支持的视频格式
    SUPPORTED_VIDEO_FORMATS = {
        '.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', 
        '.m4v', '.mpg', '.mpeg', '.3gp', '.mts', '.m2ts', '.ts',
        '.rm', '.rmvb', '.asf', '.vob', '.ogv', '.divx'
    }
    
    # 音频编码格式和参数
    AUDIO_FORMATS = {
        'mp3': {
            'ext': '.mp3',
            'codec': 'libmp3lame',
            'args': ['-q:a', '2'],  # 0-9, 0最好
            'bitrate': '192k'
        },
        'aac': {
            'ext': '.m4a',
            'codec': 'aac',
            'args': ['-b:a', '192k'],
            'bitrate': '192k'
        },
        'flac': {
            'ext': '.flac',
            'codec': 'flac',
            'args': ['-compression_level', '8'],  # 0-12, 12最高
            'bitrate': None
        },
        'wav': {
            'ext': '.wav',
            'codec': 'pcm_s16le',
            'args': [],
            'bitrate': None
        },
        'opus': {
            'ext': '.opus',
            'codec': 'libopus',
            'args': ['-b:a', '128k'],
            'bitrate': '128k'
        },
        'ogg': {
            'ext': '.ogg',
            'codec': 'libvorbis',
            'args': ['-q:a', '5'],  # -1 to 10, 10最好
            'bitrate': None
        }
    }
    
    def __init__(self, ffmpeg_path: str = None):
        """
        初始化转换器
        
        参数:
            ffmpeg_path: ffmpeg可执行文件路径，如果为None则从系统PATH查找
        """
        self.ffmpeg_path = ffmpeg_path or 'ffmpeg'
        self._check_ffmpeg()
    
    def _check_ffmpeg(self) -> bool:
        """检查ffmpeg是否可用"""
        try:
            result = subprocess.run(
                [self.ffmpeg_path, '-version'],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            if result.returncode == 0:
                # 获取ffmpeg版本
                version_line = result.stdout.split('\n')[0]
                print(f"✓ 找到ffmpeg: {version_line}")
                return True
            else:
                print(f"✗ ffmpeg检查失败: {result.stderr}")
                return False
        except FileNotFoundError:
            print(f"✗ 找不到ffmpeg: {self.ffmpeg_path}")
            print("请安装ffmpeg:")
            print("  Ubuntu/Debian: sudo apt install ffmpeg")
            print("  macOS: brew install ffmpeg")
            print("  Windows: 从 https://ffmpeg.org/download.html 下载")
            return False
    
    def get_video_info(self, video_path: str) -> Dict:
        """获取视频文件信息"""
        cmd = [
            self.ffmpeg_path,
            '-i', video_path,
            '-hide_banner',
            '-loglevel', 'error',
            '-f', 'null',
            '-'
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            info = {'path': video_path, 'size': os.path.getsize(video_path)}
            
            # 从错误输出中解析信息（ffmpeg在分析文件时输出到stderr）
            lines = result.stderr.split('\n')
            for line in lines:
                if 'Duration:' in line:
                    # 解析时长
                    parts = line.split(',')
                    for part in parts:
                        if 'Duration:' in part:
                            duration = part.split('Duration:')[1].strip()
                            info['duration'] = duration.split()[0]
                
                elif 'Stream' in line and 'Audio:' in line:
                    # 解析音频信息
                    if 'Audio:' in line:
                        info['has_audio'] = True
                        if 'Hz' in line:
                            try:
                                hz_part = line.split('Hz')[0]
                                hz = hz_part.split()[-1]
                                info['sample_rate'] = hz
                            except:
                                pass
            
            if 'has_audio' not in info:
                info['has_audio'] = False
            
            return info
            
        except subprocess.TimeoutExpired:
            print(f"获取视频信息超时: {video_path}")
            return {'path': video_path, 'has_audio': False}
        except Exception as e:
            print(f"获取视频信息失败 {video_path}: {e}")
            return {'path': video_path, 'has_audio': False}
    
    def convert_video_to_audio(
        self,
        video_path: str,
        audio_path: str,
        audio_format: str = 'mp3',
        quality: int = None,
        bitrate: str = None,
        sample_rate: int = None,
        channels: int = None,
        overwrite: bool = True
    ) -> Tuple[bool, str]:
        """
        转换单个视频文件为音频
        
        参数:
            video_path: 视频文件路径
            audio_path: 音频输出路径
            audio_format: 音频格式 (mp3, aac, flac, wav, opus, ogg)
            quality: 质量参数 (格式相关)
            bitrate: 比特率 (如 '192k')
            sample_rate: 采样率 (如 44100)
            channels: 声道数 (1=单声道, 2=立体声)
            overwrite: 是否覆盖已存在的文件
            
        返回:
            (是否成功, 错误信息)
        """
        # 检查输入文件
        if not os.path.exists(video_path):
            return False, f"视频文件不存在: {video_path}"
        
        # 检查输出目录
        output_dir = os.path.dirname(audio_path)
        os.makedirs(output_dir, exist_ok=True)
        
        # 检查是否已存在
        if not overwrite and os.path.exists(audio_path):
            return False, f"输出文件已存在: {audio_path}"
        
        # 获取音频格式配置
        if audio_format not in self.AUDIO_FORMATS:
            return False, f"不支持的音频格式: {audio_format}"
        
        format_config = self.AUDIO_FORMATS[audio_format]
        
        # 构建ffmpeg命令
        cmd = [self.ffmpeg_path, '-i', video_path]
        
        # 添加音频参数
        cmd.extend(['-vn'])  # 不要视频
        cmd.extend(['-sn'])  # 不要字幕
        cmd.extend(['-dn'])  # 不要数据
        
        # 音频编解码器
        cmd.extend(['-acodec', format_config['codec']])
        
        # 质量参数
        if format_config['args']:
            cmd.extend(format_config['args'])
        
        # 自定义质量参数
        if quality is not None:
            if audio_format == 'mp3':
                cmd.extend(['-q:a', str(quality)])  # 0-9, 0最好
            elif audio_format == 'ogg':
                cmd.extend(['-q:a', str(quality)])  # -1-10, 10最好
        
        # 比特率
        if bitrate:
            cmd.extend(['-b:a', bitrate])
        elif format_config.get('bitrate'):
            cmd.extend(['-b:a', format_config['bitrate']])
        
        # 采样率
        if sample_rate:
            cmd.extend(['-ar', str(sample_rate)])
        
        # 声道数
        if channels:
            cmd.extend(['-ac', str(channels)])
        
        # 其他参数
        cmd.extend(['-y' if overwrite else '-n'])  # 是否覆盖
        cmd.extend(['-loglevel', 'error'])  # 只显示错误
        cmd.append(audio_path)
        
        try:
            # 执行转换
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,  # 1小时超时
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            if result.returncode == 0:
                # 检查输出文件
                if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
                    return True, "转换成功"
                else:
                    return False, "转换后文件为空或不存在"
            else:
                error_msg = result.stderr.strip() or "未知错误"
                return False, f"ffmpeg错误: {error_msg}"
                
        except subprocess.TimeoutExpired:
            return False, "转换超时 (超过1小时)"
        except Exception as e:
            return False, f"转换异常: {str(e)}"
    
    def batch_convert(
        self,
        input_dir: str,
        output_dir: str = None,
        audio_format: str = 'mp3',
        quality: int = None,
        bitrate: str = None,
        sample_rate: int = None,
        channels: int = None,
        recursive: bool = False,
        keep_structure: bool = False,
        overwrite: bool = True,
        max_workers: int = 2
    ) -> Dict:
        """
        批量转换目录中的所有视频文件
        
        参数:
            input_dir: 输入目录
            output_dir: 输出目录 (None则为input_dir/audio)
            audio_format: 音频格式
            quality: 质量参数
            bitrate: 比特率
            sample_rate: 采样率
            channels: 声道数
            recursive: 是否递归处理子目录
            keep_structure: 是否保持目录结构
            overwrite: 是否覆盖已存在的文件
            max_workers: 最大并行任务数
            
        返回:
            转换统计信息
        """
        input_path = Path(input_dir)
        
        # 检查输入目录
        if not input_path.exists() or not input_path.is_dir():
            return {'error': f"输入目录不存在: {input_dir}"}
        
        # 设置输出目录
        if output_dir is None:
            output_path = input_path / 'audio_output'
        else:
            output_path = Path(output_dir)
        
        # 创建输出目录
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 查找视频文件
        video_files = []
        if recursive:
            # 递归查找
            for root, dirs, files in os.walk(input_dir):
                for file in files:
                    file_path = Path(root) / file
                    if file_path.suffix.lower() in self.SUPPORTED_VIDEO_FORMATS:
                        video_files.append(file_path)
        else:
            # 只查找当前目录
            for file in input_path.iterdir():
                if file.is_file() and file.suffix.lower() in self.SUPPORTED_VIDEO_FORMATS:
                    video_files.append(file)
        
        if not video_files:
            return {
                'total': 0,
                'success': 0,
                'failed': 0,
                'skipped': 0,
                'no_audio': 0,
                'message': f"在 {input_dir} 中没有找到支持的视频文件"
            }
        
        print(f"找到 {len(video_files)} 个视频文件")
        
        # 统计信息
        stats = {
            'total': len(video_files),
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'no_audio': 0,
            'start_time': datetime.now(),
            'output_dir': str(output_path)
        }
        
        # 进度条
        pbar = tqdm(total=len(video_files), desc="转换进度", unit="文件")
        
        # 创建任务列表
        tasks = []
        for video_file in video_files:
            # 生成输出路径
            if keep_structure:
                # 保持目录结构
                rel_path = video_file.relative_to(input_path)
                audio_file = output_path / rel_path.with_suffix(self.AUDIO_FORMATS[audio_format]['ext'])
                audio_file.parent.mkdir(parents=True, exist_ok=True)
            else:
                # 扁平化结构
                audio_file = output_path / f"{video_file.stem}{self.AUDIO_FORMATS[audio_format]['ext']}"
            
            # 检查是否跳过
            if not overwrite and audio_file.exists():
                stats['skipped'] += 1
                pbar.update(1)
                pbar.set_postfix({'状态': f"跳过 {video_file.name}"})
                continue
            
            # 创建转换任务
            task = {
                'video_path': str(video_file),
                'audio_path': str(audio_file),
                'audio_format': audio_format,
                'quality': quality,
                'bitrate': bitrate,
                'sample_rate': sample_rate,
                'channels': channels,
                'overwrite': overwrite
            }
            tasks.append(task)
        
        # 并行处理
        if max_workers > 1 and len(tasks) > 1:
            print(f"使用 {max_workers} 个线程并行处理...")
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交任务
                future_to_task = {
                    executor.submit(
                        self.convert_video_to_audio,
                        **task
                    ): task for task in tasks
                }
                
                # 处理结果
                for future in concurrent.futures.as_completed(future_to_task):
                    task = future_to_task[future]
                    video_name = os.path.basename(task['video_path'])
                    
                    try:
                        success, message = future.result(timeout=3600)
                        
                        if success:
                            stats['success'] += 1
                            pbar.set_postfix({'状态': f"✓ {video_name}"})
                        else:
                            stats['failed'] += 1
                            pbar.set_postfix({'状态': f"✗ {video_name}"})
                            print(f"\n转换失败 {video_name}: {message}")
                            
                    except concurrent.futures.TimeoutError:
                        stats['failed'] += 1
                        pbar.set_postfix({'状态': f"⏰ {video_name}"})
                        print(f"\n转换超时: {video_name}")
                    except Exception as e:
                        stats['failed'] += 1
                        pbar.set_postfix({'状态': f"💥 {video_name}"})
                        print(f"\n转换异常 {video_name}: {e}")
                    
                    pbar.update(1)
        else:
            # 单线程处理
            for task in tasks:
                video_name = os.path.basename(task['video_path'])
                
                success, message = self.convert_video_to_audio(**task)
                
                if success:
                    stats['success'] += 1
                    pbar.set_postfix({'状态': f"✓ {video_name}"})
                else:
                    stats['failed'] += 1
                    pbar.set_postfix({'状态': f"✗ {video_name}"})
                    print(f"\n转换失败 {video_name}: {message}")
                
                pbar.update(1)
        
        pbar.close()
        
        # 计算总耗时
        stats['end_time'] = datetime.now()
        stats['duration'] = stats['end_time'] - stats['start_time']
        
        return stats

def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="视频批量转音频工具 - 使用ffmpeg将视频文件转换为音频",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 基本用法: 转换当前目录所有视频为MP3
  python video2audio.py .
  
  # 指定输入输出目录
  python video2audio.py /path/to/videos -o /path/to/audio
  
  # 转换为AAC格式
  python video2audio.py /path/to/videos --format aac
  
  # 转换为无损FLAC格式
  python video2audio.py /path/to/videos --format flac
  
  # 高质量MP3 (质量0最好)
  python video2audio.py /path/to/videos --quality 0
  
  # 192k比特率
  python video2audio.py /path/to/videos --bitrate 192k
  
  # 单声道, 16kHz采样率
  python video2audio.py /path/to/videos --channels 1 --sample-rate 16000
  
  # 递归处理子目录并保持目录结构
  python video2audio.py /path/to/videos -r -k
  
  # 4线程并行处理
  python video2audio.py /path/to/videos --threads 4
  
  # 不覆盖已存在的文件
  python video2audio.py /path/to/videos --no-overwrite
  
  # 查看支持的格式
  python video2audio.py --list-formats
        """
    )
    
    # 必需参数
    parser.add_argument("input_dir", nargs="?", default=".", 
                       help="输入目录 (默认: 当前目录)")
    
    # 输出选项
    parser.add_argument("-o", "--output", help="输出目录 (默认: input_dir/audio_output)")
    parser.add_argument("-f", "--format", default="mp3", 
                       choices=['mp3', 'aac', 'flac', 'wav', 'opus', 'ogg'],
                       help="音频格式 (默认: mp3)")
    
    # 质量选项
    parser.add_argument("-q", "--quality", type=int, 
                       help="质量参数 (MP3: 0-9, 0最好; OGG: -1-10, 10最好)")
    parser.add_argument("-b", "--bitrate", help="比特率 (如: 128k, 192k, 320k)")
    parser.add_argument("--sample-rate", type=int, 
                       help="采样率 (如: 44100, 48000, 16000)")
    parser.add_argument("--channels", type=int, choices=[1, 2],
                       help="声道数 (1=单声道, 2=立体声)")
    
    # 处理选项
    parser.add_argument("-r", "--recursive", action="store_true",
                       help="递归处理子目录")
    parser.add_argument("-k", "--keep-structure", action="store_true",
                       help="保持目录结构")
    parser.add_argument("--no-overwrite", action="store_true",
                       help="不覆盖已存在的文件")
    parser.add_argument("-t", "--threads", type=int, default=2,
                       help="并行线程数 (默认: 2)")
    parser.add_argument("--ffmpeg-path", help="ffmpeg可执行文件路径")
    
    # 信息选项
    parser.add_argument("--list-formats", action="store_true",
                       help="显示支持的视频格式并退出")
    parser.add_argument("--audio-info", action="store_true",
                       help="显示音频格式信息并退出")
    
    args = parser.parse_args()
    
    # 显示支持的格式
    converter = VideoToAudioConverter(args.ffmpeg_path)
    
    if args.list_formats:
        print("支持的视频格式:")
        for fmt in sorted(converter.SUPPORTED_VIDEO_FORMATS):
            print(f"  {fmt}")
        sys.exit(0)
    
    if args.audio_info:
        print("支持的音频格式:")
        for fmt, config in converter.AUDIO_FORMATS.items():
            print(f"\n{fmt.upper()}:")
            print(f"  扩展名: {config['ext']}")
            print(f"  编解码器: {config['codec']}")
            if config.get('bitrate'):
                print(f"  默认比特率: {config['bitrate']}")
            if config['args']:
                print(f"  默认参数: {' '.join(config['args'])}")
        sys.exit(0)
    
    # 检查输入目录
    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        print(f"错误: 目录不存在: {input_dir}")
        sys.exit(1)
    
    # 检查ffmpeg
    if not converter._check_ffmpeg():
        sys.exit(1)
    
    # 显示配置信息
    print(f"\n{'='*60}")
    print("视频批量转音频工具")
    print(f"{'='*60}")
    print(f"输入目录: {input_dir.resolve()}")
    if args.output:
        print(f"输出目录: {args.output}")
    print(f"音频格式: {args.format.upper()}")
    
    if args.quality is not None:
        print(f"质量设置: {args.quality}")
    if args.bitrate:
        print(f"比特率: {args.bitrate}")
    if args.sample_rate:
        print(f"采样率: {args.sample_rate} Hz")
    if args.channels:
        print(f"声道数: {args.channels}")
    
    print(f"递归处理: {'是' if args.recursive else '否'}")
    print(f"保持目录结构: {'是' if args.keep_structure else '否'}")
    print(f"覆盖已存在: {'否' if args.no_overwrite else '是'}")
    print(f"并行线程: {args.threads}")
    print(f"{'='*60}\n")
    
    # 执行转换
    try:
        stats = converter.batch_convert(
            input_dir=str(input_dir),
            output_dir=args.output,
            audio_format=args.format,
            quality=args.quality,
            bitrate=args.bitrate,
            sample_rate=args.sample_rate,
            channels=args.channels,
            recursive=args.recursive,
            keep_structure=args.keep_structure,
            overwrite=not args.no_overwrite,
            max_workers=args.threads
        )
        
        # 显示结果
        print(f"\n{'='*60}")
        print("转换完成!")
        print(f"{'='*60}")
        
        if 'error' in stats:
            print(f"错误: {stats['error']}")
        else:
            print(f"总文件数: {stats['total']}")
            print(f"成功转换: {stats['success']}")
            print(f"转换失败: {stats['failed']}")
            print(f"跳过文件: {stats.get('skipped', 0)}")
            print(f"无音频文件: {stats.get('no_audio', 0)}")
            print(f"输出目录: {stats['output_dir']}")
            print(f"总耗时: {stats['duration']}")
        
        print(f"{'='*60}")
        
    except KeyboardInterrupt:
        print("\n\n用户中断，停止转换...")
        sys.exit(1)
    except Exception as e:
        print(f"\n转换过程中发生错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()