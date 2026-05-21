#!/usr/bin/env python3
"""
LINE アルバムからダウンロードした写真・動画に exiftool で撮影日時を埋め込むスクリプト。

使い方:
    python embed_timestamps.py <csv_path> <album_dir>

引数:
    csv_path   タイムスタンプ情報が入った CSV ファイルのパス
    album_dir  LINE アルバムをダウンロードしたディレクトリのパス
"""

import argparse
import csv
import re
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path


SOFTWARE = f"line-timestamp-restore 0.1.0"
JST = timezone(timedelta(hours=9))


def extract_file_index(path: Path) -> int:
    """ファイル名末尾の番号を取得する (例: LINE_ALBUM_..._42.jpg -> 42)"""
    m = re.search(r'_(\d+)\.\w+$', path.name)
    if m:
        return int(m.group(1))
    raise ValueError(f"ファイル名からインデックスを取得できません: {path.name}")


def parse_timestamp(ts: str) -> datetime:
    """'YYYY/MM/DD HH:MM' を JST aware な datetime に変換する"""
    return datetime.strptime(ts.strip(), '%Y/%m/%d %H:%M').replace(tzinfo=JST)


def fmt_local(dt: datetime) -> str:
    """EXIF ローカル時刻形式: 'YYYY:MM:DD HH:MM:SS' (tzなし)"""
    return dt.strftime('%Y:%m:%d %H:%M:%S')


def fmt_utc(dt: datetime) -> str:
    """QuickTime UTC 形式: 'YYYY:MM:DD HH:MM:SS' (tzなし、UTC値)"""
    return dt.astimezone(timezone.utc).strftime('%Y:%m:%d %H:%M:%S')


def fmt_tz(dt: datetime) -> str:
    """タイムゾーン付き形式: 'YYYY:MM:DD HH:MM:SS+09:00'"""
    return dt.strftime('%Y:%m:%d %H:%M:%S%z').replace('+0900', '+09:00')


def apply_exiftool_jpg(path: Path, dt: datetime) -> bool:
    local = fmt_local(dt)
    tz_str = fmt_tz(dt)
    cmd = [
        'exiftool', '-overwrite_original',
        f'-DateTimeOriginal={local}',
        f'-CreateDate={local}',
        f'-ModifyDate={local}',
        '-OffsetTime=+09:00',
        '-OffsetTimeOriginal=+09:00',
        '-OffsetTimeDigitized=+09:00',
        f'-FileModifyDate={tz_str}',
        f'-Software={SOFTWARE}',
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERROR [{path.name}]: {result.stderr.strip()}", file=sys.stderr)
        return False
    return True


def apply_exiftool_mp4(path: Path, dt: datetime) -> bool:
    utc = fmt_utc(dt)
    tz_str = fmt_tz(dt)
    cmd = [
        'exiftool', '-overwrite_original',
        f'-CreateDate={utc}',
        f'-ModifyDate={utc}',
        f'-TrackCreateDate={utc}',
        f'-TrackModifyDate={utc}',
        f'-MediaCreateDate={utc}',
        f'-MediaModifyDate={utc}',
        f'-XMP:CreateDate={tz_str}',
        f'-XMP:ModifyDate={tz_str}',
        f'-FileModifyDate={tz_str}',
        f'-XMP:CreatorTool={SOFTWARE}',
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERROR [{path.name}]: {result.stderr.strip()}", file=sys.stderr)
        return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description='LINE アルバム画像・動画に exiftool で撮影日時を埋め込む'
    )
    parser.add_argument('csv_path', help='タイムスタンプ CSV ファイルのパス')
    parser.add_argument('album_dir', help='LINE アルバムをダウンロードしたディレクトリのパス')
    args = parser.parse_args()

    csv_path = Path(args.csv_path)
    album_dir = Path(args.album_dir)

    if not csv_path.exists():
        print(f"Error: CSV ファイルが見つかりません: {csv_path}", file=sys.stderr)
        sys.exit(1)
    if not album_dir.is_dir():
        print(f"Error: ディレクトリが見つかりません: {album_dir}", file=sys.stderr)
        sys.exit(1)

    # CSV 読み込み
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print("Error: CSV が空です", file=sys.stderr)
        sys.exit(1)

    # CSV カラム・index バリデーション
    required_columns = {'index', 'filetype', 'timestamp', 'registrant', 'status'}
    missing = required_columns - rows[0].keys()
    if missing:
        print(f"Error: CSV に必須カラムがありません: {', '.join(sorted(missing))}", file=sys.stderr)
        sys.exit(1)

    index_errors: list[str] = []
    for i, row in enumerate(rows):
        expected = i + 1
        try:
            actual = int(row['index'])
        except ValueError:
            index_errors.append(f"行 {i + 1}: index が整数ではありません: {row['index']!r}")
            continue
        if actual != expected:
            index_errors.append(f"行 {i + 1}: index={actual}, 期待値={expected}")
    if index_errors:
        for e in index_errors:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # ファイル一覧を取得してインデックス順にソート
    jpg_files = sorted(album_dir.glob('*.jpg'), key=extract_file_index)
    mp4_files = sorted(album_dir.glob('*.mp4'), key=extract_file_index)
    total_files = len(jpg_files) + len(mp4_files)

    # --- バリデーション ---
    print("バリデーション中...")
    print(f"  CSV 行数:    {len(rows)}")
    print(f"  JPG ファイル数: {len(jpg_files)}")
    print(f"  MP4 ファイル数: {len(mp4_files)}")
    print(f"  ファイル合計:  {total_files}")

    csv_jpg_rows = [r for r in rows if r['filetype'].lower() == 'jpg']
    csv_mp4_rows = [r for r in rows if r['filetype'].lower() == 'mp4']

    errors: list[str] = []

    # 合計数チェック
    if total_files != len(rows):
        errors.append(
            f"合計数が一致しません: ファイル={total_files}, CSV={len(rows)}"
        )
    if len(jpg_files) != len(csv_jpg_rows):
        errors.append(
            f"JPG 数が一致しません: ファイル={len(jpg_files)}, CSV={len(csv_jpg_rows)}"
        )
    if len(mp4_files) != len(csv_mp4_rows):
        errors.append(
            f"MP4 数が一致しません: ファイル={len(mp4_files)}, CSV={len(csv_mp4_rows)}"
        )

    if errors:
        for e in errors:
            print(f"  [ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    print("  バリデーション OK")

    # --- exiftool 適用 ---
    print("\nタイムスタンプを埋め込み中...")
    failed = 0

    print(f"  JPG {len(csv_jpg_rows)} 件を処理中...")
    for file, row in zip(jpg_files, csv_jpg_rows):
        dt = parse_timestamp(row['timestamp'])
        print(f"  [index={row['index']}] {file.name}  <-  {fmt_tz(dt)}")
        if not apply_exiftool_jpg(file, dt):
            failed += 1

    print(f"  MP4 {len(csv_mp4_rows)} 件を処理中...")
    for file, row in zip(mp4_files, csv_mp4_rows):
        dt = parse_timestamp(row['timestamp'])
        print(f"  [index={row['index']}] {file.name}  <-  {fmt_tz(dt)}")
        if not apply_exiftool_mp4(file, dt):
            failed += 1

    if failed:
        print(f"\n完了 (失敗: {failed} 件)", file=sys.stderr)
        sys.exit(1)
    else:
        print("\n完了")


if __name__ == '__main__':
    main()
