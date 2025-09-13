# 播客播放器使用说明 / Podcast Player Instructions

## 收听链接：`https://zhuoqilang.github.io/podcast-player/`

## 播放器核心理念 / Player Core Concept
- 本播放器的主要特点是首先随机播放音频内容，当您对一条音频感兴趣（例如完播或选择根据此条推荐），系统会自动生成与之最相关的播放列表。
- 我们认为这是语言类播客的最佳使用方式。
- The main feature of this player is that it first plays audio content randomly. When you are interested in an audio (such as finishing playback or choosing to recommend based on this one), the system will automatically generate a playlist most relevant to it.
- We believe this is the best way to use language podcasts.

## 功能概述 / Features
- 支持随机播放和推荐模式 / Support random play and recommendation mode
- 触摸区域支持划屏操作 / Touch area supports swipe gestures
- 提供按钮点击和键盘控制 / Provide button click and keyboard control
- 支持本地存储数据文件 / Support local storage of data files

## 使用方法 / How to Use

### 基本操作 / Basic Operations
- **播放/暂停**：点击中央播放按钮或按空格键/回车键 / **Play/Pause**: Click center play button or press Space/Enter key
- **上一条**：左滑、点击左箭头按钮或按左箭头键 / **Previous**: Swipe left, click left arrow button or press ArrowLeft key
- **下一条**：右滑、点击右箭头按钮或按右箭头键 / **Next**: Swipe right, click right arrow button or press ArrowRight key
- **随机模式**：上滑、点击"随机播放"按钮或按上箭头键 / **Random Mode**: Swipe up, click "Random Play" button or press ArrowUp key
- **推荐模式**：下滑、点击"推荐模式"按钮或按下箭头键 / **Recommendation Mode**: Swipe down, click "Recommendation Mode" button or press ArrowDown key

### 文件加载 / File Loading
播放器支持三种方式加载数据文件：/ The player supports three ways to load data files:
1. 自动从本地存储加载（如果有） / Automatically load from local storage (if available)
2. 自动从同一目录加载指定的JSON文件 / Automatically load specified JSON files from the same directory
3. 手动选择三个JSON文件：单集数据、节点文件和边文件 / Manually select three JSON files: episodes data, nodes file and edges file

## 推荐系统 / Recommendation System
- 基于节目标注内容提取关键词 / Extract keywords based on episode annotations
- 利用节点关系扩展相关关键词 / Expand related keywords using node relationships
- 根据话题词匹配度计算推荐分数 / Calculate recommendation scores based on topic word matching


