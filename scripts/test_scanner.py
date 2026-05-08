"""测试媒体库扫描功能"""
import sys
import asyncio
import json
from pathlib import Path

# 添加后端路径
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.media.scanner import (
    MediaScanner,
    is_season_folder,
    parse_season_folder,
    parse_season_episode,
    parse_media_name,
    is_video_file,
    _find_nfo_file,  # 私有函数测试
    find_nfo_file,
)
from app.media.scanner import parse_nfo_file


def test_scanner():
    """测试扫描器功能"""
    scanner = MediaScanner()

    # 测试目录
    test_dir = Path("F:/downloads/综艺")
    print(f"=== 测试目录: {test_dir} ===")
    print(f"目录存在: {test_dir.exists()}")
    print(f"是目录: {test_dir.is_dir()}")

    # 列出目录内容
    print("\n=== 目录内容 ===")
    try:
        for entry in test_dir.iterdir():
            print(f"  {entry.name} ({'目录' if entry.is_dir() else '文件'})")
    except Exception as e:
        print(f"  列出目录失败: {e}")

    # 测试 is_season_folder
    print("\n=== 测试 is_season_folder ===")
    test_folders = [
        "Season 6",
        "Season 06",
        "Season 1-5",
        "S01",
        "第1季",
        "第6季",
        "哈哈哈哈哈 (2020)",
        "Season 6",
    ]
    for folder in test_folders:
        result = is_season_folder(folder)
        print(f"  is_season_folder('{folder}') = {result}")

    # 测试 parse_season_folder
    print("\n=== 测试 parse_season_folder ===")
    for folder in test_folders:
        result = parse_season_folder(folder)
        print(f"  parse_season_folder('{folder}') = {result}")

    # 测试 parse_season_episode
    print("\n=== 测试 parse_season_episode ===")
    test_files = [
        "哈哈哈哈哈 - S06E01 - 第 1 集.mkv",
        "哈哈哈哈哈 - S06E02 - 第 2 集.mkv",
        "哈哈哈哈哈 - S06E01 - 第 1 集.nfo",
        "test.S06E01.mkv",
        "test.1x01.mkv",
    ]
    for f in test_files:
        result = parse_season_episode(f, include_multi=True)
        print(f"  parse_season_episode('{f}') = {result}")

    # 测试 parse_media_name
    print("\n=== 测试 parse_media_name ===")
    for f in test_files:
        result = parse_media_name(f)
        print(f"  parse_media_name('{f}') = {result}")

    # 测试 is_video_file
    print("\n=== 测试 is_video_file ===")
    test_exts = [".mkv", ".mp4", ".avi", ".nfo", ".jpg", ".srt"]
    for ext in test_exts:
        print(f"  is_video_file('test{ext}') = {is_video_file(Path(f'test{ext}'))}")

    # 测试 find_nfo_file
    print("\n=== 测试 find_nfo_file ===")
    test_video = Path("F:/downloads/综艺/哈哈哈哈哈 (2020)/Season 6/哈哈哈哈哈 - S06E01 - 第 1 集.mkv")
    if test_video.exists():
        nfo_path = find_nfo_file(test_video)
        print(f"  find_nfo_file('{test_video.name}') = {nfo_path}")
        if nfo_path and nfo_path.exists():
            nfo_data = parse_nfo_file(nfo_path)
            print(f"  parse_nfo_file 结果: {json.dumps(nfo_data, ensure_ascii=False, indent=2)}")
    else:
        print(f"  测试文件不存在: {test_video}")

    # 递归查找视频文件
    print("\n=== 递归查找视频文件 ===")
    try:
        video_files = list(test_dir.rglob("*.mkv"))
        print(f"  找到 {len(video_files)} 个 .mkv 文件:")
        for vf in video_files[:5]:  # 只显示前5个
            rel_path = vf.relative_to(test_dir)
            print(f"    {rel_path}")
        if len(video_files) > 5:
            print(f"    ... 还有 {len(video_files) - 5} 个文件")
    except Exception as e:
        print(f"  递归查找失败: {e}")

    # 测试实际的 scan_directory
    print("\n=== 测试 scan_directory (剧集模式) ===")
    async def run_scan():
        try:
            results = await scanner.scan_directory(str(test_dir), "tv")
            print(f"  扫描结果: 找到 {len(results)} 个媒体文件")
            if results:
                print("\n  前3个结果:")
                for r in results[:3]:
                    print(f"    文件: {r.get('file_name')}")
                    print(f"    类型: {r.get('media_type')}")
                    print(f"    解析名称: {r.get('parsed_name')}")
                    print(f"    季号: {r.get('season_number')}")
                    print(f"    集号: {r.get('episode_number')}")
                    print(f"    NFO路径: {r.get('nfo_path', '无')}")
                    print(f"    TMDB ID: {r.get('tmdb_id', '无')}")
                    print()
            return results
        except Exception as e:
            print(f"  扫描失败: {e}")
            import traceback
            traceback.print_exc()
            return []

    results = asyncio.run(run_scan())


if __name__ == "__main__":
    test_scanner()
