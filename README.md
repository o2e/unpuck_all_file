# batch_unpuck

> support hybrid .rar, .zip, .7z, .zip.001, .7z.001, .rar.001, .part1.rar, .part01.rar, .part001.rar, .z01, .001

[English Version](#batch_unpuck_en)

### 📦 批量解压Python脚本(支持各种格式压缩包一键扫描解压，truenas可用)

### 本套装包含两个核心脚本，旨在提供从压缩包提取到目录结构优化的全流程自动化方案，兼顾高性能与数据安全性。仅依赖`rich`,`7z`库
---

## 🚀 1. `unpack.py` - 并行可靠解压
基于 `7z` 引擎的高性能解压工具，通过“预处理-解压-原子交付”流程确保资源库的完整性。
<img width="1108" height="488" alt="image" src="https://github.com/user-attachments/assets/ca292327-16f2-40be-9cb9-2a82ba64b727" />

### 🌟 核心特性
- **双阶段可靠解压**：
    - **临时缓冲区**：所有文件首先解压至 `xxx.out_tmp` 目录。
    - **成功签名**：解压 100% 成功后，写入 `.zipp_done` 标记并执行原子级目录重命名。
- **智能分卷全对齐**：通过多套正则算法，自动关联并起始解压 `.001`、`.part1.rar`、`.z01` 等数多种分卷格式。
- **冲突预防策略**：解压前自动清理同名残余文件(如输出目录有同名文件请重命名避免被误删)，确保交付环境绝对纯净。
- **实时监控界面**：使用 `rich` 渲染总体任务进度条与详细文件扫描统计表。
- **断点续传支持**：自动跳过包含 `.zipp_done` 标记的已完成任务。

### 🛠️ 使用方法
```bash
python3 unpack.py <输入目录> [-o <输出目录>] [-t <并行线程数>]
```
<img width="572" height="376" alt="image" src="https://github.com/user-attachments/assets/6c1fcfb1-1301-482d-b079-3ef182897f0d" />


---

## 🪄 2. `flatten_dir.py` - 项目级深度平铺整理
专门解决解压后产生的“一层套一层”文件夹结构，通过向上提取文件实现目录扁平化。

<img width="776" height="238" alt="image" src="https://github.com/user-attachments/assets/9a0f71df-20c1-442f-8090-17aa515ed38f" />

### 🌟 核心特性
- **项目结构快照**：在执行任何整理操作前，于各项目内部生成 `[项目名].txt`，记录含隐藏文件的全量原始树状结构。
- **深度递归收敛**：只要项目目录下仅存在唯一的可见子文件夹（无其他文件并存），脚本将自动进入并将内容递归上提。
- **两阶段安全移动**：
    - **临时空间规避**：将待处理子文件夹重命名为带有随机后缀的临时名，以彻底释放原路径占用。
    - **零损校验**：清理子目录前进行可见项盘点，如因文件名重复导致未能移出，则恢复目录原状，绝不丢失数据。
- **高阶视觉反馈**：采用多色阶路径显示（父目录置灰，正在提取的子目录按深度彩色高亮）。
- **无损优先**：所有的平铺操作均附带冲突检测，如遇同名冲突将保留原始嵌套结构。
- **可逆性**：自带的 `.txt` 文件提供了最原始的项目结构参照。
  
### 🛠️ 使用方法
```bash
python3 flatten_dir.py <目标目录>
```

# ⚠️ 使用时尽量将目标文件夹，输出路径，另存为副本在单独的文件夹环境中处理以免出现bug导致数据丢失，使用前复制少量需要处理的文件单独测试脚本是否符合预期再正式使用。

# batch_unpuck_en

### 📦 Batch Decompression Python Scripts (Supports one-click scanning and decompression for various archive formats, compatible with TrueNAS)

### This toolkit contains two core scripts designed to provide an automated end-to-end solution from archive extraction to directory structure optimization, balancing high performance with data safety. Dependencies: `rich`, `7z`.
---

## 🚀 1. `unpack.py` - Parallel Reliable Decompression
A high-performance decompression tool based on the `7z` engine, ensuring library integrity through a "Pre-process -> Extract -> Atomic Delivery" workflow.
<img width="1108" height="488" alt="image" src="https://github.com/user-attachments/assets/ca292327-16f2-40be-9cb9-2a82ba64b727" />

### 🌟 Key Features
- **Two-Stage Reliable Decompression**:
    - **Temporary Buffer**: All files are first extracted to a `xxx.out_tmp` directory.
    - **Success Signature**: After 100% successful extraction, a `.zipp_done` marker is written, followed by an atomic directory rename.
- **Smart Multi-Volume Alignment**: Uses multiple regex sets to automatically associate and initiate extraction for dozens of multi-volume formats like `.001`, `.part1.rar`, `.z01`, etc.
- **Conflict Prevention Strategy**: Automatically cleans up residual files with the same name before extraction (please rename existing files in the output directory to avoid accidental deletion), ensuring a clean delivery environment.
- **Real-time Monitoring**: Uses `rich` to render an overall progress bar and detailed file scanning statistics.
- **Resume Support**: Automatically skips tasks that already contain the `.zipp_done` marker.

### 🛠️ Usage
```bash
python3 unpack.py <input_directory> [-o <output_directory>] [-t <thread_count>]
```
<img width="572" height="376" alt="image" src="https://github.com/user-attachments/assets/6c1fcfb1-1301-482d-b079-3ef182897f0d" />


---

## 🪄 2. `flatten_dir.py` - Project-Level Deep Flattening
Specifically solves the "nested folder" issue (folders inside folders with the same name) created after decompression by lifting files upwards to flatten the directory.

<img width="776" height="238" alt="image" src="https://github.com/user-attachments/assets/9a0f71df-20c1-442f-8090-17aa515ed38f" />

### 🌟 Key Features
- **Project Structure Snapshot**: Generates a `[ProjectName].txt` inside each project before any operation, recording the full original tree structure including hidden files.
- **Deep Recursive Convergence**: As long as a project directory contains only a single visible subfolder (with no other files present), the script will automatically dive in and lift the contents recursively until multiple items are encountered.
- **Two-Stage Secure Move**:
    - **Temporary Path Evasion**: Renames target subfolders with a random suffix during processing to completely release the original path occupation.
    - **Zero-Loss Verification**: Perfroms a visible item count before deleting the sub-directory; if any items remain due to name conflicts, the original structure is restored to prevent data loss.
- **High-Level Visual Feedback**: Features multi-color path displays (parent directories are greyed out, while the sub-directory being extracted is highlighted in dynamic colors based on depth).
- **Lossless Priority**: All flattening operations include conflict detection; if a name collision occurs, the original nested structure is preserved.
- **Reversibility**: The included `.txt` file provides a reference to the original physical layout of the project.
  
### 🛠️ Usage
```bash
python3 flatten_dir.py <target_directory>
```

# ⚠️ WARNING: When using these scripts, perform operations on copies in a separate environment to avoid data loss due to unexpected bugs. Always test with a small number of files to ensure the script meets your expectations before full production use.

