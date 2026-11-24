"""Explicit cosmetic wear expressions. No benefit inferred from a product name."""
from __future__ import annotations

import re
from statistics import mean

WEAR_ATTRIBUTES = ('naturalness', 'transfer_resistance', 'smoothness')
TELL = r'(?:화장(?:한|하는)?\s*티|바른\s*티|(?<![가-힣])티)'
# Keep these endings on the clause they qualify. Dropping '했는데' from
# '안 묻어난다고 했는데' used to turn a quoted promise into observed wear.
CLAUSE_BOUNDARY = re.compile(r'[.!?\n,;]+|그런데|하지만|그치만|'
                            r'(?:했|었|았|였|이)?는데|(?:은데|운데)(?=\s|[.!?,;]|$)|텐데|지만|'
                            r'(?<=[요다])[ \t]+(?=(?:그리고|또한|무엇보다)\s)|'
                            r'(?<!\S)(?:다만|대신)\s+')
NON_OBSERVATION = re.compile(r'다고|다며|다길래|다던|다는데|'
                             r'다는\s*(?:말|후기|광고|설명)|텐데|'
                             r'(?:있|없|되|돼|해|하)어?야\s*(?:하|한|합|해|되|돼)|'
                             r'(?:있|없)어야')
LIST_NOUN = r'(?:모공|홍조|여드름|트러블|잡티|주름|다크서클|흉터|커버력|지속력|발림성|수분감)'


def review_clauses(text, split_commas=False):
    """Original-text clauses, with quotation/concession endings still attached."""
    parts, start = [], 0
    for match in CLAUSE_BOUNDARY.finditer(text or ''):
        before = text[start:match.start()]
        new_conclusion = bool(re.fullmatch(r'[ \t]+', match.group()))
        if new_conclusion and not NON_OBSERVATION.search(before):
            # Only release an explicitly new conclusion from an unobserved
            # prefix. Ordinary coordinated descriptions keep their context.
            continue
        if (not split_commas and re.fullmatch(r',+', match.group())
                and re.search(rf'{LIST_NOUN}\s*$', before)
                and re.match(rf'\s*{LIST_NOUN}', text[match.end():])):
            # '모공, 홍조도 커버돼요' has one shared predicate. Splitting the
            # list would discard pore coverage from concern extraction.
            continue
        if ((new_conclusion or match.group().endswith(('는데', '은데', '운데')))
                and re.search(r'기존|예전|이전|다른\s*제품|타사', before)
                and not re.search(r'보다|비해', before)
                and not re.match(r'\s*(?:이\s*제품|이건|이거|이번|지금|현재)', text[match.end():])):
            # '기존 제품을 써왔는데 두껍게 발렸어요' retains its old-product
            # subject until the reviewer explicitly switches to this product.
            continue
        end = match.end() if match.group().endswith(('는데', '은데', '운데', '텐데', '지만')) else match.start()
        part = text[start:end].strip()
        if part:
            parts.append(part)
        start = match.end()
    tail = (text or '')[start:].strip()
    if tail:
        parts.append(tail)
    return parts


PATTERNS = {
    'naturalness': (
        [r'(?<!부)자연스러(?:워|웠)', r'부자연스럽지\s*않', r'(?<!부)자연스러운\s*(?:느낌|피부\s*표현|표현|마무리|발색|색감)',
         rf'{TELL}(?:가|도|는)?\s*(?:전혀|거의|별로|많이)?\s*(?:안\s*(?:나|남|납)|나지\s*않|없)',
         r'(?:원래|본래|제)\s*피부\s*(?:같아|같이|처럼)'],
        [r'부자연스러(?:워|웠)', r'부자연스러운\s*(?:느낌|표현|마무리|발색|색감)', r'(?<!부)자연스럽지\s*않',
         rf'{TELL}(?:가|도|는)?\s*(?:너무|많이|확|엄청|좀)?\s*(?:나서|나요|납니다|나는\s*편|났어요)']),
    'transfer_resistance': (
        [r'묻(?:어\s*나)?(?:지|지는)\s*(?:잘\s*)?않',
         r'(?:안|덜)\s*묻(?:어|어나|고|는|어요|습니다)',
         r'묻(?:어\s*나)?(?:는\s*(?:감|것|게|부분))?(?:음|남|감)?(?:이|은|는|도|가)?\s*(?:전혀|하나도|거의|많이)?\s*(?:없|적)',
         r'묻어\s*남(?:이|은|는|도|가)?\s*(?:전혀|하나도|거의|별로)?\s*없'],
        [r'묻어\s*(?:나와|나요|나오|나는|납니다|났|나고|나서|나네요|나더)', r'묻(?:어요|는다|는\s*편|어서)',
         r'묻(?:음|어남)(?:이|은|가)?\s*(?:좀\s*)?(?:많|심|있)']),
    'smoothness': (
        [r'(?:들뜨|뭉치)(?:지|지는|지도)\s*않', r'(?:들뜸|뭉침|끼임)(?:현상)?(?:이|은|도|가)?\s*(?:전혀|거의|많이|별로)?\s*(?:없|적)',
         r'(?:모공|주름|수염).{0,12}끼(?:지|지는)\s*않',
         r'(?:모공|주름|수염).{0,12}안\s*끼',
         r'(?:잘\s*)?안\s*떠(?:요|서|도|서요|$)',
         r'(?:화장|얼굴|피부|베이스).{0,12}뜨(?:지|지는|지도)\s*않'],
        [r'들뜨(?:고|는|네요|더|거나|어서|어요)', r'들떴', r'뭉치(?:고|는|네요|더|거나)',
         r'(?:들뜸|뭉침|끼임)(?:이|은|도|가)?\s*(?:조금|좀|많이|많|심|있)',
         r'(?:모공|주름|수염).{0,12}끼(?:어요|네요|더|고|는)']),
}
COMPILED = {key: tuple([re.compile(p) for p in patterns] for patterns in pair) for key, pair in PATTERNS.items()}
HYPOTHETICAL = re.compile(r'원하|원했|바랄|바라|좋겠|기대|예정|구매\s*전|후기.{0,12}(?:보니|읽)|'
                            r'많이\s*바르면|잘못\s*바르면|두껍게.{0,10}바르면|잘해준다면|(?:티가\s*날|들뜰|뭉칠)\s*수|'
                            r'스러워야|웠다면|부담스러울까|남성분들.{0,20}(?:안\s*꾸미|말성|망설)|어색했|거짓말|'
                            r'메이크업\s*제품을\s*바르면|사용하지\s*않으면|들뜨면|밝으면|어두우면')
DOUBLE_NEGATION = re.compile(r'(?:않|없|안\s*묻|안\s*나).{0,14}(?:아니|않|없)')
TRANSFER_TARGET = re.compile(r'퍼프|스[펀폰]지|브러[시쉬]|손(?:에|을)|케이스|용기|'
                             r'마스크|옷|흰티|셔츠|휴지|핸드폰|베개|문질')
PICKUP_TARGET = re.compile(r'퍼프|스[펀폰]지|브러[시쉬]|손(?:에|을)|케이스|용기')


def transfer_pickup(text, start):
    # Decide for each claim, not the entire review: a puff pickup and a mask
    # transfer may occur in the very same clause.
    targets = list(TRANSFER_TARGET.finditer(text, max(0, start - 80), start))
    return bool(targets and PICKUP_TARGET.fullmatch(targets[-1].group()))


def negated_bad(text, end, key):
    suffix = text[end:end + 30]
    # Only a grammatical continuation can negate the matched claim. An
    # unrelated '지속력이 좋지 않아요' must not erase actual mask transfer.
    if re.match(r'\s*(?:(?:지|지는|지도|게|건|거|것|감|현상|부분|이|은|는|도|가|을|를|전혀|거의|별로|많이|하나도)\s*)*'
                r'(?:없|않|적|아니|느끼지\s*못|못\s*느)', suffix):
        return True
    if re.match(r'\s*(?:그런\s*)?(?:거|것|증상|현상)(?:도|이|은|는)?\s*'
                r'(?:전혀|거의)?\s*(?:없|나타나지\s*않)', suffix):
        return True
    if (text[:end].endswith(('거나', '고', '는')) and re.match(
            r'\s*[^.!?;,]{0,24}(?:증상|현상)(?:이|도)?\s*나타나지\s*않', suffix)):
        return True
    return key == 'smoothness' and bool(re.match(
        r'\s*(?:뭉침|들뜸|끼임)(?:이|도|은|가)?\s*(?:거의|별로|많이)?\s*(?:없|적)', suffix))


def extract_wear(parts):
    result = {key: {'positive': [], 'negative': []} for key in WEAR_ATTRIBUTES}
    for original in parts:
        # A sentence may describe both favourable and unfavourable wear.
        for part in review_clauses(original, split_commas=True):
            text = re.sub(r'\s+', ' ', part).strip()
            if not text or NON_OBSERVATION.search(text) or HYPOTHETICAL.search(text) or DOUBLE_NEGATION.search(text):
                continue
            if re.search(r'(?:다른\s*(?:제품|쿠션)|타사|기존|예전|바꿔|바꾸|갈아|그건|그\s*제품|비비크림\s*같은)', text) and not re.search(r'보다|비해', text):
                continue
            if re.search(r'(?:티가?\s*나|들뜨|뭉치).{0,24}(?:구매|구입|사봤|샀)', text):
                continue
            if re.search(r'(?:들뜨는|들뜬|뭉치는)\s*피부', text):
                continue
            for key, (good_patterns, bad_patterns) in COMPILED.items():
                if key == 'naturalness' and re.search(r'자연스러.{0,12}(?:않|없|아니)', text):
                    good = []
                else:
                    good = [m.span() for rx in good_patterns for m in rx.finditer(text)
                            if not re.search(r'(?:지\s*않|는\s*건\s*아니|지는\s*않)', text[m.end():m.end() + 10])]
                # A negated bad root is already represented by a positive span.
                bad = [m.span() for rx in bad_patterns for m in rx.finditer(text)
                       if not any(a <= m.start() < b or m.start() <= a < m.end() for a, b in good)
                       and not negated_bad(text, m.end(), key)]
                # '부자연스러워요' contains '자연스러워': never count both.
                if key == 'naturalness' and re.search(r'부자연스러(?:워|웠)|(?<!부)자연스럽지\s*않', text):
                    good = []
                    bad = [(0, len(text))]
                if key == 'smoothness' and re.search(r'하얗|밝|피부색|피부톤|목이랑', text):
                    # Colour mismatch is not evidence of physical creasing.
                    good = [span for span in good if re.search(r'들뜨|들뜸|뭉치|뭉침|끼임|끼지', text[span[0]:span[1]])]
                if key == 'transfer_resistance':
                    good = [span for span in good if not transfer_pickup(text, span[0])]
                    bad = [span for span in bad if not transfer_pickup(text, span[0])]
                for polarity, spans in [('positive', good), ('negative', bad)]:
                    if spans and text not in result[key][polarity]:
                        result[key][polarity].append(text[:220])
    return result


def summarize_wear(items):
    """Each item is (review id, extracted wear). A review contributes at most once."""
    unique = dict(items)
    result = {}
    for key in WEAR_ATTRIBUTES:
        good, bad, mixed, values = [], [], [], []
        for rid, extracted in unique.items():
            entry = extracted[key]
            pos, neg = bool(entry['positive']), bool(entry['negative'])
            if pos and neg:
                mixed.append(str(rid))
            elif pos:
                good.append(str(rid)); values.append(4.0)
            elif neg:
                bad.append(str(rid)); values.append(2.0)
        n = len(values)
        result[key] = {'score': round(mean(values), 2) if n >= 3 else None,
                       'evidence_count': n, 'positive_count': len(good), 'negative_count': len(bad),
                       'mixed_count': len(mixed), 'positive_review_ids': good[:5], 'negative_review_ids': bad[:5],
                       'mixed_review_ids': mixed[:3]}
    return result
