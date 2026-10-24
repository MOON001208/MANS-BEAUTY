"""Conservative, deterministic Korean review baseline. No paid API required.

Scores describe explicit textual evidence, not clinical compatibility. Absence
and mixed/negated evidence remain unknown. Reviewers' concerns are not benefits.
"""
from __future__ import annotations
import hashlib
import json
import re
from collections import Counter, defaultdict
from statistics import mean
from shared import product_type
from pipeline.wear import extract_wear, summarize_wear

VERSION = 'rules-ko-v3'
# Shape of profile_metadata. Bumping this rebuilds stored profiles on the next run
# without changing VERSION, so the deployed site keeps reading current profiles.
METADATA_REVISION = 8
SKIN_TYPES = {'지성': 'oily', '건성': 'dry', '복합성': 'combination', '중성': 'combination', '민감성': 'sensitive'}
ATTRIBUTES = {
    'coverage': (
        [r'커버(?:력)?(?:이|은|는|가|도)?\s*(?:정말|아주|너무|꽤)?\s*(?:좋|뛰어나|훌륭|잘\s*돼|잘\s*되)', r'(?:잡티|모공|흉터|홍조).{0,10}(?:잘\s*가려|잘\s*커버)'],
        [r'커버(?:력)?(?:이|은|는|가|도)?\s*(?:별로|부족|약해|약하|아쉬|안\s*돼|안\s*되)', r'(?:잡티|모공|흉터|홍조).{0,8}(?:안\s*가려|가려지지)']),
    'longevity': (
        [r'지속(?:력)?(?:이|은|는|가|도)?\s*(?:정말|아주|너무|꽤)?\s*(?:좋|뛰어나|길어|길다)', r'오래\s*(?:유지|가요|갑니다)', r'하루\s*종일.{0,10}(?:유지|멀쩡)'],
        [r'지속(?:력)?(?:이|은|는|가|도)?\s*(?:별로|부족|약해|약하|아쉬|짧)', r'(?:금방|빨리|쉽게)\s*(?:무너|지워|사라)']),
    'lightweight': (
        [r'(?:발림|착용감|사용감|제형).{0,10}(?:가벼|산뜻)', r'가볍게\s*발', r'가벼워요', r'가벼운\s*(?:느낌|사용감|제형)'],
        [r'무거워요', r'(?:사용감|제형|착용감).{0,10}(?:무겁|무거|답답)', r'답답해요', r'두껍게\s*발']),
}
CONCERNS = {'acne': '여드름|트러블', 'pore': '모공', 'redness': '홍조', 'spots': '잡티|다크서클', 'wrinkle': '주름'}
NEGATION = re.compile(r'않|아니|못|없|안\s*(?:되|돼|좋|가려|커버)|별로')
CONDITIONAL = re.compile(r'(?:좋|뛰어나|가려지|커버하|되|돼)(?:으면|면)')


def current_experience(part):
    if re.search(r'(?:구매|구입|사용해보)(?:하려|하고\s*싶|려고)|(?:사려|사려고|사고\s*싶)|제품을\s*(?:찾|구하)', part):
        return False
    if re.search(r'(?:기존|예전|이전).{0,80}(?:써왔|쓰던|사용하던|썼던|사용했)', part) and not re.search(r'보다|비해', part):
        return False
    return True


def positive_concern(part, words):
    """A concern name plus a product noun is not an observed benefit."""
    effect = (r'(?:잘\s*)?가려(?:져|줘|주|졌|집|요|지)|'
              r'커버(?:력)?(?:이|가|은|는|도)?\s*(?:정말|아주|너무|꽤|잘)?\s*'
              r'(?:좋|뛰어나|돼|되|됩|됐|해줘|해주)|'
              r'(?:완화|진정)(?:가|이|은|는|도)?\s*(?:잘\s*)?(?:돼|되|됩|됐)|줄어|줄었')
    return bool(re.search(rf'(?:{words}).{{0,18}}(?:{effect})', part))


def negative_concern(part, words):
    coverage = re.search(rf'(?:{words}).{{0,14}}(?:안\s*가려|못\s*가려|가려지지|커버.{{0,6}}(?:안|못|부족|약하|약해|아쉬))', part)
    if coverage and not re.search(r'않|없', part[coverage.end():coverage.end() + 12]):
        return True
    flare = re.search(rf'(?:{words}).{{0,12}}(?:심해졌|더\s*심해|올라왔|올라오|올라와|올라옵|생겼|났|뒤집)', part)
    if not flare:
        return False
    local = part[flare.start():flare.end() + 12]
    if re.search(r'안\s|않|없', local):
        return False
    background = re.search(r'원래|평소|피부라|피부인데|피부타입|생겨서|나서|올라와서|구매.*계기', part)
    usage = re.search(r'사용\s*후|사용하고|바른\s*후|바르고|쓰고|쓰니|사용하니|발랐더니|바르니|사용\s*뒤', part[max(0, flare.start() - 40):flare.start()])
    return not background or bool(usage)

def clauses(text):
    return [s.strip() for s in re.split(r'[.!?\n]+|(?:지만|그런데|하지만)', text or '') if s.strip()]

def extract_attributes(review):
    parts = clauses(review.get('content') or '')
    result = {'positive_concerns': [], 'negative_concerns': [], 'evidence': {}}
    for attr, (positive_patterns, negative_patterns) in ATTRIBUTES.items():
        positive, negative = [], []
        for part in parts:
            if not current_experience(part):
                continue
            pos = any(re.search(p, part) for p in positive_patterns)
            neg = any(re.search(p, part) for p in negative_patterns)
            if pos and not NEGATION.search(part) and not CONDITIONAL.search(part):
                positive.append(part[:180])
            if neg and not re.search(r'(?:무겁|답답|무너|부족|아쉬).{0,5}(?:않|없)', part):
                negative.append(part[:180])
        result[attr] = 4.0 if positive and not negative else 2.0 if negative and not positive else None
        result['evidence'][attr] = {'positive': positive[:2], 'negative': negative[:2]}
    for concern, words in CONCERNS.items():
        good = bad = False
        for part in parts:
            if not current_experience(part):
                continue
            if not re.search(words, part):
                continue
            if positive_concern(part, words) and not NEGATION.search(part) and not CONDITIONAL.search(part) and not re.search(r'부족|약하|약해|아쉬', part):
                good = True
            if negative_concern(part, words):
                bad = True
        if good and not bad and (review.get('rating') or 0) >= 4:
            result['positive_concerns'].append(concern)
        if bad:
            result['negative_concerns'].append(concern)
    result['wear'] = extract_wear([part for part in parts if current_experience(part)])
    return result

def get_shade_from_option(option):
    """Only explicit shade numbers. Brand shade 1 and vague beige are not 21/23."""
    matches = set(re.findall(r'(?<!\d)(21|23|25)(?=\s*호|[NnCcWw](?:\d)?\b|\b)', option or ''))
    return next(iter(matches)) if len(matches) == 1 else None

# Packaging, volume and bundle wording is not part of a shade name.
SHADE_NOISE = re.compile(r'\[[^\]]*\]|\([^)]*\)|\d+\s*(?:ml|mL|g|매|개입|종|입)|[+＋].*$')
SHADE_NUMBER = re.compile(r'(?<!\d)(\d{1,2})\s*호')
# Ordered light to dark. The first match wins, so 라이트베이지 is light, not mid.
# (단계, 패턴). Specific tone words are matched before the generic 베이지, so
# 샌드 베이지 is sand rather than plain beige; the level is stated, not positional.
BRIGHTNESS_WORDS = [
    (0, re.compile(r'라이트|light|밝은\s*피부|아이보리|ivory|페어|fair')),
    (1, re.compile(r'내추럴|natural|미디엄|medium|뉴트럴')),
    (3, re.compile(r'샌드|sand')),
    (4, re.compile(r'앰버|amber')),
    (5, re.compile(r'탄\b|tan|딥|deep|어두운\s*피부|다크|dark')),
    (2, re.compile(r'베이지|beige')),
]

def _clean_option(name):
    return re.sub(r'\s+', ' ', SHADE_NOISE.sub(' ', name or '')).strip()

def _is_shade_name(text):
    """A number alone does not make an option a shade: 01 코어썸 numbers a
    variant, not a tone. Require the 호 marker, a bare numeric code, or a
    colour/brightness word alongside it."""
    return bool(re.search(r'\d\s*호', text) or re.fullmatch(r'0*\d{1,3}', text)
                or _brightness_level(text) is not None)

def _option_number(text):
    """Brand shade numbering: 1호, 21호, 02, 001. Not converted to a 21/23/25 shade."""
    match = SHADE_NUMBER.search(text)
    if match:
        return int(match.group(1))
    match = re.fullmatch(r'0*(\d{1,3})', text)
    if match:
        return int(match.group(1))
    match = re.match(r'0(\d)(?!\d)', text)
    return int(match.group(1)) if match else None

def _brightness_level(text):
    for level, pattern in BRIGHTNESS_WORDS:
        if pattern.search(text):
            return level
    return None

def shade_lineup(option_counts, unavailable=()):
    """Order a product's own shade options from lightest to darkest.

    Uses only what the option names state: brand numbering, or brightness words
    when the options land on distinct levels. A brand's 1호 is never claimed to
    equal the 21호 of the cushion scale; only the order within this product is
    asserted. Packaging variants of one shade collapse onto a single rung, and
    names that state no shade at all are dropped. Returns None when the source
    states fewer than two rungs.

    Keep sold-out shades and their positions; stock status is displayed, not a
    reason to hide shade information. Prefer a buyable packaging variant when
    several options describe the same shade.
    """
    cleaned = defaultdict(Counter)
    for name, count in option_counts.items():
        text = _clean_option(name)
        if text:
            cleaned[text][name] += count
    for basis, resolve in [('number', _option_number), ('brightness_words', _brightness_level)]:
        rungs = defaultdict(Counter)
        for text, names in cleaned.items():
            level = resolve(text)
            if level is not None and (basis != 'number' or _is_shade_name(text)):
                rungs[level].update(names)
        if len(rungs) < 2:
            continue
        ordered = sorted(rungs)
        last = len(ordered) - 1
        options = []
        for index, level in enumerate(ordered):
            available = Counter({name: count for name, count in rungs[level].items()
                                 if name not in unavailable})
            name = (available or rungs[level]).most_common(1)[0][0]
            label = _clean_option(name)
            options.append({'name': name, 'label': label, 'position': round(index / last, 3),
                            'sold_out': not bool(available)})
        return {'basis': basis, 'options': options} if options else None
    return None

def profile_product_type(product):
    source_category = (product.get('profile_metadata') or {}).get('source_category')
    if source_category:
        return product_type(product.get('name'), source_category)
    return product.get('product_type') or product_type(product.get('name'), product.get('category'))

def input_hash(product, reviews):
    source = {k: product.get(k) for k in ['id', 'name', 'category', 'ingredients_raw', 'source_options']}
    source['source_category'] = (product.get('profile_metadata') or {}).get('source_category')
    ingredients = (product.get('profile_metadata') or {}).get('ingredient_source')
    source['ingredient_source'] = {k: ingredients.get(k) for k in ['status', 'source_url', 'entries', 'references', 'images']} if ingredients else None
    source['product_type'] = profile_product_type(product)
    data = [{k: r.get(k) for k in ['id', 'content', 'rating', 'skin_type', 'option_name']} for r in reviews]
    raw = json.dumps([VERSION, METADATA_REVISION, source, sorted(data, key=lambda r: r['id'])], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()

def build_profile(product, reviews):
    # A review ID contributes at most once, regardless of crawl sort.
    reviews = list({r['id']: r for r in reviews}.values())
    scores, evidence_ids, concern_ids = defaultdict(list), defaultdict(list), defaultdict(list)
    good, bad, skin_ratings = Counter(), Counter(), defaultdict(list)
    options, option_names = defaultdict(Counter), Counter()
    wear_items, option_wear_items = [], defaultdict(list)
    for review in reviews:
        attr = extract_attributes(review)
        wear_items.append((review['id'], attr['wear']))
        if (review.get('option_name') or '').strip():
            option_wear_items[review['option_name']].append((review['id'], attr['wear']))
        for name in ATTRIBUTES:
            if attr[name] is not None:
                scores[name].append(attr[name])
                if len(evidence_ids[name]) < 5:
                    evidence_ids[name].append(review['id'])
        good.update(attr['positive_concerns'])
        bad.update(attr['negative_concerns'])
        for concern in attr['positive_concerns']:
            if len(concern_ids[concern]) < 5:
                concern_ids[concern].append(review['id'])
        skin = SKIN_TYPES.get(review.get('skin_type'))
        rating = review.get('rating')
        if skin and isinstance(rating, (int, float)) and 1 <= rating <= 5:
            # Smoothed review satisfaction index, not skin safety probability.
            skin_ratings[skin].append(rating)
        option = review.get('option_name') or ''
        if option.strip():
            option_names[option] += 1
        shade = get_shade_from_option(option)
        if shade:
            options[shade][option] += 1
    # Prefer the current catalog over option names remembered from old reviews, so
    # options removed from the catalog are not offered. Sold-out shades still
    # belong to the product's lineup and carry an availability flag.
    source_options = product.get('source_options')
    unavailable = set()
    if source_options is not None:
        options, option_names = defaultdict(Counter), Counter()
        available_names = {o.get('name') for o in source_options if not o.get('sold_out')}
        for option in source_options:
            name = option.get('name') or ''
            if not name.strip():
                continue
            option_names[name] += 1
            if option.get('sold_out'):
                if name not in available_names:
                    unavailable.add(name)
                continue
            # Only a buyable option may claim a 21/23/25 shade the quiz matches on.
            shade = get_shade_from_option(name)
            if shade:
                options[shade][name] += 1
    profile = {name + '_score': round(mean(scores[name]), 2) if len(scores[name]) >= 3 else None for name in ATTRIBUTES}
    for skin in ['oily', 'dry', 'combination', 'sensitive']:
        vals = skin_ratings[skin]
        profile['compat_' + skin] = round(((sum(vals) + 3 * 5) / (len(vals) + 5) - 1) / 4, 3) if len(vals) >= 5 else None
    suitable_concerns = [c for c in CONCERNS if good[c] >= 3 and good[c] >= 2 * bad[c]]
    profile.update({
        # The crawler infers this from Olive Young's own category. products.category
        # holds a display group ('쿠션/파운데이션'), so re-inferring from it fed the
        # word 쿠션 back in and turned every foundation, stick and powder into a
        # cushion. Prefer the preserved source category, then the crawler's type.
        'product_type': profile_product_type(product),
        'suitable_skin_types': [s for s in skin_ratings if len(skin_ratings[s]) >= 5 and mean(skin_ratings[s]) >= 4],
        'suitable_concerns': suitable_concerns, 'suitable_shades': sorted(options),
        'shade_options': {s: counts.most_common(1)[0][0] for s, counts in options.items()},
        'ingredient_level': '성분 확인' if product.get('ingredients_raw') and (
            not (product.get('profile_metadata') or {}).get('ingredient_source') or
            (product['profile_metadata']['ingredient_source'].get('status') in ['collected', 'partial'])) else None,
        'profile_metadata': {
            'version': VERSION, 'analyzed_count': len(reviews), 'input_hash': input_hash(product, reviews),
            'metadata_revision': METADATA_REVISION,
            'source_category': (product.get('profile_metadata') or {}).get('source_category'),
            'ingredient_source': (product.get('profile_metadata') or {}).get('ingredient_source'),
            'evidence_counts': {k: len(scores[k]) for k in ATTRIBUTES}, 'evidence_review_ids': dict(evidence_ids),
            'concern_evidence_ids': dict(concern_ids),
            'wear_attributes': summarize_wear(wear_items),
            'option_wear': {name: {'review_count': len(items), 'attributes': summarize_wear(items)}
                            for name, items in sorted(option_wear_items.items())},
            'skin_review_counts': {k: len(v) for k, v in skin_ratings.items()},
            'positive_concern_counts': dict(good), 'negative_concern_counts': dict(bad),
            'shade_source': 'catalog' if source_options is not None else 'historical_reviews',
            # Order within this product only; a brand's 1호 is not the 21호 of the cushion scale.
            'shade_lineup': shade_lineup(option_names, unavailable),
        },
    })
    return profile
