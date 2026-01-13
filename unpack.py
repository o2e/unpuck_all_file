import os
import re
import subprocess
import concurrent.futures
import argparse
import readline  # 增强终端输入体验 (macOS/Linux)
import sys
import shutil
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn, MofNCompleteColumn
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.text import Text

# 初始化 Rich 控制台
console = Console()


def ask_yes_no(prompt):
    """
    循环请求用户输入，直到得到 y/n 为止。
    """
    while True:
        response = console.input(prompt).lower().strip()
        if response.startswith('y'):
            return True
        if response.startswith('n'):
            return False
        console.print("[yellow]无效输入，请输入 y (是) 或 n (否)。[/]")


def decompress_archive_with_7z(archive_path, extract_dir, progress_task=None):
    """
    使用 7z 命令行工具解压单个压缩文件。
    采用可靠解压方案：
    1. 先解压到 extract_dir.out_tmp
    2. 成功后在里面写入 .zipp_done 标记
    3. 最后重命名为 extract_dir
    """
    archive_name = os.path.basename(archive_path)
    tmp_extract_dir = extract_dir + ".out_tmp"
    
    # 使用 Text 对象手动构建日志
    msg = Text()
    msg.append("[", style="bold cyan")
    msg.append(archive_name, style="bold cyan")
    msg.append("] 开始解压...", style="bold cyan")
    console.print(msg)

    try:
        # 清理并创建临时解压目录，确保环境绝对纯净，防止旧文件污染
        if os.path.exists(tmp_extract_dir):
            shutil.rmtree(tmp_extract_dir)
        os.makedirs(tmp_extract_dir, exist_ok=True)

        # 优先使用用户提供的最新版 7zzs，否则使用系统默认的 7z
        seven_zip_cmd = '/mnt/runtime/sbin/7zzs' if os.path.exists('/mnt/runtime/sbin/7zzs') else '7z'
        
        command = [
            seven_zip_cmd,
            'x',
            f'-o{tmp_extract_dir}',
            archive_path,
            '-aoa',  # 强制覆盖已存在的文件
            '-mmt=on',
            '-p',    # 传入空密码，防止遇到加密文件时弹出交互提示
            # '-kb'    # 保留损坏的文件 (Keep Broken files)，即使 CRC 失败也尽量解出东西
        ]

        # 运行解压，并重定向 stdin 以彻底杜绝交互挂起
        result = subprocess.run(command, capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL)

        if result.returncode == 0:
            # --- 成功收尾逻辑 ---
            # 1. 如果正式目录已存在（之前的残余），先删除
            if os.path.exists(extract_dir):
                shutil.rmtree(extract_dir)
            
            # 2. 原子重命名：将临时目录正式交付
            os.rename(tmp_extract_dir, extract_dir)

            # 3. 最后写入成功标记（作为全过程的最终签名）
            done_file = os.path.join(extract_dir, ".zipp_done")
            with open(done_file, 'w') as f:
                f.write("Decompression finished successfully")

            msg = Text()
            msg.append("[", style="bold green")
            msg.append(archive_name, style="bold green")
            msg.append("] 解压成功: ", style="bold green")
            msg.append(extract_dir, style="magenta")
            console.print(msg)
            return True
        else:
            msg = Text()
            msg.append("[", style="bold red")
            msg.append(archive_name, style="bold red")
            msg.append(f"] 解压失败 (错误码: {result.returncode})", style="bold red")
            if result.stderr:
                msg.append("\n", style="dim")
                msg.append(result.stderr.strip(), style="dim")
            console.print(msg)
            return False

    except FileNotFoundError:
        console.print(Text("错误: 未找到 '7z' 命令。", style="bold red"))
        return False
    except Exception as e:
        console.print(Text(f"异常: {e}", style="bold red"))
        return False


def is_volume_part(filename):
    """
    判断文件是否为分卷压缩包的一部分，并返回分卷编号
    返回: (是否为分卷, 分卷编号, 基础名称)
    """
    lower_name = filename.lower()
    
    # 格式1: data.zip.001, data.7z.001, data.rar.001
    for ext in ['.zip.', '.7z.', '.rar.']:
        if ext in lower_name:
            idx = lower_name.rfind(ext)
            suffix = lower_name[idx + len(ext):]
            if suffix.isdigit():
                base_name = filename[:idx + len(ext) - 1]  # 保留原始大小写
                return True, int(suffix), base_name
    
    # 格式2: data.part1.rar, data.part01.rar, data.part001.rar
    match = re.match(r'(.+)\.part(\d+)\.(rar|zip|7z)$', lower_name)
    if match:
        base_name = filename[:match.start(2) - 5]  # 去掉 .partXXX
        part_num = int(match.group(2))
        return True, part_num, base_name
    
    # 格式3: data.z01, data.z02 ... data.zip (zip分卷的旧格式)
    match = re.match(r'(.+)\.z(\d+)$', lower_name)
    if match:
        base_name = match.group(1)
        part_num = int(match.group(2))
        return True, part_num, base_name
    
    # 格式4: data.001, data.002 ... (通用数字分卷)
    match = re.search(r'\.(\d{3})$', lower_name)
    if match:
        suffix = match.group(1)
        base_name = filename[:-4] # 去掉 .XXX
        return True, int(suffix), base_name

    return False, 0, filename


def get_first_volume(file_path, filename, target_directory):
    """
    如果是分卷压缩包，返回第一个分卷的路径；否则返回原路径
    """
    is_volume, vol_num, base_name = is_volume_part(filename)
    
    if not is_volume:
        # 普通压缩包，直接返回
        return file_path
    
    # 是分卷压缩包，需要找到第一个分卷
    if vol_num == 1:
        # 当前就是第一个分卷
        return file_path
    
    # 尝试找到第一个分卷
    lower_filename = filename.lower()
    
    # 尝试不同的第一分卷命名格式
    first_volume_candidates = []
    
    # 格式1: .001
    if '.zip.' in lower_filename or '.7z.' in lower_filename or '.rar.' in lower_filename:
        first_volume_candidates.append(base_name + '.001')
    
    # 格式2: .part1.rar 或 .part01.rar 或 .part001.rar
    if '.part' in lower_filename:
        match = re.search(r'\.part(\d+)\.', lower_filename)
        if match:
            ext = filename.split('.')[-1]
            # 保持相同的数字位数
            num_digits = len(match.group(1))
            first_volume_candidates.append(f"{base_name}.part{'1'.zfill(num_digits)}.{ext}")
            # 也尝试不带前导零的版本
            if num_digits > 1:
                first_volume_candidates.append(f"{base_name}.part1.{ext}")
    
    # 格式3: .z01
    if lower_filename.endswith(tuple(f'.z{i:02d}' for i in range(1, 100))) or \
       re.match(r'.+\.z\d+$', lower_filename):
        first_volume_candidates.append(base_name + '.z01')
        # 有些zip分卷第一个文件是 .zip 而不是 .z01
        first_volume_candidates.append(base_name + '.zip')
    
    # 格式4: .001 (通用)
    if re.search(r'\.\d{3}$', lower_filename):
        first_volume_candidates.append(base_name + '.001')
    
    # 检查哪个候选文件存在
    for candidate in first_volume_candidates:
        candidate_path = os.path.join(target_directory, candidate)
        if os.path.exists(candidate_path):
            return candidate_path
    
    # 如果找不到第一个分卷，返回当前文件（让7z尝试处理）
    return file_path


def main():
    parser = argparse.ArgumentParser(description="自动解压工具 (使用 7z)")
    parser.add_argument("input", help="包含压缩文件的目录路径")
    parser.add_argument("-o", "--output", help="指定解压输出目录 (如果未指定，则解压到输入目录同级)")
    parser.add_argument("-t", "--threads", type=int, help="手动指定并发线程数 (默认: CPU核心数)")
    
    args = parser.parse_args()
    target_directory = args.input.strip()
    output_base_dir = args.output.strip() if args.output else target_directory

    if not os.path.isdir(target_directory):
        console.print(f"[bold red]错误:[/] 目录 '{target_directory}' 不存在。", style="red")
        return

    # 检查 7z 命令是否可用
    has_7z = shutil.which('7z') or os.path.exists('/mnt/runtime/sbin/7zzs')
    if not has_7z:
        console.print(Panel("[bold red]未找到 '7z' 或 '7zzs' 命令[/]\n\n请确保已安装 7-Zip 并添加到系统 PATH 中，或放置在 /mnt/runtime/sbin/7zzs。", title="系统错误", border_style="red"))
        return

    console.print(f"\n[bold yellow]正在扫描目录:[/] [cyan]{target_directory}[/]")

    # 用于存储要处理的压缩包路径和解压目录
    archives_to_process = []
    # 用于去重的集合，存储基础名称
    processed_base_names = set()
    
    # 文件统计
    total_files = 0
    ignored_files = {}  # 存储被忽略的文件扩展名及数量
    normal_archive_count = 0
    volume_archive_count = 0
    skipped_count = 0  # 存储因带有 .zipp_done 而跳过的数量
    volume_counts = {}  # 存储每个分卷组的文件数量 {base_name: count}

    # 支持的压缩包扩展名
    supported_extensions = ('.zip', '.7z', '.rar')

    for filename in os.listdir(target_directory):
        file_path = os.path.join(target_directory, filename)
        if not os.path.isfile(file_path): continue
        
        total_files += 1
        lower_filename = filename.lower()
        
        # 检查压缩包逻辑 (保持不变)
        is_archive = False
        if any(lower_filename.endswith(ext) for ext in supported_extensions):
            is_archive = True
        elif any(ext in lower_filename for ext in ['.zip.', '.7z.', '.rar.']):
            is_archive = True
        elif lower_filename.endswith(tuple(f'.z{i:02d}' for i in range(1, 100))):
            is_archive = True
        elif re.search(r'\.\d{3}$', lower_filename):
            is_archive = True
        elif '.part' in lower_filename and any(lower_filename.endswith(ext) for ext in supported_extensions):
            is_archive = True
        
        if not is_archive:
            _is_vol, _, _ = is_volume_part(filename)
            if _is_vol: is_archive = True
        
        if not is_archive:
            ext = os.path.splitext(filename)[1].lower() or '(无扩展名)'
            # [调试] 如果看起来像分卷但被忽略了，打印出来
            if re.search(r'\.\d{3}$', lower_filename) or '.part' in lower_filename:
                debug_msg = Text()
                debug_msg.append("[debug] ", style="yellow")
                debug_msg.append("文件被忽略但看起来像分卷: ")
                debug_msg.append(filename, style="cyan")
                console.print(debug_msg)
                
            ignored_files[ext] = ignored_files.get(ext, 0) + 1
            continue
        
        is_volume, vol_num, base_name = is_volume_part(filename)
        if is_volume:
            volume_counts[base_name] = volume_counts.get(base_name, 0) + 1
        
        if base_name in processed_base_names: continue
        
        target_file = get_first_volume(file_path, filename, target_directory)
        target_filename = os.path.basename(target_file)
        
        # 目录清理逻辑 (保持不变)
        extract_name = target_filename
        if extract_name.lower().endswith(('.rar', '.zip')): extract_name = extract_name[:-4]
        elif extract_name.lower().endswith('.7z'): extract_name = extract_name[:-3]
        
        extract_name = re.sub(r'\.part\d+$', '', extract_name, flags=re.IGNORECASE)
        extract_name = re.sub(r'\.z\d+$', '', extract_name, flags=re.IGNORECASE)
        extract_name = re.sub(r'\.(zip|7z|rar)\.\d+$', '', extract_name, flags=re.IGNORECASE)
        extract_name = re.sub(r'\.\d{3}$', '', extract_name)
        extract_name = re.sub(r'_zip$', '', extract_name, flags=re.IGNORECASE)
        
        extract_dir = os.path.join(output_base_dir, extract_name)
        
        # --- 增加成功标记检查 ---
        done_marker = os.path.join(extract_dir, ".zipp_done")
        if os.path.exists(done_marker):
            skipped_count += 1
            processed_base_names.add(base_name)
            continue
        # ----------------------
        
        archives_to_process.append((target_file, extract_dir, is_volume, base_name))
        processed_base_names.add(base_name)
        
        if is_volume: volume_archive_count += 1
        else: normal_archive_count += 1


    if not archives_to_process:
        console.print("[yellow]未找到支持的压缩文件。[/]")
        return

    # --- 恢复详细文件列表打印 ---
    console.print(f"\n[bold]待处理压缩包详情:[/]")
    console.print("=" * 60)
    
    # 对压缩包列表排序：普通压缩包在前，分卷压缩包在后，内部按文件名排序
    archives_to_process.sort(key=lambda x: (x[2], os.path.basename(x[0]).lower()))
    
    idx_width = len(str(len(archives_to_process)))
    for idx, (archive_path, extract_dir, is_volume, base_name) in enumerate(archives_to_process, 1):
        filename = os.path.basename(archive_path)
        extract_name = os.path.basename(extract_dir)
        
        # 统一索引块，例如 [0001]
        prefix = f"[{idx:0{idx_width}}]"
        
        # 使用 Text 对象手动构建，彻底避免转义问题
        line = Text()
        line.append(prefix, style="dim")
        line.append(" ")
        
        if is_volume:
            vol_count = volume_counts.get(base_name, 1)
            line.append(filename, style="bold cyan")
            line.append(f" (共{vol_count}卷)", style="dim")
        else:
            line.append(filename, style="bold green")
        
        console.print(line)
            
        # 精确对齐逻辑：
        # 第一行起始位置是 len(prefix) + 1 (空格)
        # └─> 符号及其后的空格总计占 4 个字符宽度
        # 因此，补白空格数 = (len(prefix) + 1) - 4
        padding_size = (len(prefix) + 1) - 4
        if padding_size < 0: padding_size = 0
        indent = " " * padding_size
        
        dir_line = Text()
        dir_line.append(indent)
        dir_line.append("└─> ", style="dim")
        dir_line.append(f"{extract_name}/", style="magenta")
        console.print(dir_line)
    
    console.print("=" * 60)

    # 使用 Table 展示统计
    stats_table = Table(title="文件扫描统计", show_header=True, header_style="bold magenta")
    stats_table.add_column("分类", style="cyan")
    stats_table.add_column("数量", justify="right", style="green")
    
    stats_table.add_row("总文件数", str(total_files))
    stats_table.add_row("待处理缩包数", str(len(archives_to_process)))
    stats_table.add_row("待处理普通包", str(normal_archive_count))
    stats_table.add_row("待处理分卷组", str(volume_archive_count))
    stats_table.add_row("已跳过(检测到标记)", str(skipped_count), style="green")
    if ignored_files:
        stats_table.add_row("被忽略的文件", str(sum(ignored_files.values())), style="dim")
        # 计算忽略文件总数
        total_ignored = sum(ignored_files.values())
        stats_table.add_row("被忽略的种类", str(len(ignored_files)))
        # 按数量降序排序
        sorted_ignored = sorted(ignored_files.items(), key=lambda x: x[1], reverse=True)
        for ext, count in sorted_ignored:
            stats_table.add_row(ext, str(count))
    console.print(stats_table)
    

    # --------------------------
    
    if not ask_yes_no("\n[bold]确认开始解压? (y/n): [/]"):
        return

    # 解压逻辑
    num_cpu_cores = os.cpu_count() or 4
    if args.threads:
        max_workers = args.threads
    else:
        max_workers = num_cpu_cores

    console.print(f"\n[bold green]开始解压...[/] (并行线程: {max_workers})\n")

    failed_archives = []
    
    # 使用 Rich Progress
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=40),
        MofNCompleteColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        
        main_task = progress.add_task("[yellow]总体进度", total=len(archives_to_process))
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 存储 future 到 (archive_path, extract_dir) 的映射
            future_to_task = {
                executor.submit(decompress_archive_with_7z, archive_path, extract_dir): (archive_path, extract_dir)
                for archive_path, extract_dir, _, _ in archives_to_process
            }

            for future in concurrent.futures.as_completed(future_to_task):
                archive_path, extract_dir = future_to_task[future]
                try:
                    success = future.result()
                    if not success:
                        failed_archives.append((archive_path, extract_dir))
                except Exception as e:
                    err_msg = Text()
                    err_msg.append("错误: ", style="bold red")
                    err_msg.append(os.path.basename(archive_path), style="red")
                    err_msg.append(f" -> {e}")
                    console.print(err_msg)
                    failed_archives.append((archive_path, extract_dir))
                
                progress.update(main_task, advance=1)

    # 最终报告
    console.print("\n" + "=" * 40)
    success_count = len(archives_to_process) - len(failed_archives)
    
    if len(failed_archives) == 0:
        console.print(f"[bold green]恭喜！所有 {success_count} 个任务均已成功完成 [/]")
    else:
        console.print(f"处理结果: [green]{success_count} 成功[/], [red]{len(failed_archives)} 失败[/]")
        
        # 构建美观的失败详情 Panel
        fail_list = Text()
        fail_list.append("失败的任务:\n")
        for path, _ in sorted(failed_archives):
            fail_list.append(f"{path}\n", style="red")
        console.print(fail_list)

        # 提示是否删除失败任务的临时文件夹
        if ask_yes_no("\n[bold yellow]是否删除上述失败任务留下的 .out_tmp 临时文件夹? (y/n): [/]"):
            print("")
            for _, extract_dir in failed_archives:
                tmp_dir = extract_dir + ".out_tmp"
                if os.path.exists(tmp_dir):
                    try:
                        shutil.rmtree(tmp_dir)
                        console.print(f"[dim]已清理: {os.path.basename(tmp_dir)}[/]")
                    except Exception as e:
                        console.print(f"[red]清理失败 {tmp_dir}: {e}[/]")
    
    console.print("\n" + "=" * 40)

if __name__ == "__main__":
    main()
