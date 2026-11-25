"""Precompute source-checked review summaries without AI calls or database writes.

Only the existing score evidence samples are read. Full review text and author
are never written to the public artifact; short, unchanged clauses are optional.
The browser must verify the current product, profile, IDs and raw text hashes
before using these classifications. Scores and profile versions are untouched.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.profiles import ATTRIBUTES, VERSION, extract_attributes
from pipeline.wear import WEAR_ATTRIBUTES
from shared import ROOT, database, read_all, utc_now, write_json

METHOD = 'rules-extractive-v1'
KEYS = (*ATTRIBUTES, *WEAR_ATTRIBUTES)
# Additional summary-only caution. Existing score rules are deliberately not
# changed: a quoted review can still be present in the original evidence panel,
# but must not become this summary's assertion about observed use.
ATTRIBUTED_REVIEW = re.compile(r'(?:다는|다던|던|다고|라던)\s*(?:리뷰|후기|말|광고|설명)|'
                              r'(?:리뷰|후기).{0,12}(?:많던|많다|많아서|많아|하길래|라길래)|'
                              r'(?:없|있|좋|안\s*묻)다\s*해서')
NEGATED_NEGATIVE = re.compile(
    r'두껍게\s*발(?:리|라|린).{0,24}(?:않|없|아니|적|안\s*들)|'
    r'안\s*(?:뭉치|들뜨|끼)|'
    r'(?:들뜨|들뜸|뭉치|뭉침|끼|끼임).{0,32}(?:없|않|적|아니|덜|못\s*느)|'
    r'(?:답답|무겁|무거).{0,12}(?:없|않|아니)|짧(?:지|진)\s*않|'
    r'아쉬운\s*건\s*못|묻어나(?:는|오는)\s*(?:정도|불편함|것도|게|것).{0,16}(?:적|개선|없|않)|'
    r'덜\s*티나|안\s*묻어?나')
UNOBSERVED = re.compile(r'기대\s*(?:됩|됨|해|하고|되)|어떨지\s*기대|줄\s*알았|걱정이\s*있었|'
                        r'(?:전에|이전에|예전에)\s*(?:쓰던|사용하던)|과거\s*사용|'
                        r'일반\s*파우더는|가루\s*타입\s*파우더는|미닉(?:은|이|의)|'
                        r'남들\s*바르는|비비\s*바르자니|못\s*바르시던')
ADVICE = re.compile(r'묻지\s*않게\s*(?:잘)?하|조심하|주의하')
CONDITIONAL_ADVICE = re.compile(r'(?:하|바르|발라|뿌리|찍|두드리).{0,5}(?:시면|으면|면)')
HYPOTHETICAL_CONTEXT = re.compile(r'이면|라면|다면|으면|경우|같았|걱정|우려|좋겠|원했|바랐|'
                                  r'(?<!표)면(?=\s|[,;.!?])')
PAST_PRODUCT_CONTEXT = re.compile(r'(?:원래|기존|예전|이전|전에|작년).{0,80}(?:사용했|썼|쓰던|써왔|쓰고|사용하던)|'
                                  r'제\s*(?:껄|꺼|걸로|것으로)', re.S)
OTHER_PRODUCT_PREP = re.compile(r'(?:파우더|픽서|미스트|프라이머|다른\s*제품|타사).{0,24}'
                                r'(?:처리|뿌리|사용|바르|마무리|한\s*후|후)')
PICKUP = re.compile(r'패드에\s*(?:잘\s*)?안\s*묻|(?:퍼프|패드|스[펀폰]지|브러[시쉬]).{0,60}잘\s*묻어?나', re.S)
BACKGROUND = re.compile(r'(?:지성|건성|피부).{0,16}(?:이라|라서|인데|때문)|(?:원래|평소).{0,25}(?:무너|지워|커버)|고민이었')
INTENT = re.compile(r'찾고\s*(?:있었|있)|구매.*(?:이유|계기)|구매(?:했|하려|하시려)|구입(?:했|하려)|선물하기|원해서|사\s*줬')
QUOTE_OFF_TOPIC = re.compile(r'구매|구입|선물|성분|저자극|임상|테스트|피부과|치료|안전|주름\s*개선|미백\s*효과')
FRAGMENT = re.compile(r'^(?:은|는|이|가|을|를|에|도|만|와|과|의|로|으로|에서|까지|부터|처럼|보다|지만|는데|은데|운데)(?:\s|$)|^[)\],\.…]|^(?:안\s*그러면|그러면|확률로|단점\s*:)')
CLEANSING = re.compile(r'클렌징|세안|지우는\s*것도.{0,18}지워')
PACKAGING_SPILL = re.compile(r'분해되|파손|깨졌|세면대|싱크대|용기.{0,20}(?:터|새서|새는)')


def evidence_specs(meta):
    """Keep the original full sample, including negative and mixed wear IDs."""
    for key in ATTRIBUTES:
        yield '', key, list(dict.fromkeys(map(str, meta.get('evidence_review_ids', {}).get(key, [])))), meta.get('evidence_counts', {}).get(key, 0)
    for scope, attributes in [('', meta.get('wear_attributes', {})), *[
            (name, group.get('attributes', {})) for name, group in meta.get('option_wear', {}).items()]]:
        for key in WEAR_ATTRIBUTES:
            entry = attributes.get(key, {})
            ids = [str(rid) for polarity in ('positive', 'negative', 'mixed')
                   for rid in entry.get(polarity + '_review_ids', [])]
            yield scope, key, list(dict.fromkeys(ids)), entry.get('evidence_count', 0) + entry.get('mixed_count', 0)


def summary_source(product_id, key, review, scope=''):
    if str(review.get('product_id')) != str(product_id):
        raise ValueError('Cross-product review ID in summary evidence')
    content = review.get('content')
    if not isinstance(content, str) or not content.strip():
        raise ValueError('Missing original text in summary evidence')
    if scope and review.get('option_name') != scope:
        raise ValueError('Wrong option scope in summary evidence')
    extracted = extract_attributes(review)
    evidence = extracted['evidence'][key] if key in ATTRIBUTES else extracted['wear'][key]
    positive, negative = evidence['positive'], evidence['negative']
    polarity = 'mixed' if positive and negative else 'positive' if positive else 'negative' if negative else None
    if polarity is None:
        raise ValueError(f'Unclassified original evidence: {product_id}/{key}/{review["id"]}')
    # The classifiers may normalize whitespace or truncate clauses. Never
    # present that transformed text as a quotation from the original review.
    candidates = list(dict.fromkeys(part for part in [*negative, *positive]
                                   if part in content and len(part) <= 100
                                   and not FRAGMENT.search(part)
                                   and not QUOTE_OFF_TOPIC.search(part)
                                   and part.count('(') == part.count(')')
                                   and part.count('[') == part.count(']')))
    excerpts = sorted(candidates, key=content.index)[:2]
    by_polarity = {name: [part for part in excerpts if part in parts]
                   for name, parts in [('positive', positive), ('negative', negative)]}
    return {'id': str(review['id']), 'sha256': hashlib.sha256(content.encode('utf-8')).hexdigest(),
            'polarity': polarity, 'excerpts': excerpts, 'excerpts_by_polarity': by_polarity,
            'semantic_verified': not (UNOBSERVED.search(content)
                or PAST_PRODUCT_CONTEXT.search(content)
                or (key == 'transfer_resistance' and (PICKUP.search(content) or PACKAGING_SPILL.search(content)))
                or any(ATTRIBUTED_REVIEW.search(part) or PICKUP.search(part) for part in [*positive, *negative])
                or any(NEGATED_NEGATIVE.search(part) for part in negative)
                or any(BACKGROUND.search(part) for part in negative)
                or (key == 'longevity' and any(CLEANSING.search(part) for part in negative))
                or any(ADVICE.search(part) or INTENT.search(part) for part in positive)
                or any(CONDITIONAL_ADVICE.search(part) for part in [*positive, *negative])
                or any(HYPOTHETICAL_CONTEXT.search(part) or OTHER_PRODUCT_PREP.search(part)
                       for part in [*positive, *negative])
                or (key == 'coverage' and '어쉽' in content)
                or (key == 'coverage' and polarity == 'negative'
                    and re.search(r'자연스럽게.{0,12}커버|커버(?:가|도)?\s*(?:되네|돼요|됩니다)', content)))}


def build_summary_product(product, reviews):
    meta = product.get('profile_metadata') or {}
    if meta.get('version') != VERSION or not meta.get('input_hash'):
        raise ValueError('Current profile with input_hash required')
    by_id = {str(review['id']): review for review in reviews}
    result = {'input_hash': meta['input_hash'], 'attributes': {}, 'options': {}}
    for scope, key, ids, total in evidence_specs(meta):
        if any(rid not in by_id for rid in ids):
            raise ValueError(f'Missing summary source: {product["id"]}/{key}')
        sources = [summary_source(product['id'], key, by_id[rid], scope) for rid in ids]
        entry = {'totalEvidenceCount': total, 'sources': sources}
        if key in WEAR_ATTRIBUTES:
            attributes = meta.get('option_wear', {}).get(scope, {}).get('attributes', {}) if scope else meta.get('wear_attributes', {})
            counts = attributes.get(key, {})
            entry['overallPolarityCounts'] = {polarity: counts.get(polarity + '_count', 0)
                                              for polarity in ('positive', 'negative', 'mixed')}
        if scope:
            result['options'].setdefault(scope, {})[key] = entry
        else:
            result['attributes'][key] = entry
    return result


def main():
    db = database()
    products = list(read_all(db, 'products', 'id,profile_metadata'))
    artifact = {'schema_version': 1, 'method': METHOD, 'profile_version': VERSION,
                'generated_at': utc_now(), 'products': {}}
    review_count = reference_count = 0
    for product in products:
        ids = sorted({rid for _, _, ids, _ in evidence_specs(product.get('profile_metadata') or {}) for rid in ids})
        reviews = []
        for offset in range(0, len(ids), 100):
            # Explicit public columns only. Do not read author or mutate rows.
            response = db.table('reviews').select('id,product_id,content,option_name').eq(
                'product_id', product['id']).in_('id', ids[offset:offset + 100]).execute()
            reviews.extend(response.data or [])
        value = build_summary_product(product, reviews)
        artifact['products'][product['id']] = value
        review_count += len(reviews)
        reference_count += sum(len(entry['sources']) for entry in value['attributes'].values())
        reference_count += sum(len(entry['sources']) for attrs in value['options'].values() for entry in attrs.values())
    target = ROOT / 'web/public/review-summaries.json'
    write_json(target, artifact)
    print(f'{len(products)} products; {review_count} unique product/review sources; {reference_count} attribute references; DB writes 0')
    print(target)


if __name__ == '__main__':
    main()
