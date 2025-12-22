import os
import subprocess
import sys
import tempfile
from pathlib import Path

def compress_with_opus_then_mp3(input_folder, output_folder=None, opus_bitrate='6k', mp3_bitrate='16k'):
    """
    两阶段压缩：先用Opus极限压缩，再转MP3保持兼容性
    
    Args:
        input_folder: 输入文件夹
        output_folder: 输出文件夹
        opus_bitrate: Opus压缩比特率（6k-8k最小）
        mp3_bitrate: MP3最终比特率（16k-24k兼容）
    """
    if output_folder is None:
        output_folder = os.path.join(input_folder, "opus_mp3_mini")
    
    os.makedirs(output_folder, exist_ok=True)
    
    # 支持的输入格式
    audio_extensions = {
        '.mp3', '.wav', '.flac', '.m4a', '.aac', 
        '.ogg', '.opus', '.wma', '.amr', '.aiff', '.au'
    }
    
    processed_count = 0
    failed_files = []
    
    print("🎯 两阶段极致压缩模式")
    print("="*60)
    print(f"📁 输入文件夹: {input_folder}")
    print(f"💾 输出文件夹: {output_folder}")
    print(f"⚙️  阶段1: Opus极限压缩 ({opus_bitrate}, 8kHz)")
    print(f"⚙️  阶段2: MP3兼容转换 ({mp3_bitrate}, 8kHz)")
    print("="*60)
    
    for filename in sorted(os.listdir(input_folder)):
        file_ext = os.path.splitext(filename)[1].lower()
        if file_ext in audio_extensions:
            input_path = os.path.join(input_folder, filename)
            
            if not os.path.isfile(input_path):
                continue
            
            # 生成输出文件名
            name_without_ext = os.path.splitext(filename)[0]
            output_filename = f"{name_without_ext}.mp3"
            output_path = os.path.join(output_folder, output_filename)
            
            # 执行两阶段压缩
            success, message = two_stage_compress(input_path, output_path, opus_bitrate, mp3_bitrate)
            
            if success:
                processed_count += 1
            else:
                failed_files.append((filename, message))
    
    # 显示结果
    print_summary(processed_count, failed_files, output_folder, input_folder)
    return output_folder

def two_stage_compress(input_path, output_path, opus_bitrate='6k', mp3_bitrate='16k'):
    """
    两阶段压缩：Opus → MP3
    """
    filename = os.path.basename(input_path)
    print(f"\n🎯 处理: {filename}")
    
    try:
        # 获取原始文件大小
        if not os.path.exists(input_path):
            print("   ❌ 文件不存在")
            return False, "文件不存在"
        
        original_size = os.path.getsize(input_path) / 1024  # KB
        
        # 创建临时文件
        with tempfile.NamedTemporaryFile(suffix='.opus', delete=False) as tmp:
            temp_opus_path = tmp.name
        
        try:
            # ========== 阶段1: Opus极限压缩 ==========
            print("   📥 阶段1: Opus极限压缩...")
            opus_cmd = [
                'ffmpeg',
                '-i', input_path,                    # 输入
                
                # 音频处理：人声优化
                '-af', 'lowpass=3400,highpass=300',  # 带通滤波
                '-af', 'compand=attacks=0.1:decays=0.5',  # 动态压缩
                '-af', 'silenceremove=stop_periods=-1:stop_duration=0.5:stop_threshold=-30dB',  # 去静音
                
                # Opus编码（最小体积）
                '-c:a', 'libopus',
                '-b:a', opus_bitrate,                # 极低比特率
                '-vbr', 'constrained',               # 约束VBR
                '-compression_level', '10',          # 最高压缩
                '-application', 'voip',              # 语音优化
                '-frame_duration', '60',             # 最长帧
                
                # 音频参数
                '-ar', '8000',                       # 8kHz采样
                '-ac', '1',                          # 单声道
                
                '-loglevel', 'error',
                '-y', temp_opus_path
            ]
            
            result1 = subprocess.run(opus_cmd, capture_output=True, text=True, timeout=300)
            if result1.returncode != 0:
                print(f"   ❌ Opus压缩失败: {result1.stderr[:100]}")
                return False, f"Opus失败: {result1.stderr[:100]}"
            
            if not os.path.exists(temp_opus_path) or os.path.getsize(temp_opus_path) == 0:
                print("   ❌ Opus文件未生成")
                return False, "Opus文件未生成"
            
            opus_size = os.path.getsize(temp_opus_path) / 1024
            print(f"   ✅ Opus压缩完成: {opus_size:.1f}KB")
            
            # ========== 阶段2: MP3兼容转换 ==========
            print("   📤 阶段2: MP3兼容转换...")
            mp3_cmd = [
                'ffmpeg',
                '-i', temp_opus_path,                # Opus文件
                
                # MP3编码
                '-c:a', 'libmp3lame',
                '-b:a', mp3_bitrate,                 # 兼容比特率
                '-ar', '8000',                       # 保持8kHz
                '-ac', '1',                          # 保持单声道
                '-q:a', '5',                         # 中等质量
                
                # 元数据
                '-write_id3v1', '1',
                '-id3v2_version', '3',
                '-map_metadata', '0',
                
                '-loglevel', 'error',
                '-y', output_path
            ]
            
            result2 = subprocess.run(mp3_cmd, capture_output=True, text=True, timeout=300)
            if result2.returncode != 0:
                print(f"   ❌ MP3转换失败: {result2.stderr[:100]}")
                return False, f"MP3失败: {result2.stderr[:100]}"
            
            if os.path.exists(output_path):
                final_size = os.path.getsize(output_path) / 1024
                ratio = (final_size / original_size) * 100
                
                # 显示结果
                print(f"   ✅ 最终MP3: {final_size:.1f}KB")
                print(f"   📊 原始: {original_size:.1f}KB → 最终: {final_size:.1f}KB")
                print(f"   📉 总压缩率: {ratio:.1f}%")
                
                # 中间文件对比
                stage1_ratio = (opus_size / original_size) * 100
                stage2_ratio = (final_size / opus_size) * 100
                print(f"   🔄 阶段1压缩: {stage1_ratio:.1f}%")
                print(f"   🔄 阶段2转换: {stage2_ratio:.1f}%")
                
                return True, f"成功: {ratio:.1f}%"
            else:
                print("   ❌ 最终文件未生成")
                return False, "最终文件未生成"
                
        finally:
            # 清理临时文件
            if os.path.exists(temp_opus_path):
                os.unlink(temp_opus_path)
                
    except subprocess.TimeoutExpired:
        print("   ⏰ 超时: 处理时间过长")
        return False, "超时"
    except Exception as e:
        print(f"   ❌ 错误: {str(e)[:100]}")
        return False, f"错误: {str(e)[:50]}"

def direct_opus_to_mp3(input_folder, output_folder=None, quality="extreme"):
    """
    直接Opus压缩并转MP3的优化版本
    
    quality: extreme(6k), high(8k), standard(12k)
    """
    quality_settings = {
        "extreme": {"opus_bitrate": "6k", "mp3_bitrate": "12k", "name": "极限压缩"},
        "high": {"opus_bitrate": "8k", "mp3_bitrate": "16k", "name": "高质量压缩"},
        "standard": {"opus_bitrate": "12k", "mp3_bitrate": "24k", "name": "标准压缩"},
    }
    
    setting = quality_settings.get(quality, quality_settings["extreme"])
    
    print(f"\n🎯 {setting['name']}模式")
    print(f"   Opus: {setting['opus_bitrate']} → MP3: {setting['mp3_bitrate']}")
    
    if output_folder is None:
        output_folder = os.path.join(input_folder, f"minimp3_{quality}")
    
    return compress_with_opus_then_mp3(
        input_folder, 
        output_folder,
        opus_bitrate=setting['opus_bitrate'],
        mp3_bitrate=setting['mp3_bitrate']
    )

def smart_dual_output(input_folder):
    """
    智能双输出：生成两种版本
    1. Opus最小版（自己保存）
    2. MP3兼容版（微信发送）
    """
    opus_folder = os.path.join(input_folder, "opus_mini")
    mp3_folder = os.path.join(input_folder, "mp3_wechat")
    
    os.makedirs(opus_folder, exist_ok=True)
    os.makedirs(mp3_folder, exist_ok=True)
    
    audio_extensions = {'.mp3', '.wav', '.flac', '.m4a', '.aac'}
    
    print("🤖 智能双输出模式")
    print("="*60)
    print(f"🎯 Opus最小版: {opus_folder}")
    print(f"📱 MP3微信版: {mp3_folder}")
    print("="*60)
    
    for filename in sorted(os.listdir(input_folder)):
        file_ext = os.path.splitext(filename)[1].lower()
        if file_ext in audio_extensions:
            input_path = os.path.join(input_folder, filename)
            
            if not os.path.isfile(input_path):
                continue
            
            name = os.path.splitext(filename)[0]
            original_size = os.path.getsize(input_path) / 1024
            
            print(f"\n📦 处理: {filename} ({original_size:.1f}KB)")
            
            # 1. 生成Opus最小版
            opus_path = os.path.join(opus_folder, f"{name}.opus")
            opus_cmd = [
                'ffmpeg', '-i', input_path,
                '-c:a', 'libopus', '-b:a', '6k', '-vbr', 'constrained',
                '-compression_level', '10', '-application', 'voip',
                '-ar', '8000', '-ac', '1',
                '-loglevel', 'error', '-y', opus_path
            ]
            
            subprocess.run(opus_cmd, capture_output=True)
            if os.path.exists(opus_path):
                opus_size = os.path.getsize(opus_path) / 1024
                opus_ratio = (opus_size / original_size) * 100
                print(f"   🎯 Opus版: {opus_size:.1f}KB ({opus_ratio:.1f}%)")
            
            # 2. 生成MP3微信版
            mp3_path = os.path.join(mp3_folder, f"{name}.mp3")
            
            # 如果有Opus版，从Opus转换（最小文件）
            if os.path.exists(opus_path) and opus_size < original_size * 0.5:  # 如果Opus确实更小
                source = opus_path
            else:
                source = input_path
            
            mp3_cmd = [
                'ffmpeg', '-i', source,
                '-c:a', 'libmp3lame', '-b:a', '16k',
                '-ar', '8000', '-ac', '1', '-q:a', '5',
                '-write_id3v1', '1', '-id3v2_version', '3',
                '-loglevel', 'error', '-y', mp3_path
            ]
            
            subprocess.run(mp3_cmd, capture_output=True)
            if os.path.exists(mp3_path):
                mp3_size = os.path.getsize(mp3_path) / 1024
                mp3_ratio = (mp3_size / original_size) * 100
                print(f"   📱 MP3版: {mp3_size:.1f}KB ({mp3_ratio:.1f}%)")
    
    print(f"\n✅ 双输出完成！")
    print(f"   💾 Opus最小版: {opus_folder}")
    print(f"   📤 MP3微信版: {mp3_folder}")
    
    return opus_folder, mp3_folder

def print_summary(processed_count, failed_files, output_folder, input_folder):
    """显示总结信息"""
    print(f"\n" + "="*60)
    print(f"✅ 处理完成！")
    print(f"   成功: {processed_count} 个文件")
    print(f"   失败: {len(failed_files)} 个文件")
    
    if failed_files:
        print(f"\n❌ 失败的文件:")
        for i, (filename, error) in enumerate(failed_files, 1):
            print(f"   {i:2d}. {filename}: {error}")
    
    print(f"\n📁 输出文件夹: {output_folder}")
    
    # 显示统计
    if processed_count > 0:
        total_original = 0
        total_final = 0
        
        for filename in os.listdir(input_folder):
            if filename.lower().endswith(('.mp3', '.wav', '.flac', '.m4a', '.aac')):
                filepath = os.path.join(input_folder, filename)
                if os.path.isfile(filepath):
                    total_original += os.path.getsize(filepath)
        
        for filename in os.listdir(output_folder):
            if filename.lower().endswith('.mp3'):
                filepath = os.path.join(output_folder, filename)
                if os.path.isfile(filepath):
                    total_final += os.path.getsize(filepath)
        
        if total_original > 0:
            orig_mb = total_original / (1024 * 1024)
            final_mb = total_final / (1024 * 1024)
            ratio = (total_final / total_original) * 100
            
            print(f"\n📊 统计信息:")
            print(f"   原始总大小: {orig_mb:.2f} MB")
            print(f"   最终总大小: {final_mb:.2f} MB")
            print(f"   总体压缩率: {ratio:.1f}%")
            print(f"   节省空间: {orig_mb - final_mb:.2f} MB")

def main():
    """主程序"""
    print("🎵 音频极致压缩工具 (Opus+MP3双阶段)")
    print("="*60)
    
    # 获取文件夹路径
    if len(sys.argv) > 1:
        folder = sys.argv[1]
    else:
        folder = input("请输入音频文件夹路径: ").strip('"')
    
    if not os.path.isdir(folder):
        print(f"❌ 错误: 文件夹不存在 - {folder}")
        input("按回车键退出...")
        return
    
    print(f"📁 输入文件夹: {folder}")
    
    # 选择模式
    print("\n请选择压缩模式:")
    print("1. 极限压缩模式 (6k→12k) - 最小体积")
    print("2. 高质量模式 (8k→16k) - 推荐语音")
    print("3. 标准模式 (12k→24k) - 音质较好")
    print("4. 智能双输出 - 同时生成Opus和MP3")
    print("5. 自定义参数")
    
    choice = input("\n请选择 (1-5): ").strip()
    
    if choice == "1":
        output_folder = direct_opus_to_mp3(folder, quality="extreme")
    elif choice == "2":
        output_folder = direct_opus_to_mp3(folder, quality="high")
    elif choice == "3":
        output_folder = direct_opus_to_mp3(folder, quality="standard")
    elif choice == "4":
        opus_folder, mp3_folder = smart_dual_output(folder)
        output_folder = mp3_folder
    elif choice == "5":
        print("\n🔧 自定义参数:")
        opus_bitrate = input("Opus比特率 (如 6k, 8k, 12k): ").strip() or "6k"
        mp3_bitrate = input("MP3比特率 (如 12k, 16k, 24k): ").strip() or "16k"
        output_folder = compress_with_opus_then_mp3(
            folder, 
            opus_bitrate=opus_bitrate, 
            mp3_bitrate=mp3_bitrate
        )
    else:
        print("使用默认: 高质量模式")
        output_folder = direct_opus_to_mp3(folder, quality="high")
    
    # 完成提示
    print(f"\n🎉 压缩完成！")
    print(f"📁 文件保存在: {output_folder}")
    
    # 询问是否打开文件夹
    open_folder = input("\n是否打开输出文件夹？(y/n): ").lower()
    if open_folder == 'y':
        try:
            if sys.platform == 'win32':
                os.startfile(output_folder)
            elif sys.platform == 'darwin':
                subprocess.run(['open', output_folder])
            else:
                subprocess.run(['xdg-open', output_folder])
        except:
            pass
    
    input("\n按回车键退出...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  用户中断操作")
    except Exception as e:
        print(f"\n❌ 程序出错: {e}")
        input("按回车键退出...")