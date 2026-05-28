#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统计season文件夹中所有HTML文件的单词出现次数
"""

import os
import re
from collections import Counter
from html.parser import HTMLParser


class HTMLTextExtractor(HTMLParser):
    """HTML解析器，用于提取纯文本内容"""
    
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.in_script = False
        self.in_style = False
        
    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'script':
            self.in_script = True
        elif tag.lower() == 'style':
            self.in_style = True
            
    def handle_endtag(self, tag):
        if tag.lower() == 'script':
            self.in_script = False
        elif tag.lower() == 'style':
            self.in_style = False
            
    def handle_data(self, data):
        # 只收集非脚本和非样式标签中的文本
        if not self.in_script and not self.in_style:
            self.text_parts.append(data)
    
    def get_text(self):
        return ' '.join(self.text_parts)


def extract_text_from_html(file_path):
    """从HTML文件中提取纯文本"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        parser = HTMLTextExtractor()
        parser.feed(content)
        return parser.get_text()
    except Exception as e:
        print(f"读取文件 {file_path} 时出错: {e}")
        return ""


def count_words_in_directory(directory_path):
    """统计目录下所有HTML文件的单词出现次数"""
    
    # 获取所有HTML文件
    html_files = [f for f in os.listdir(directory_path) if f.endswith('.html')]
    
    if not html_files:
        print(f"在 {directory_path} 中没有找到HTML文件")
        return None
    
    print(f"找到 {len(html_files)} 个HTML文件")
    
    # 存储所有单词
    all_words = []
    
    # 逐个处理文件
    for filename in sorted(html_files):
        file_path = os.path.join(directory_path, filename)
        text = extract_text_from_html(file_path)
        
        # 提取单词（只保留字母和数字组成的单词）
        words = re.findall(r"[a-zA-Z0-9']+", text.lower())
        all_words.extend(words)
        
        print(f"已处理: {filename}")
    
    print("\n正在统计单词...")
    
    # 统计单词频率
    word_counter = Counter(all_words)
    
    return word_counter


def save_results(word_counter, output_file='word_count_results.txt'):
    """将结果保存到文件"""
    
    # 按出现次数排序
    sorted_words = word_counter.most_common()
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"总单词数: {sum(word_counter.values())}\n")
        f.write(f"不同单词数: {len(word_counter)}\n")
        f.write("=" * 60 + "\n\n")
        
        f.write(f"{'排名':<8} {'单词':<30} {'出现次数':<12}\n")
        f.write("-" * 60 + "\n")
        
        for rank, (word, count) in enumerate(sorted_words, 1):
            f.write(f"{rank:<8} {word:<30} {count:<12}\n")
    
    print(f"\n结果已保存到: {output_file}")


def display_top_words(word_counter, top_n=50):
    """显示出现频率最高的前N个单词"""
    
    print(f"\n{'='*60}")
    print(f"出现频率最高的前 {top_n} 个单词:")
    print(f"{'='*60}\n")
    
    print(f"{'排名':<8} {'单词':<30} {'出现次数':<12}")
    print("-" * 60)
    
    for rank, (word, count) in enumerate(word_counter.most_common(top_n), 1):
        print(f"{rank:<8} {word:<30} {count:<12}")


def main():
    # 设置目录路径
    directory_path = r"C:\Users\ICN00069\Downloads\scripts\season"
    
    # 检查目录是否存在
    if not os.path.exists(directory_path):
        print(f"目录不存在: {directory_path}")
        return
    
    print("开始统计单词...")
    print("=" * 60)
    
    # 统计单词
    word_counter = count_words_in_directory(directory_path)
    
    if word_counter is None:
        return
    
    print("\n" + "=" * 60)
    print(f"统计完成!")
    print(f"总单词数: {sum(word_counter.values())}")
    print(f"不同单词数: {len(word_counter)}")
    print("=" * 60)
    
    # 显示前50个高频词
    display_top_words(word_counter, 50)
    
    # 保存结果到文件
    save_results(word_counter)
    
    print("\n程序执行完毕!")


if __name__ == "__main__":
    main()
