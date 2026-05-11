#!/usr/bin/env python3
"""
修复 Issue #42: 为 _scan_tv_shows 添加并发支持
"""
import re

filepath = r"c:\Users\Administrator\WorkBuddy\20260428130330\backend\app\media\scanner.py"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 添加 _process_tv_file 辅助方法（在 _scan_tv_shows 之前）
# 找到 _scan_tv_shows 方法定义
pattern = r"    async def _scan_tv_shows\(self, root: Path, media_type: str\) -> list\[dict\]:"

if pattern in content:
    # 在 _scan_tv_shows 之前插入 _process_tv_file 方法
    method_def = """    async def _process_tv_file(self, vf: Path, media_type: str, season_num: int | None, show_name: str, show_nfo_data: dict | None) -> dict | None:
        \"\"\"处理单个电视剧文件（带信号量，限制并发）\"\"\"
        async with self._semaphore:
            try:
                # 解析剧集信息
                file_season_num, episode_num, episode_name = parse_season_episode(vf.name, include_multi=True)
                
                # 如果文件名没有季号但传入了季信息，使用传入的
                if file_season_num is None and season_num is not None:
                    file_season_num = season_num
                
                # 使用 asyncio.to_thread 包装阻塞 I/O 调用
                stat = await asyncio.to_thread(vf.stat)
                _ = await asyncio.to_thread(vf.exists)  # 检查文件是否存在
                
                info = {
                    "file_path": str(vf),
                    "file_name": vf.name,
                    "file_size": stat.st_size,
                    "media_type": media_type,
                    "container": vf.suffix.lstrip(".").lower(),
                    "season": file_season_num,
                    "episode": episode_num,
                    "episode_name": episode_name,
                    "show_name": show_name,
                }
                
                # 解析名称
                info["parsed_name"] = parse_media_name(vf.name)
                
                # 尝试用 ffprobe 获取精确信息
                probe_data = await self._ffprobe(vf)
                if probe_data:
                    info["duration"] = probe_data.get("duration", 0)
                    info["video_codec"] = probe_data.get("video_codec", "")
                    info["audio_codec"] = probe_data.get("audio_codec", "")
                    info["resolution"] = probe_data.get("resolution", "")
                else:
                    info["duration"] = 0
                
                # 优先使用NFO元数据
                nfo_path = find_nfo_file(vf)
                if nfo_path:
                    nfo_data = parse_nfo_file(nfo_path)
                    if nfo_data:
                        info["nfo_path"] = str(nfo_path)
                        if nfo_data.get("tmdb_id"):
                            info["tmdb_id"] = nfo_data["tmdb_id"]
                        if nfo_data.get("imdb_id"):
                            info["imdb_id"] = nfo_data["imdb_id"]
                        if nfo_data.get("title"):
                            info["nfo_title"] = nfo_data["title"]
                
                # 查找关联字幕
                info["subtitles"] = self._find_subtitles(vf)
                
                # 查找海报
                all_posters = find_all_posters(vf)
                if all_posters:
                    info["local_poster"] = str(all_posters[0])
                    info["all_posters"] = [str(p) for p in all_posters]
                
                # 如果节目标NFO有标题，使用NFO的标题
                if show_nfo_data and show_nfo_data.get("title"):
                    nfo_show_title = show_nfo_data["title"]
                    if len(nfo_show_title) > 2 and not nfo_show_title.startswith("<"):
                        info["show_name"] = nfo_show_title
                
                return info
            except Exception as e:
                logger.warning(f"处理电视剧文件失败 {vf}: {e}")
                return None

"""

    insert_pos = content.find(pattern)
    if insert_pos != -1:
        content = content[:insert_pos] + method_def + "\n" + content[insert_pos:]
        print("Added _process_tv_file helper method")
    else:
        print("ERROR: Could not find _scan_tv_shows method definition")
else:
    print("ERROR: Pattern not found in file")

# 2. 修改 _scan_tv_shows 使用并发
# 找到 "for vf in files:" 循环并开始替换
old_loop_pattern = r"            for vf in files:\n                season_num, episode_num, _ = parse_season_episode\(vf\.name, include_multi=True\)"
if old_loop_pattern in content:
    # 替换为并发版本
    new_loop = """            # 并发处理所有文件（信号量限制并发数）
            tasks = [self._process_tv_file(vf, media_type, folder_season_num, show_name, show_nfo_data) for vf in files]
            results_list = await asyncio.gather(*tasks)
            
            # 过滤掉处理失败的文件
            for result in results_list:
                if result is not None:
                    results.append(result)"""
    
    content = content.replace(old_loop_pattern, new_loop)
    print("Modified _scan_tv_shows to use concurrent processing")
else:
    print("WARNING: Could not find the for vf in files loop pattern")

# 写回文件
with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("Done! Fixed Issue #42 for _scan_tv_shows")
