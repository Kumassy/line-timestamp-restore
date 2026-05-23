# line-timestamp-restore

## 背景

LINE アルバムにアップロードされた写真・動画は、ダウンロード時に EXIF などのメタデータが削除される。
撮影日時は LINE アプリの「詳細情報」画面で確認できるが、ファイルには残らない。

本プロジェクトは 2 つのステップでこの問題を解決する:

1. **extract.py** — Android 端末に接続し、LINE アルバムを自動操作して撮影日時・登録者を CSV に書き出す
2. **embed.py** — CSV とダウンロード済みファイルを照合し、exiftool でメタデータを埋め込む

## 前提条件

- LINE アプリが Android 及び PC にインストールされていること
- [uv](https://docs.astral.sh/uv/) がインストールされていること
- [exiftool](https://exiftool.org/) がインストールされていること
- Android 端末を USB デバッグ有効でホスト PC に接続済みであること
- Android 端末で LINE アプリを立ち上げ、抽出対象アルバムの 1 枚目の画像を開いた状態にしておくこと

macOS の場合の必要パッケージ: 

```
brew install uv
brew install exiftool
```

### セットアップ

```bash
uv sync
```

## extract.py の使い方

LINE アプリ上でアルバムを「追加順」に並び替え、 **1 枚目の画像を開いた状態**にしてから実行する。

スクリプトが自動的に全画像をスワイプしながら詳細情報を取得し、`line_album_datetime.csv` に書き出す。

> **注意**: タイムスタンプは JST (UTC+9) であることを前提としています。

```bash
uv run python extract.py
```

### 出力 CSV の形式

```
index,filetype,timestamp,registrant,status
1,jpg,2026/04/04 11:59,山田 太郎,ok
2,mp4,2026/04/04 12:02,山田 太郎,ok
```

| カラム | 内容 |
|---|---|
| `index` | アルバム内の連番 (1始まり) |
| `filetype` | `jpg` または `mp4` |
| `timestamp` | 撮影日時 (`YYYY/MM/DD HH:MM`) |
| `registrant` | アルバム登録者名 |
| `status` | `ok` / `detail_open_failed` / `datetime_not_found` |

## embed.py の使い方
PC 版 LINE アプリでアルバム→「すべて保存」から写真・動画をダウンロードしておく。
このとき画像, 動画それぞれ 1 始まりの連番が付与されるが、これはアルバムに追加した順になる。また、画像, 動画は独立にカウントされる。

PC 版 LINE アプリ等でアルバムをダウンロードしたディレクトリと CSV を指定して `embed.py` を実行する。

> **注意**: タイムスタンプは JST (UTC+9) であることを前提としています。

```bash
uv run python embed.py <csv_path> <album_dir>
```

### 例

```bash
uv run python embed.py \
  line_album_datetime_202604_tokyo.csv \
  ~/Downloads/line_album_202604_tokyo
```

### 埋め込まれるメタデータ

**JPG**

| タグ | 値 |
|---|---|
| `DateTimeOriginal`, `CreateDate`, `ModifyDate` | 撮影日時（ローカル時刻） |
| `OffsetTime`, `OffsetTimeOriginal`, `OffsetTimeDigitized` | `+09:00` |
| `FileModifyDate` | タイムゾーン付き撮影日時 |
| `Software` | `line-timestamp-restore <version>` |

**MP4**

| タグ | 値 |
|---|---|
| `CreateDate`, `ModifyDate`, `TrackCreate/ModifyDate`, `MediaCreate/ModifyDate` | 撮影日時（UTC） |
| `XMP:CreateDate`, `XMP:ModifyDate` | タイムゾーン付き撮影日時 |
| `FileModifyDate` | タイムゾーン付き撮影日時 |
| `XMP:CreatorTool` | `line-timestamp-restore <version>` |
