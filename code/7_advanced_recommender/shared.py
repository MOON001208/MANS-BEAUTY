"""Explicit configuration, atomic checkpoints and complete database reads."""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / '.pipeline-cache'

def product_type(name, category=''):
    import re
    # Source categories outrank name keywords (e.g. a primer mentioning cushion).
    source_types = {'프라이머/베이스': 'primer', '메이크업베이스/프라이머': 'primer',
                    '파우더/팩트': 'powder', '파우더': 'powder', '쉐이딩': 'shading'}
    source_type = source_types.get(re.sub(r'\s+', '', category or ''))
    if source_type:
        return source_type
    text = (name or '') + ' ' + (category or '')
    if '컨실러' in text:
        return 'concealer'
    if '쿠션' in text:
        return 'cushion'
    if '스틱' in text:
        return 'stick'
    if re.search(r'로션|BB|CC|비비|톤업', text, re.I):
        return 'tone_lotion'
    return 'liquid'

def utc_now():
    return datetime.now(timezone.utc).isoformat()

def database():
    from dotenv import load_dotenv
    from supabase import create_client
    for path in [ROOT / '.env', ROOT / 'scraper/.env', ROOT / 'pipeline/.env']:
        load_dotenv(path, override=False)
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SECRET_KEY') or os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY')
    if not url or not key:
        raise RuntimeError('SUPABASE_URL 및 서버 전용 SUPABASE_SECRET_KEY가 필요합니다.')
    return create_client(url, key)

def read_all(db, table, columns='*', filters=None):
    """Keyset pagination: works even if the API row cap is below 1000."""
    last_id = None
    while True:
        query = db.table(table).select(columns).order('id').limit(500)
        for key, value in (filters or {}).items():
            query = query.eq(key, value)
        if last_id is not None:
            query = query.gt('id', last_id)
        rows = query.execute().data or []
        if not rows:
            return
        yield from rows
        if rows[-1]['id'] == last_id:
            raise RuntimeError('DB 페이지 커서가 진행하지 않습니다.')
        last_id = rows[-1]['id']

def write_json(path, value, attempts=5):
    """Atomic write that survives a concurrent reader.

    On Windows the replace fails with PermissionError while another process has
    the destination open, which is exactly what happens when someone tails a
    progress report. Losing a long crawl to that is not acceptable, so the
    replace is retried briefly before giving up.
    """
    import time
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    for attempt in range(attempts):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.2 * (attempt + 1))

def read_json(path, default):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
