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

VERSION = 'rules-ko-v1'
# Shape of profile_metadata. Bumping this rebuilds stored profiles on the next run
# without changing VERSION, so the deployed site keeps reading current profiles.
METADATA_REVISION = 2
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

def clauses(text):
    return [s.strip() for s in re.split(r'[.!?\n]+|(?:지만|그런데|하지만)', text or '') if s.strip()]

def extract_attributes(review):
    parts = clauses(review.get('content') or '')
    result = {'positive_concerns': [], 'negative_concerns': [], 'evidence': {}}
    for attr, (positive_patterns, negative_patterns) in ATTRIBUTES.items():
        positive, negative = [], []
        for part in parts:
            pos = any(re.search(p, part) for p in positive_patterns)
            neg = any(re.search(p, part) for p in negative_patterns)
            if pos and not NEGATION.search(part):
                positive.append(part[:180])
            if neg and not re.search(r'(?:무겁|답답|무너|부족|아쉬).{0,5}(?:않|없)', part):
                negative.append(part[:180])
        result[attr] = 4.0 if positive and not negative else 2.0 if negative and not positive else None
        result['evidence'][attr] = {'positive': positive[:2], 'negative': negative[:2]}
    for concern, words in CONCERNS.items():
        good = bad = False
        for part in parts:
            if not re.search(words, part):
                continue
            if re.search(r'(?:가려|커버|완화|진정|줄어|줄었)', part) and not NEGATION.search(part):
                good = True
            if re.search(r'(?:심해|심해졌|올라|났|생겼|뒤집|못\s*가|안\s*가|가려지지|커버.{0,4}(?:안|못))', part) and not re.search(r'(?:안|않|없).{0,3}(?:났|생겼|올라)', part):
                bad = True
        if good and not bad and (review.get('rating') or 0) >= 4:
            result['positive_concerns'].append(concern)
        if bad:
            result['negative_concerns'].append(concern)
    return result

def get_shade_from_option(option):
    """Only explicit shade numbers. Brand shade 1 and vague beige are not 21/23."""
    matches = set(re.findall(r'(?<!\d)(21|23|25)(?=\s*호|[NnCcWw](?:\d)?\b|\b)', option or ''))
    return next(iter(matches)) if len(matches) == 1 else None

def input_hash(product, reviews):
    source = {k: product.get(k) for k in ['id', 'name', 'category', 'ingredients_raw', 'source_options']}
    data = [{k: r.get(k) for k in ['id', 'content', 'rating', 'skin_type', 'option_name']} for r in reviews]
    raw = json.dumps([VERSION, METADATA_REVISION, source, sorted(data, key=lambda r: r['id'])], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()

def build_profile(product, reviews):
    # A review ID contributes at most once, regardless of crawl sort.
    reviews = list({r['id']: r for r in reviews}.values())
    scores, evidence_ids, concern_ids = defaultdict(list), defaultdict(list), defaultdict(list)
    good, bad, skin_ratings = Counter(), Counter(), defaultdict(list)
    options = defaultdict(Counter)
    for review in reviews:
        attr = extract_attributes(review)
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
        shade = get_shade_from_option(option)
        if shade:
            options[shade][option] += 1
    # Prefer current source options; omit sold-out options and never synthesize unavailable shades.
    source_options = product.get('source_options')
    if source_options is not None:
        options = defaultdict(Counter)
        for option in source_options:
            shade = get_shade_from_option(option.get('name'))
            if shade and not option.get('sold_out'):
                options[shade][option['name']] += 1
    profile = {name + '_score': round(mean(scores[name]), 2) if len(scores[name]) >= 3 else None for name in ATTRIBUTES}
    for skin in ['oily', 'dry', 'combination', 'sensitive']:
        vals = skin_ratings[skin]
        profile['compat_' + skin] = round(((sum(vals) + 3 * 5) / (len(vals) + 5) - 1) / 4, 3) if len(vals) >= 5 else None
    suitable_concerns = [c for c in CONCERNS if good[c] >= 3 and good[c] >= 2 * bad[c]]
    profile.update({
        'product_type': product_type(product.get('name'), product.get('category')),
        'suitable_skin_types': [s for s in skin_ratings if len(skin_ratings[s]) >= 5 and mean(skin_ratings[s]) >= 4],
        'suitable_concerns': suitable_concerns, 'suitable_shades': sorted(options),
        'shade_options': {s: counts.most_common(1)[0][0] for s, counts in options.items()},
        'ingredient_level': '성분 확인' if product.get('ingredients_raw') else None,
        'profile_metadata': {
            'version': VERSION, 'analyzed_count': len(reviews), 'input_hash': input_hash(product, reviews),
            'evidence_counts': {k: len(scores[k]) for k in ATTRIBUTES}, 'evidence_review_ids': dict(evidence_ids),
            'concern_evidence_ids': dict(concern_ids),
            'skin_review_counts': {k: len(v) for k, v in skin_ratings.items()},
            'positive_concern_counts': dict(good), 'negative_concern_counts': dict(bad),
            'shade_source': 'catalog' if source_options is not None else 'historical_reviews',
        },
    })
    return profile
