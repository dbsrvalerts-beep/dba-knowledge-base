"""
extract_images.py — Extracts base64 images from word2md.com markdown files.

Usage:  python extract_images.py "docs/ORACLE/2. Cloud Database Objective.md"

Creates:
    docs/ORACLE/images/<doc-slug>/image-001.png
    docs/ORACLE/images/<doc-slug>/image-002.png
    ...

Updates the .md file to use relative paths instead of base64 data URIs.
"""

import re, os, sys, base64
from pathlib import Path


def slugify(name: str) -> str:
    name = Path(name).stem
    name = re.sub(r'^\d+\.\s*', '', name)
    name = name.lower().strip()
    name = re.sub(r'[^a-z0-9]+', '-', name).strip('-')
    return name


def extract_images(md_file: str) -> None:
    md_path = Path(md_file).resolve()
    if not md_path.exists():
        print(f"Error: {md_path} not found"); sys.exit(1)

    print(f"Processing: {md_path.name}")

    with open(md_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    doc_slug = slugify(md_path.name)
    images_dir = md_path.parent / "images" / doc_slug
    rel_dir = os.path.relpath(images_dir, md_path.parent).replace('\\', '/')

    count = 0
    new_lines = []

    # Simpler approach: find base64 image markers per line
    marker_start = '](data:image/'
    for line in lines:
        if marker_start not in line:
            new_lines.append(line)
            continue

        # Process line with base64 image(s)
        result = line
        # Find all ![...](data:image/...;base64,...) in this line
        while marker_start in result:
            # Find the alt text
            img_start = result.find('![')
            if img_start == -1:
                break
            alt_end = result.find('](data:image/', img_start)
            if alt_end == -1:
                break
            alt_text = result[img_start+2:alt_end]

            # Find image format
            fmt_start = alt_end + len('](data:image/')
            fmt_end = result.find(';base64,', fmt_start)
            if fmt_end == -1:
                break
            img_format = result[fmt_start:fmt_end]

            # Find base64 data (ends with closing paren)
            data_start = fmt_end + len(';base64,')
            data_end = result.find(')', data_start)
            if data_end == -1:
                break
            b64_data = result[data_start:data_end].strip()

            count += 1

            # Determine extension
            ext_map = {'png': 'png', 'jpeg': 'jpg', 'jpg': 'jpg', 'gif': 'gif', 'webp': 'webp'}
            ext = ext_map.get(img_format, 'png')

            # Create filename from alt text
            if alt_text and alt_text != 'image':
                fname = re.sub(r'[^a-zA-Z0-9_-]', '-', alt_text).strip('-')[:60]
            else:
                fname = f"image-{count:03d}"
            fname = f"{fname}.{ext}"

            # Save image
            images_dir.mkdir(parents=True, exist_ok=True)
            img_path = images_dir / fname
            try:
                img_bytes = base64.b64decode(b64_data)
                with open(img_path, 'wb') as f:
                    f.write(img_bytes)
                print(f"  [{count}] Extracted: {fname} ({len(img_bytes):,} bytes)")
            except Exception as e:
                print(f"  [{count}] Warning: Failed - {e}")

            # Replace in result
            old_chunk = result[img_start:data_end+1]
            new_chunk = f"![{alt_text}]({rel_dir}/{fname})"
            result = result[:img_start] + new_chunk + result[data_end+1:]

        new_lines.append(result)

    if count == 0:
        print("  No base64 images found.")
        return

    # Write updated markdown
    with open(md_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    print(f"\n  Done! Extracted {count} image(s)")
    print(f"  Images saved to: {images_dir}")
    print(f"  To change an image: replace the .png file in that folder")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python extract_images.py "path/to/file.md"')
        sys.exit(1)
    extract_images(sys.argv[1])
