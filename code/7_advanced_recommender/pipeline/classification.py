"""Evidence-based base makeup formulation and recommendation eligibility rules.

Never guess liquid vs stick from gift volumes, promo wording, or gift puffs.
Unverified or conflicting foundations stay explicitly unconfirmed rather than
falling back to liquid or cushion.
"""
from __future__ import annotations

import re

NON_COVER_SOURCE_TYPES = {
    '프라이머/베이스': 'primer',
    '메이크업베이스/프라이머': 'primer',
    '파우더/팩트': 'powder',
    '파우더': 'powder',
    '쉐이딩': 'shading',
    '컨실러': 'concealer',
}
LIP_SOURCE_CATEGORIES = {
    '립메이크업', '립밤', '립케어', '립틴트', '립스틱', '립글로즈', '컬러립밤',
}
NON_COVER_TYPES = frozenset({'concealer', 'primer', 'powder', 'shading'})
FULL_FACE_BASE_TYPES = frozenset({'cushion', 'liquid', 'stick', 'tone_lotion', 'foundation_unknown'})

# Strip gift/promo clauses without breaking SPF50+, PA+++, or 1+1.
_GIFT_PAREN = re.compile(r'\(\s*[+＋][^)]*(?:\)|$)')
_GIFT_PROMO_TAIL = re.compile(
    r'(?:단품/기획|기획/단품|단독기획|기획세트|기획)\s*(?:\([^)]*(?:\)|$)|[+＋].*$)'
)
_PROTECT_SPF_PA = re.compile(r'(SPF\s*\d+|PA)\++', re.I)
_PROTECT_ONE_PLUS_ONE = re.compile(r'\b1\s*\+\s*1\b')

_LIP_PRODUCT_RE = re.compile(r'립밤|레드립밤|컬러립밤|립스틱|립틴트|립글로즈|립\s*케어|코어밤')
_OTHER_MAKEUP_BUNDLE_RE = re.compile(
    r'립밤|레드립밤|컬러립밤|립스틱|립틴트|립글로즈|립\s*케어|코어밤|'
    r'아이브로우|브로우\s*펜슬|마스카라|아이라이너|아이섀도우|'
    r'오일\s*컨트롤\s*피니셔|피니셔|노세범\s*파우더|세범\s*파우더|파우더|프라이머|쉐딩|쉐이딩|컨실러'
)
_BASE_PRODUCT_RE = re.compile(
    r'쿠션|파운데이션|파데|커버\s*로션|톤\s*로션|톤로션|톤\s*컨트롤\s*로션|'
    r'톤\s*커버\s*로션|필터\s*로션|비비|BB|CC|톤업\s*크림|톤케어\s*크림|큐라톤즈',
    re.I,
)

# Clause splitting and experience guards match pipeline/profiles.py.
_CLAUSE_SPLIT = re.compile(r'[.!?\n]+|(?:지만|그런데|하지만)')
_FUTURE_OR_PAST = (
    re.compile(r'(?:구매|구입|사용해보)(?:하려|하고\s*싶|려고)|(?:사려|사려고|사고\s*싶)|제품을\s*(?:찾|구하)'),
    re.compile(r'(?:기존|예전|이전).{0,80}(?:써왔|쓰던|사용하던|썼던|사용했)'),
)
_HYPOTHETICAL = re.compile(r'원하|원했|바랄|바라|좋겠|기대|예정|구매\s*전|후기.{0,12}(?:보니|읽)')

# Direct review statements describing this product's actual content/formulation
# (not tool-only mentions such as built-in/rear brushes, which liquid bottles also have).
_STICK_DIRECT = re.compile(
    r'(?<!립)스틱\s*(?:형|타입|형태|파데|파운데이션|이라|여서|이어서|제품|으로|이기에|이네요|입니다)|'
    r'(?:이건|이\s*제품은?|파데가?)\s*(?<!립)스틱|'
    r'고체\s*(?:형|타입|형태|제형|스틱)|'
    r'(?:상단|용기|스틱|내용물).{0,10}돌려(?:서)?\s*(?:꺼내|올려|쓰|사용)'
)
_STICK_EXCLUDE = re.compile(
    r'립스틱|'
    r'스틱.{0,18}(?:보다|비해|대신|말고|달리|쓰다가|쓰던|사용하다가|만\s*쓰다가|만\s*쓰던|쓸\s*때는|같은\s*건|같은\s*거|아니라|안\s*쓰)|'
    r'(?:타\s*브랜드|타사|기존|예전|다른|오브제|다슈|보통)\s*(?:스틱|파운데이션\s*스틱)|'
    r'스틱(?:형|타입)?인줄\s*알았'
)
_LIQUID_DIRECT = re.compile(
    r'리퀴드\s*(?:형|타입|형태|제형|파데|파운데이션|이라|여서|이어서|제품)?|'
    r'액체\s*(?:형|타입|형태|제형|재질|이라|여서|이어서)|'
    r'펌핑\s*(?:형|식|해서|하면|해|으로|기|한번|두번|1번|2번|소량)|'
    r'펌프\s*(?:형|식|용기|타입|파데)|'
    r'(?<![가-힣])튜브\s*(?:형|타입|형태|용기|라서|라)|'
    r'스포이드|'
    r'짜서\s*(?:쓰|사용|바르)|'
    r'묽(?:은\s*(?:편|제형|타입|느낌)|어서|고|다)|'
    r'흘러\s*내리'
)
_LIQUID_EXCLUDE = re.compile(
    r'(?:리퀴드|액체|펌핑|펌프|튜브|짜서).{0,18}(?:보다|비해|대신|말고|달리|쓰다가|쓰던|사용하다가|만\s*사용하다|아니라|아니고|안\s*쓰)|'
    r'(?:타\s*브랜드|타사|기존|예전|다른|비레디|이전에\s*사용하던).{0,22}(?:리퀴드|펌핑|펌프|튜브|액체)|'
    r'(?:묽지|흘러\s*내리지|흘러\s*내리는\s*느낌\s*없|펌프식이\s*아니|짜서\s*쓰는\s*게\s*아니)'
)

_LIP_REVIEW_RE = re.compile(r'립밤|립스틱|입술|코어밤|컬러립|립\s*케어|생기\s*립|레드립|립틴트|립글로즈')
_BASE_REVIEW_RE = re.compile(r'파운데이션|파데|쿠션|비비|BB|CC|로션|톤업|커버|컨실러|피부톤|모공|잡티|얼굴', re.I)

# Display-group labels stored in products.category must never be treated as source categories.
_DISPLAY_GROUPS = {'쿠션/파운데이션', '톤로션/BB'}
_BRACKET_TAG = re.compile(r'\[[^\]]*\]')

# Directly verified seller-page/thumbnail formulation records for foundation SKUs
# whose product title omits 스틱/리퀴드. Applied ONLY when both SKU ID and
# canonical primary product name match.
VERIFIED_SELLER_FORMULATIONS = {
    'A000000203000': {
        'product_type': 'liquid',
        'primary_name': '라끌랑 올데이 픽싱 커버 파운데이션 30ml (1호/2호) 2종 택1',
        'source_url': 'https://image.oliveyoung.co.kr/cfimages/cf-goods/uploads/images/thumbnails/400/10/0000/0020/A00000020300004ko.jpg?l=ko',
        'verified_at': '2026-11-24',
        'verified_fact': '판매자 대표 사진에서 30ml 투명 병 액상 파운데이션을 봉 팁 어플리케이터로 꺼내 도포하고 상단 브러시로 펴 바르는 리퀴드 제형 확인',
    },
    'A000000210307': {
        'product_type': 'stick',
        'primary_name': '듀이셀 트루빔 파운데이션 12g',
        'source_url': 'https://image.oliveyoung.co.kr/cfimages/cf-goods/uploads/images/thumbnails/10/0000/0021/A00000021030706ko.jpg?l=ko',
        'verified_at': '2026-11-24',
        'verified_fact': '판매자 대표 사진 본품 용기와 단상자에 Stick Type 및 고체 스틱 도식 표기, 큐라힐스 패드 20매 증정 명시 확인',
    },
    'A000000222827': {
        'product_type': 'liquid',
        'primary_name': '그라펜 팁 스케치 멀티 커버 파운데이션 20ml',
        'source_url': 'https://image.oliveyoung.co.kr/cfimages/cf-goods/uploads/images/thumbnails/10/0000/0022/A00000022282742ko.jpg?l=ko',
        'verified_at': '2026-11-24',
        'verified_fact': '판매자 대표 사진 본품 용기 20ML(0.67FL.OZ.) 표기 및 일체형 스펀지 팁으로 액상 제형을 도포하는 리퀴드 파운데이션 구조와 모공클렌저 증정 명시 확인',
    },
    'A000000224891': {
        'product_type': 'liquid',
        'primary_name': '그라펜 팁 스케치 멀티 커버 파운데이션 20ml (2종 택1)',
        'source_url': 'https://image.oliveyoung.co.kr/cfimages/cf-goods/uploads/images/thumbnails/10/0000/0022/A00000022489101ko.jpg?l=ko',
        'verified_at': '2026-11-24',
        'verified_fact': '판매자 대표 사진 본품 용기 20ML(0.67FL.OZ.) 표기 및 상단 스펀지 팁 토출 다이얼 구조의 액상 리퀴드 파운데이션 확인',
    },
}


def canonical_primary_name(name: str | None) -> str:
    """Primary product name with marketing bracket prefixes normalized away."""
    without_tags = _BRACKET_TAG.sub(' ', primary_product_name(name))
    return re.sub(r'\s+', ' ', without_tags).strip()


def verified_seller_formulation(product_id: str | None, name: str | None) -> dict | None:
    """Return verified seller formulation record only when SKU ID and primary name match."""
    entry = VERIFIED_SELLER_FORMULATIONS.get(str(product_id or '').strip())
    if not entry:
        return None
    if canonical_primary_name(name) != entry['primary_name']:
        return None
    return entry


def _protect_non_bundle_pluses(text: str) -> str:
    protected = _PROTECT_SPF_PA.sub(lambda m: m.group(0).replace('+', '_PLUS_'), text or '')
    return _PROTECT_ONE_PLUS_ONE.sub('1_PLUS_1', protected)


def _split_bundle_parts(text: str) -> list[str]:
    protected = _protect_non_bundle_pluses(text)
    return [part.replace('_PLUS_', '+').strip() for part in re.split(r'[+＋]', protected) if part.strip()]


def primary_product_name(name: str | None) -> str:
    """Return the main item title with gift/promo suffixes removed."""
    text = name or ''
    cleaned = _GIFT_PROMO_TAIL.sub(' ', text)
    cleaned = _GIFT_PAREN.sub(' ', cleaned)
    protected = _protect_non_bundle_pluses(cleaned)
    if '+' in protected or '＋' in protected:
        protected = re.split(r'[+＋]', protected, maxsplit=1)[0]
    cleaned = protected.replace('_PLUS_', '+')
    cleaned = re.sub(r'\s*(?:단품/기획|기획/단품|단독기획|기획세트|기획)\s*$', '', cleaned)
    return re.sub(r'\s+', ' ', cleaned).strip()


def _primary_ml_volumes(primary_name: str) -> list[float]:
    return [float(val) for val in re.findall(r'(\d+(?:\.\d+)?)\s*ml\b', primary_name, re.I)]


def _current_clauses(text: str) -> list[str]:
    parts = []
    for raw in _CLAUSE_SPLIT.split(text or ''):
        part = raw.strip()
        if not part or _HYPOTHETICAL.search(part):
            continue
        if _FUTURE_OR_PAST[0].search(part):
            continue
        if _FUTURE_OR_PAST[1].search(part) and not re.search(r'보다|비해', part):
            continue
        parts.append(part)
    return parts


def extract_formulation_evidence(reviews) -> dict[str, list[str]]:
    """Extract deterministic review IDs stating stick vs liquid formulation."""
    unique = {str(r['id']): r for r in (reviews or [])}
    stick_ids, liquid_ids, mixed_ids = [], [], []
    for rid in sorted(unique):
        review = unique[rid]
        s_hit = l_hit = False
        for part in _current_clauses(review.get('content') or ''):
            if _STICK_DIRECT.search(part) and not _STICK_EXCLUDE.search(part):
                s_hit = True
            if _LIQUID_DIRECT.search(part) and not _LIQUID_EXCLUDE.search(part):
                l_hit = True
        if s_hit and l_hit:
            mixed_ids.append(rid)
        elif s_hit:
            stick_ids.append(rid)
        elif l_hit:
            liquid_ids.append(rid)
    return {'stick': stick_ids, 'liquid': liquid_ids, 'mixed': mixed_ids}


def _clean_source_category(category: str | None) -> str:
    compact = re.sub(r'\s+', '', category or '')
    return '' if compact in _DISPLAY_GROUPS else compact


def infer_static_product_type(name: str | None, source_category: str | None = '') -> str:
    """Classify product_type from seller category and primary name only.

    Never reads products.category display groups ('쿠션/파운데이션'), gift volumes,
    promo wording, or gift puffs. Ambiguous foundations return 'foundation_unknown'.
    """
    sc = _clean_source_category(source_category)
    primary = primary_product_name(name)

    if sc in NON_COVER_SOURCE_TYPES:
        return NON_COVER_SOURCE_TYPES[sc]
    if sc in LIP_SOURCE_CATEGORIES:
        return 'lip'
    if sc == '쿠션':
        return 'cushion'
    if sc == 'BB/CC':
        return 'tone_lotion'
    if sc == '올인원':
        if re.search(r'로션|BB|CC|비비|톤업|톤케어|커버', primary, re.I):
            return 'tone_lotion'
        return 'unknown'
    if sc == '파운데이션' or re.search(r'파운데이션|파데', primary):
        has_stick = '스틱' in primary
        has_liquid = '리퀴드' in primary
        if has_stick and not has_liquid:
            return 'stick'
        if has_liquid and not has_stick:
            return 'liquid'
        if has_stick and has_liquid:
            return 'foundation_unknown'
        if '쿠션' in primary:
            return 'cushion'
        return 'foundation_unknown'

    if '컨실러' in primary:
        return 'concealer'
    if '프라이머' in primary:
        return 'primer'
    if re.search(r'파우더|팩트|피니셔', primary):
        return 'powder'
    if re.search(r'쉐딩|쉐이딩', primary):
        return 'shading'
    if _LIP_PRODUCT_RE.search(primary) and not _BASE_PRODUCT_RE.search(primary):
        return 'lip'
    if '쿠션' in primary:
        return 'cushion'
    if '스틱' in primary:
        return 'stick'
    if '리퀴드' in primary:
        return 'liquid'
    if re.search(r'로션|BB|CC|비비|톤업|톤케어|큐라톤즈', primary, re.I):
        return 'tone_lotion'
    return 'unknown'


def classify_formulation(product: dict, reviews=()) -> tuple[str, dict]:
    """Resolve (product_type, formulation_metadata) from product metadata and reviews."""
    name = product.get('name') or ''
    meta = product.get('profile_metadata') or {}
    sc_raw = meta.get('source_category') or ''
    sc = _clean_source_category(sc_raw)
    primary = primary_product_name(name)

    # Minimal synthetic fixtures with neither name nor source_category preserve explicit type.
    if not primary and not sc:
        explicit = product.get('product_type')
        if explicit:
            return explicit, {'status': 'confirmed', 'basis': 'preserved', 'evidence_review_ids': []}
        return 'unknown', {'status': 'unconfirmed', 'basis': 'insufficient_evidence', 'evidence_review_ids': []}

    static_type = infer_static_product_type(name, sc_raw)
    is_foundation = sc == '파운데이션' or bool(re.search(r'파운데이션|파데', primary))

    if static_type != 'foundation_unknown':
        if static_type == 'unknown':
            return 'unknown', {'status': 'unconfirmed', 'basis': 'insufficient_evidence', 'evidence_review_ids': []}
        basis = 'source_category' if sc in NON_COVER_SOURCE_TYPES or sc in LIP_SOURCE_CATEGORIES or sc in {'쿠션', 'BB/CC'} else 'name'
        return static_type, {'status': 'confirmed', 'basis': basis, 'evidence_review_ids': []}

    # Ambiguous foundation (no explicit 스틱/리퀴드 in primary name).
    if '스틱' in primary and '리퀴드' in primary:
        return 'foundation_unknown', {'status': 'unconfirmed', 'basis': 'conflicting_name', 'evidence_review_ids': []}

    seller_verified = verified_seller_formulation(product.get('id'), name)
    if seller_verified:
        return seller_verified['product_type'], {
            'status': 'confirmed',
            'basis': 'seller_verified',
            'source_url': seller_verified['source_url'],
            'verified_at': seller_verified['verified_at'],
            'verified_fact': seller_verified['verified_fact'],
            'evidence_review_ids': [],
        }

    ev = extract_formulation_evidence(reviews)
    s, l, m = len(ev['stick']), len(ev['liquid']), len(ev['mixed'])
    counts = {'stick': s, 'liquid': l, 'mixed': m}
    primary_mls = _primary_ml_volumes(primary)

    if s >= 3 and s >= 3 * l and s > m:
        # Guard: a liquid-unit main volume (>= 20ml) contradicting stick review claims
        # stays unconfirmed rather than forcing stick or guessing liquid.
        if primary_mls and max(primary_mls) >= 20:
            return 'foundation_unknown', {
                'status': 'unconfirmed',
                'basis': 'conflicting_evidence',
                'counts': counts,
                'evidence_review_ids': ev['stick'][:5],
            }
        return 'stick', {
            'status': 'confirmed',
            'basis': 'reviews',
            'counts': counts,
            'evidence_review_ids': ev['stick'][:5],
        }

    if l >= 3 and l >= 3 * s and l > m:
        return 'liquid', {
            'status': 'confirmed',
            'basis': 'reviews',
            'counts': counts,
            'evidence_review_ids': ev['liquid'][:5],
        }

    basis = 'mixed_evidence' if (s >= 3 and l >= 3) or m >= 3 else 'insufficient_evidence'
    sample_ids = (ev['stick'][:3] + ev['liquid'][:3])[:5] if is_foundation else []
    return 'foundation_unknown', {
        'status': 'unconfirmed',
        'basis': basis,
        'counts': counts,
        'evidence_review_ids': sample_ids,
    }


def _secondary_makeup_match(text: str) -> str | None:
    parts = _split_bundle_parts(text)
    if len(parts) < 2:
        return None
    secondary = ' '.join(parts[1:])
    match = _OTHER_MAKEUP_BUNDLE_RE.search(secondary)
    return match.group(0) if match else None


def evaluate_recommendation_eligibility(product: dict, reviews=(), resolved_type: str | None = None) -> dict:
    """Determine whether a catalog SKU is eligible for full-face base quiz ranking.

    Preserves single-product promos with simple gifts (cleanser, toner pad, puff,
    miniature, refill, 1+1). Excludes non-cover base categories, lip-primary SKUs,
    mixed multi-makeup sets, and SKUs whose review pool is heavily contaminated
    by lip product reviews.
    """
    name = product.get('name') or ''
    meta = product.get('profile_metadata') or {}
    sc = _clean_source_category(meta.get('source_category'))
    ptype = resolved_type if resolved_type is not None else classify_formulation(product, reviews)[0]

    if sc in LIP_SOURCE_CATEGORIES or ptype == 'lip':
        return {
            'eligible': False,
            'exclusion_reason': 'lip_primary',
            'detail': '립 주상품',
            'evidence_review_ids': [],
        }

    if sc in NON_COVER_SOURCE_TYPES or ptype in NON_COVER_TYPES:
        return {
            'eligible': False,
            'exclusion_reason': 'non_cover_base',
            'detail': f'전체 얼굴 커버 유형 아님 ({sc or ptype})',
            'evidence_review_ids': [],
        }

    if ptype == 'unknown':
        return {
            'eligible': False,
            'exclusion_reason': 'unknown_type',
            'detail': '제형 및 제품 유형 근거 부족',
            'evidence_review_ids': [],
        }

    bundled_item = _secondary_makeup_match(name)
    if bundled_item:
        return {
            'eligible': False,
            'exclusion_reason': 'mixed_set',
            'detail': f'혼합 세트 구성 (+{bundled_item})',
            'evidence_review_ids': [],
        }

    # If the listing has named catalog options and EVERY option is a mixed makeup bundle,
    # exclude it; listings with standalone base options stay eligible.
    named_options = [
        (o.get('name') or '').strip()
        for o in (product.get('source_options') or [])
        if (o.get('name') or '').strip()
    ]
    if named_options:
        option_matches = [_secondary_makeup_match(opt) for opt in named_options]
        if all(option_matches):
            return {
                'eligible': False,
                'exclusion_reason': 'mixed_set',
                'detail': f'전 옵션 혼합 세트 구성 (+{option_matches[0]})',
                'evidence_review_ids': [],
            }

    unique = {str(r['id']): r for r in (reviews or [])}
    total = len(unique)
    if total >= 5:
        lip_ids, lip_only_ids = [], []
        for rid in sorted(unique):
            content = unique[rid].get('content') or ''
            if _LIP_REVIEW_RE.search(content):
                lip_ids.append(rid)
                if not _BASE_REVIEW_RE.search(content):
                    lip_only_ids.append(rid)
        if (len(lip_ids) >= 5 and len(lip_ids) / total >= 0.25) or (
            len(lip_only_ids) >= 5 and len(lip_only_ids) / total >= 0.20
        ):
            return {
                'eligible': False,
                'exclusion_reason': 'lip_contaminated_reviews',
                'detail': f'립 관련 리뷰 혼입 ({len(lip_ids)}/{total}, {len(lip_ids) / total * 100:.1f}%)',
                'evidence_review_ids': (lip_only_ids or lip_ids)[:5],
            }

    return {
        'eligible': True,
        'exclusion_reason': None,
        'detail': None,
        'evidence_review_ids': [],
    }


def classify_product(product: dict, reviews=()) -> tuple[str, dict, dict]:
    """Return (product_type, formulation_metadata, recommendation_eligibility)."""
    ptype, formulation = classify_formulation(product, reviews)
    eligibility = evaluate_recommendation_eligibility(product, reviews, resolved_type=ptype)
    return ptype, formulation, eligibility
