import os
import subprocess
from pathlib import Path

def compress_mp4_files(input_folder, output_folder=None, crf=28, preset='medium', audio_bitrate='64k'):
    """
    压缩指定文件夹中的所有MP4文件
    
    参数:
    input_folder: 输入文件夹路径
    output_folder: 输出文件夹路径（如果为None，则在原文件夹创建compressed子文件夹）
    crf: 压缩质量，值越大压缩率越高（推荐23-28，微信发送可用28）
    preset: 编码预设，可选 ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow
    audio_bitrate: 音频比特率
    """
    
    # 如果未指定输出文件夹，则在原文件夹下创建compressed文件夹
    if output_folder is None:
        output_folder = os.path.join(input_folder, 'compressed')
    
    # 创建输出文件夹
    os.makedirs(output_folder, exist_ok=True)
    
    # 支持的文件扩展名
    video_extensions = {'.mp4', '.MP4', '.Mp4'}
    
    # 遍历文件夹中的所有文件
    for file in os.listdir(input_folder):
        file_path = os.path.join(input_folder, file)
        
        # 检查是否是文件且是mp4格式
        if os.path.isfile(file_path) and os.path.splitext(file)[1] in video_extensions:
            output_path = os.path.join(output_folder, file)
            
            print(f"正在压缩: {file}")
            
            # FFmpeg压缩命令
            cmd = [
                'ffmpeg',
                '-i', file_path,           # 输入文件
                '-c:v', 'libx264',         # 视频编码器
                '-crf', str(crf),          # 质量参数
                '-preset', preset,         # 编码速度预设
                '-c:a', 'aac',            # 音频编码器
                '-b:a', audio_bitrate,     # 音频比特率
                '-movflags', '+faststart', # 优化网络播放
                '-y',                      # 覆盖输出文件
                output_path
            ]
            
            try:
                # 执行压缩命令
                subprocess.run(cmd, check=True, capture_output=True)
                print(f"✓ 完成: {file}")
                
                # 显示压缩前后大小对比
                original_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
                compressed_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
                ratio = compressed_size / original_size * 100
                
                print(f"  原始大小: {original_size:.2f} MB")
                print(f"  压缩大小: {compressed_size:.2f} MB")
                print(f"  压缩率: {ratio:.1f}%\n")
                
            except subprocess.CalledProcessError as e:
                print(f"✗ 压缩失败: {file}")
                print(f"  错误信息: {e.stderr.decode() if e.stderr else '未知错误'}")
            except Exception as e:
                print(f"✗ 处理出错: {file}")
                print(f"  错误: {str(e)}")

def compress_for_wechat(input_folder, output_folder=None):
    """
    专门为微信发送优化的压缩函数
    """
    # 微信发送推荐参数
    compress_mp4_files(
        input_folder=input_folder,
        output_folder=output_folder,
        crf=28,              # 较高压缩率
        preset='fast',      # 较快编码速度
        audio_bitrate='48k' # 较低音频质量
    )

if __name__ == "__main__":
    # 使用示例
    folder_path = input("请输入包含MP4文件的文件夹路径: ").strip()
    
    if os.path.isdir(folder_path):
        print(f"开始处理文件夹: {folder_path}")
        compress_for_wechat(folder_path)
        print("\n压缩完成！文件保存在 'compressed' 子文件夹中")
    else:
        print("错误: 指定的文件夹不存在！")