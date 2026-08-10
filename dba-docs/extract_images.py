"""
extract_images.py — Extracts base64 images from word2md.com markdown files and auto-formats code blocks.
"""

import re, os, sys, base64
from pathlib import Path

def slugify(name: str) -> str:
    name = Path(name).stem
    name = re.sub(r'^\d+\.\s*', '', name)
    name = name.lower().strip()
    name = re.sub(r'[^a-z0-9]+', '-', name).strip('-')
    return name

def format_markdown(content: str) -> str:
    content = re.sub(r'<sub>(.*?)</sub>', r'\1', content)
    lines = content.split('\n')
    new_lines = []
    in_code_block = False
    
    for line in lines:
        test_line = line.replace('&nbsp;', '').strip()
        test_line = test_line.lstrip('_*"').rstrip('_*"')
        
        is_prompt = (
            test_line.startswith('SQL>') or 
            test_line.startswith('RMAN>') or 
            test_line.startswith('ORA-') or 
            test_line.startswith('error: ORA-') or
            test_line.startswith('SELECT ') or
            test_line.startswith('FROM ') or
            test_line.startswith('WHERE ') or
            test_line.startswith('ORDER BY ') or
            test_line.startswith('GROUP BY ') or
            test_line.startswith('expdp ') or
            test_line.startswith('impdp ') or
            test_line.startswith('Export>') or
            test_line.startswith('Import>')
        )
        
        is_normal_text = (
            test_line.startswith('#') or
            test_line.startswith('- ') or
            test_line.startswith('Step') or
            test_line.startswith('Note') or
            test_line.startswith('Conclusion') or
            test_line.startswith('Scenario:') or
            test_line.startswith('Solution:') or
            test_line.startswith('|') or
            '![image' in line
        )
        
        if not in_code_block and is_prompt:
            # Determine block type
            lang = "bash" if test_line.startswith('expdp') or test_line.startswith('impdp') else "sql"
            new_lines.append(f'```{lang}')
            clean_line = line.replace('&nbsp;', '').strip()
            clean_line = re.sub(r'^[_*"]+', '', clean_line)
            clean_line = re.sub(r'[_*"]+$', '', clean_line)
            clean_line = clean_line.replace('**SQL>**', 'SQL> ').replace('**RMAN>**', 'RMAN> ')
            new_lines.append(clean_line)
            in_code_block = True
            
        elif in_code_block:
            if is_normal_text:
                while new_lines and new_lines[-1].strip() == '':
                    new_lines.pop()
                new_lines.append('```')
                new_lines.append('')
                new_lines.append(line)
                in_code_block = False
            else:
                clean_line = line.replace('&nbsp;', '').strip()
                if clean_line:
                    clean_line = re.sub(r'^[_*"]+', '', clean_line)
                    clean_line = re.sub(r'[_*"]+$', '', clean_line)
                    clean_line = clean_line.replace('**SQL>**', 'SQL> ').replace('**RMAN>**', 'RMAN> ')
                    new_lines.append(clean_line)
                else:
                    if new_lines and new_lines[-1].strip() != '':
                        new_lines.append('')
        else:
            new_lines.append(line)
            
    if in_code_block:
        while new_lines and new_lines[-1].strip() == '':
            new_lines.pop()
        new_lines.append('```')
        
    return '\n'.join(new_lines)

def extract_images(md_file: str) -> None:
    md_path = Path(md_file).resolve()
    if not md_path.exists():
        print(f"Error: {md_path} not found"); sys.exit(1)

    print(f"Processing: {md_path.name}")

    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    content = format_markdown(content)
    lines = content.split('\n')

    doc_slug = slugify(md_path.name)
    images_dir = md_path.parent / "images" / doc_slug
    rel_dir = os.path.relpath(images_dir, md_path.parent).replace('\\', '/')

    count = 0
    new_lines = []
    marker_start = '](data:image/'
    
    for line in lines:
        if marker_start not in line:
            new_lines.append(line)
            continue
        result = line
        while marker_start in result:
            img_start = result.find('![')
            if img_start == -1: break
            alt_end = result.find('](data:image/', img_start)
            if alt_end == -1: break
            alt_text = result[img_start+2:alt_end]
            fmt_start = alt_end + len('](data:image/')
            fmt_end = result.find(';base64,', fmt_start)
            if fmt_end == -1: break
            img_format = result[fmt_start:fmt_end]
            data_start = fmt_end + len(';base64,')
            data_end = result.find(')', data_start)
            if data_end == -1: break
            b64_data = result[data_start:data_end].strip()
            count += 1
            ext_map = {'png': 'png', 'jpeg': 'jpg', 'jpg': 'jpg', 'gif': 'gif', 'webp': 'webp'}
            ext = ext_map.get(img_format, 'png')
            fname = re.sub(r'[^a-zA-Z0-9_-]', '-', alt_text).strip('-')[:60] if alt_text and alt_text != 'image' else f"image-{count:03d}"
            fname = f"{fname}.{ext}"
            images_dir.mkdir(parents=True, exist_ok=True)
            img_path = images_dir / fname
            try:
                img_bytes = base64.b64decode(b64_data)
                with open(img_path, 'wb') as f:
                    f.write(img_bytes)
                print(f"  [{count}] Extracted: {fname} ({len(img_bytes):,} bytes)")
            except Exception as e:
                print(f"  [{count}] Warning: Failed - {e}")
            old_chunk = result[img_start:data_end+1]
            new_chunk = f"![{alt_text}]({rel_dir}/{fname})"
            result = result[:img_start] + new_chunk + result[data_end+1:]
        new_lines.append(result)

    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))

    if count == 0:
        print("  No base64 images found.")
        print(f"\n  Done! Markdown formatting applied.")
    else:
        print(f"\n  Done! Extracted {count} image(s) and applied markdown formatting.")
        print(f"  Images saved to: {images_dir}")
        print(f"  To change an image: replace the .png file in that folder")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python extract_images.py "path/to/file.md"')
        sys.exit(1)
    extract_images(sys.argv[1])
