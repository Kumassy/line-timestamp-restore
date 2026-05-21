import uiautomator2 as u2
import time
import csv
import re
import xml.etree.ElementTree as ET

d = u2.connect()

def dump_hierarchy_xml():
    return d.dump_hierarchy()

def swipe_next():
    # 右から左へスワイプして次の画像へ
    d.swipe(0.85, 0.5, 0.15, 0.5, duration=0.1)
    time.sleep(0.8)

def open_detail_tab():
    # content-desc="もっと見る" の ImageView をタップ（window_pic.xml で確認済み）
    btn = d(description="もっと見る")
    if not btn.exists(timeout=1.0):
        return False
    btn.click()
    time.sleep(0.3)

    # 表示名は端末・LINEバージョンで違う可能性あり
    for label in ["詳細情報", "詳細", "情報", "写真の情報"]:
        if d(text=label).exists(timeout=0.5):
            d(text=label).click()
            time.sleep(0.5)
            return True

    return False

def close_detail_tab():
    # 戻るで詳細を閉じる想定
    d.press("back")
    time.sleep(0.3)

def extract_index_and_total(xml):
    """
    画像表示中の画面から "(x/n)" テキストを探してインデックスと総数を返す。
    """
    root = ET.fromstring(xml)
    for node in root.iter('node'):
        m = re.fullmatch(r'\((\d+)/(\d+)\)', (node.get('text') or '').strip())
        if m:
            return int(m.group(1)), int(m.group(2))
    return None, None


def extract_datetime_from_xml(xml):
    """
    詳細画面で "作成日時" ラベルの直後ノードの text を返す。
    """
    root = ET.fromstring(xml)
    nodes = list(root.iter('node'))
    for i, node in enumerate(nodes):
        if node.get('text') == '作成日時' and i + 1 < len(nodes):
            return nodes[i + 1].get('text')
    return None


def extract_registrant_from_xml(xml):
    """
    詳細画面で "登録者" ラベルの直後ノードの text を返す。
    """
    root = ET.fromstring(xml)
    nodes = list(root.iter('node'))
    for i, node in enumerate(nodes):
        if node.get('text') == '登録者' and i + 1 < len(nodes):
            return nodes[i + 1].get('text')
    return None


def extract_filetype_from_xml(xml):
    """
    画像表示中の画面で content-desc="再生" ノードがあれば "mp4"、なければ "jpg" を返す。
    """
    root = ET.fromstring(xml)
    for node in root.iter('node'):
        if node.get('content-desc') == '再生':
            return 'mp4'
    return 'jpg'

def save_csv(rows):
    with open("line_album_datetime.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["index", "filetype", "timestamp", "registrant", "status"])
        writer.writeheader()
        writer.writerows(rows)

rows = []

# ここではすでにLINEアルバムの1枚目画像を開いている前提
try:
    while True:
        xml = dump_hierarchy_xml()
        current, total = extract_index_and_total(xml)
        filetype = extract_filetype_from_xml(xml)

        ok = open_detail_tab()
        if not ok:
            dt = None
            registrant = None
            status = "detail_open_failed"
        else:
            detail_xml = dump_hierarchy_xml()
            dt = extract_datetime_from_xml(detail_xml)
            registrant = extract_registrant_from_xml(detail_xml)
            status = "ok" if dt else "datetime_not_found"
            close_detail_tab()

        rows.append({
            "index": current,
            "filetype": filetype,
            "timestamp": dt,
            "registrant": registrant,
            "status": status,
        })

        print(current, filetype, dt, registrant, status)

        if current is not None and total is not None and current == total:
            break

        swipe_next()

except KeyboardInterrupt:
    print("\nC-c を検出しました。途中結果を保存します...")
finally:
    save_csv(rows)