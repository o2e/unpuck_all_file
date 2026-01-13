import os
import shutil
import argparse
import secrets
from rich.console import Console
from rich.text import Text

console = Console()

def generate_tree_string(path, prefix="", is_top=True):
    """
    递归生成文件夹的可视化树结构字符串，包含所有隐藏文件。
    """
    tree_str = ""
    if is_top:
        tree_str += f"{os.path.basename(path.rstrip(os.sep))}/\n"

    try:
        items = sorted(os.listdir(path))
    except:
        return ""

    for i, item in enumerate(items):
        is_last = (i == len(items) - 1)
        connector = "└── " if is_last else "├── "
        tree_str += f"{prefix}{connector}{item}\n"
        
        full_path = os.path.join(path, item)
        if os.path.isdir(full_path):
            new_prefix = prefix + ("    " if is_last else "│   ")
            tree_str += generate_tree_string(full_path, new_prefix, is_top=False)
    return tree_str

def flatten_project_folder(project_path):
    """
    对项目文件夹进行深度平铺。
    返回平铺的层数。
    """
    project_path = project_path.rstrip(os.sep)
    project_name = os.path.basename(project_path)
    info_file_name = f"{project_name}.txt"
    info_file_path = os.path.join(project_path, info_file_name)
    
    # 1. 生成原地结构存证
    try:
        if not os.path.exists(info_file_path):
            tree_data = generate_tree_string(project_path)
            header = f"Original Archive Structure: {project_name}\n" + "-"*40 + "\n"
            with open(info_file_path, 'w', encoding='utf-8') as f:
                f.write(header + tree_data)
    except:
        pass

    # 2. 递归平铺逻辑
    junk_names = {'.DS_Store', '.zipp_done', '__MACOSX', '__thumb', 'Thumbs.db', info_file_name}
    # 深度色阶效果：青 -> 绿 -> 金 -> 粉 -> 蓝
    LEVEL_COLORS = ["cyan", "spring_green1", "gold1", "hot_pink", "royal_blue1"]
    total_flattened = 0
    path_segments = [project_name] # 用于记录整条挖掘路径
    
    while True:
        try:
            current_items = [i for i in os.listdir(project_path) if i not in junk_names and not i.startswith('.')]
            
            if len(current_items) == 1:
                sub_name = current_items[0]
                sub_path = os.path.join(project_path, sub_name)
                
                if os.path.isdir(sub_path):
                    # 记录这一层
                    path_segments.append(sub_name)
                    
                    # 临时重命名以规避同名套娃冲突
                    temp_name = f"{sub_name}_flat_tmp_{secrets.token_hex(4)}"
                    temp_path = os.path.join(project_path, temp_name)
                    os.rename(sub_path, temp_path)
                    
                    # 提取内容
                    sub_contents = os.listdir(temp_path)
                    for item in sub_contents:
                        src = os.path.join(temp_path, item)
                        dst = os.path.join(project_path, item)
                        if not os.path.exists(dst):
                            shutil.move(src, dst)
                        else:
                            console.print(f"    [red]![/] 冲突: [dim]{item}[/] 已存在，跳过。")
                    
                    # 安全删除校验
                    remaining = [i for i in os.listdir(temp_path) if i not in junk_names and not i.startswith('.')]
                    if not remaining:
                        shutil.rmtree(temp_path)
                        total_flattened += 1
                        continue
                    else:
                        os.rename(temp_path, sub_path)
                        console.print(f"    [yellow]i[/] 冲突残留，停止展开。")
                        break
                else:
                    break
            else:
                break
        except Exception as e:
            console.print(f"  [red]![/] 处理异常: {e}")
            break
            
    if total_flattened > 0:
        # 整理完成后，只打印一条汇总的彩色长路径
        msg = Text()
        msg.append("整理完毕: ", style="bold yellow")
        for i, seg in enumerate(path_segments):
            if i > 0:
                msg.append("/", style="white")
            if i == 0:
                msg.append(seg, style="grey50")
            else:
                color = LEVEL_COLORS[min(i - 1, len(LEVEL_COLORS) - 1)]
                msg.append(seg, style=color)
        console.print(msg)
            
    return total_flattened

def main():
    parser = argparse.ArgumentParser(description="工业级项目文件夹深度展开整理工具。")
    parser.add_argument("path", help="目标父目录路径")
    args = parser.parse_args()
    
    root_dir = os.path.abspath(args.path)
    if not os.path.isdir(root_dir):
        console.print(f"[bold red]错误:[/] 目录 '{root_dir}' 不存在。")
        return

    console.print(f"\n[bold green]开始深度整理目录:[/] [cyan]{root_dir}[/]\n")
    
    try:
        items = sorted([d for d in os.listdir(root_dir) 
                        if os.path.isdir(os.path.join(root_dir, d)) and not d.startswith('.')])
    except Exception as e:
        console.print(f"[bold red]错误:[/] 无法读取目录: {e}")
        return

    stats_flattened = 0
    affected_projects = []
    untouched_projects = []
    
    for p_name in items:
        p_path = os.path.join(root_dir, p_name)
        ops = flatten_project_folder(p_path)
        if ops > 0:
            stats_flattened += ops
            affected_projects.append(p_name)
        else:
            untouched_projects.append(p_name)

    if untouched_projects:
        console.print(f"\n[bold blue]完美保持原样 (多文件并存，无需整理):[/]")
        for p in untouched_projects:
            item_text = Text()
            item_text.append("  - ", style="dim")
            item_text.append(p, style="dim")
            console.print(item_text)

    # 最终报告
    console.print("\n" + "="*40)
    console.print(f"[bold green]处理完成报告[/]")
    console.print(f"  · 扫描项目总数:   [bold cyan]{len(items)}[/]")
    console.print(f"  · 成功展开层数:   [bold green]{stats_flattened}[/]")
    console.print(f"  · 受影响项目数:   [bold yellow]{len(affected_projects)}[/]")
    console.print(f"  · 完美无需整理:   [bold blue]{len(untouched_projects)}[/]")
    console.print("="*40 + "\n")

if __name__ == "__main__":
    main()
