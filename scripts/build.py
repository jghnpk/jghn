"""
Pepper Glossary - Google Sheets Sync Builder
구글 시트 데이터를 받아서 index.html을 자동 생성합니다.
"""
import os, json, requests, re
from datetime import datetime, timezone, timedelta

SHEET_ID = os.environ['SHEET_ID']
API_KEY  = os.environ['API_KEY']

# 시트 탭 이름 목록 (구글 시트의 탭 이름과 정확히 일치해야 함)
SHEET_TABS = [
    'KRAFTON', 'Finance', 'M&A', 'Legal', 'Pharma',
    'Government', 'Technology', 'Aesthetic Surgery ',
    'Entertainment', 'AD_MKT', 'Rocket Now', 'Genarative AI'
]

# 컬럼명 후보 (대소문자 변형 대응)
COL = {
    'ja':       ['JA', 'ja'],
    'en':       ['EN', 'en'],
    'ko':       ['KO', 'ko'],
    'memo':     ['Memo', 'memo', 'MEMO'],
    'category': ['Category', 'category'],
    'type':     ['Type', 'type'],
    'ai_ja':    ['ai_ja'],
    'ai_en':    ['ai_en'],
    'ai_ko':    ['ai_ko'],
}

def find_col(row, cands):
    for c in cands:
        if c in row:
            return row[c]
    return ''

def fetch_sheet(tab_name):
    """Google Sheets API v4로 특정 탭 데이터를 가져옵니다."""
    url = (
        f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}"
        f"/values/{requests.utils.quote(tab_name)}"
        f"?key={API_KEY}"
    )
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    values = data.get('values', [])
    if not values:
        return []

    headers = values[0]
    rows = []
    for row_vals in values[1:]:
        # 열 수가 헤더보다 짧으면 빈 문자열로 패딩
        padded = row_vals + [''] * (len(headers) - len(row_vals))
        row = dict(zip(headers, padded))
        rows.append(row)
    return rows

def process_rows(tab_name, rows):
    """각 행을 RAW_DATA 형식으로 변환합니다."""
    result = []
    for row in rows:
        ja  = str(find_col(row, COL['ja'])).strip()
        en  = str(find_col(row, COL['en'])).strip()
        ko  = str(find_col(row, COL['ko'])).strip()
        if not ja and not en and not ko:
            continue

        def to_bool(v):
            return str(v).strip().upper() in ('TRUE', '1', 'YES')

        entry = {
            'sheet':    tab_name,
            'type':     str(find_col(row, COL['type'])).strip(),
            'ja':       ja,
            'en':       en,
            'ko':       ko,
            'category': str(find_col(row, COL['category'])).strip(),
            'memo':     str(find_col(row, COL['memo'])).strip(),
            'memo2':    '',
            'ai_ja':    to_bool(find_col(row, COL['ai_ja'])),
            'ai_en':    to_bool(find_col(row, COL['ai_en'])),
            'ai_ko':    to_bool(find_col(row, COL['ai_ko'])),
        }
        result.append(entry)
    return result

def main():
    print("Fetching data from Google Sheets...")
    all_data = []
    for tab in SHEET_TABS:
        try:
            rows = fetch_sheet(tab)
            entries = process_rows(tab, rows)
            all_data.extend(entries)
            print(f"  {tab}: {len(entries)} entries")
        except Exception as e:
            print(f"  WARNING: {tab} failed - {e}")

    print(f"Total: {len(all_data)} entries")

    # 업데이트 시각 (JST)
    jst = timezone(timedelta(hours=9))
    now_str = datetime.now(jst).strftime('%Y-%m-%d %H:%M JST')

    # 시트 옵션 HTML 생성
    sheet_options = '\n'.join(
        f'<option value="{s}">{s}</option>' for s in SHEET_TABS
    )

    # 템플릿 로드
    script_dir = os.path.dirname(os.path.abspath(__file__))
    before = open(os.path.join(script_dir, 'template_before.txt')).read()
    after  = open(os.path.join(script_dir, 'template_after.txt')).read()

    # updateInfo 날짜 교체
    before = re.sub(
        r'id="updateInfo">[^<]*<',
        f'id="updateInfo">{now_str}<',
        before
    )

    # 단어 추가 모달의 시트 선택 옵션 교체
    before = re.sub(
        r'<select id="wordSheet">.*?</select>',
        f'<select id="wordSheet">{sheet_options}</select>',
        before, flags=re.DOTALL
    )

    # RAW_DATA 삽입
    raw_json = json.dumps(all_data, ensure_ascii=False)
    html = before + f'var RAW_DATA = {raw_json};\n' + after

    # dist 디렉토리에 출력
    dist_dir = os.path.join(os.path.dirname(script_dir), 'dist')
    os.makedirs(dist_dir, exist_ok=True)
    out_path = os.path.join(dist_dir, 'index.html')
    open(out_path, 'w', encoding='utf-8').write(html)
    print(f"Built: {out_path} ({len(html):,} bytes)")

    # favicon.svg 복사
    import shutil
    favicon_src = os.path.join(os.path.dirname(script_dir), 'favicon.svg')
    favicon_dst = os.path.join(dist_dir, 'favicon.svg')
    if os.path.exists(favicon_src):
        shutil.copy2(favicon_src, favicon_dst)
        print(f"Copied: favicon.svg")
    else:
        print("WARNING: favicon.svg not found in repo root")

if __name__ == '__main__':
    main()
