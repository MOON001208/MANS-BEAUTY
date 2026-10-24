"""Explicit cosmetic wear expressions. No benefit inferred from a product name."""
from __future__ import annotations

import re
from statistics import mean

WEAR_ATTRIBUTES = ('naturalness', 'transfer_resistance', 'smoothness')
TELL = r'(?:화장(?:한|하는)?\s*티|바른\s*티|(?<![가-힣])티)'
PATTERNS = {
    'naturalness': (
        [r'(?<!부)자연스러(?:워|웠)', r'부자연스럽지\s*않', r'(?<!부)자연스러운\s*(?:느낌|피부\s*표현|표현|마무리|발색|색감)',
         rf'{TELL}(?:가|도|는)?\s*(?:전혀|거의|별로|많이)?\s*(?:안\s*나|나지\s*않|없)',
         r'(?:원래|본래|제)\s*피부\s*(?:같아|같이|처럼)'],
        [r'부자연스러(?:워|웠)', r'부자연스러운\s*(?:느낌|표현|마무리|발색|색감)', r'(?<!부)자연스럽지\s*않',
         rf'{TELL}(?:가|도|는)?\s*(?:너무|많이|확|엄청|좀)?\s*(?:나서|나요|납니다|나는\s*편|났어요)']),
    'transfer_resistance': (
        [r'묻(?:어\s*나)?(?:지|지는)\s*(?:잘\s*)?않',
         r'(?:안|덜)\s*묻(?:어|어나|고|는|어요|습니다)',
         r'묻(?:어\s*나)?(?:는\s*(?:감|것|게|부분))?(?:음|남|감)?(?:이|은|는|도|가)?\s*(?:전혀|하나도|거의|많이)?\s*(?:없|적)'],
        [r'묻어\s*(?:나와|나요|나오|나는|납니다|났)', r'묻(?:어요|는다|는\s*편)',
         r'묻(?:음|어남)(?:이|은|가)?\s*(?:좀\s*)?(?:많|심|있)']),
    'smoothness': (
        [r'(?:들뜨|뭉치)(?:지|지는|지도)\s*않', r'(?:들뜸|뭉침|끼임)(?:현상)?(?:이|은|도|가)?\s*(?:전혀|거의|많이|별로)?\s*(?:없|적)',
         r'(?:모공|주름|수염).{0,12}끼(?:지|지는)\s*않',
         r'(?:모공|주름|수염).{0,12}안\s*끼',
         r'(?:화장|얼굴|피부|베이스).{0,12}뜨(?:지|지는|지도)\s*않'],
        [r'들뜨(?:고|는|네요|더|거나|어서|어요)', r'들떴', r'뭉치(?:고|는|네요|더|거나)',
         r'(?:들뜸|뭉침|끼임)(?:이|은|도|가)?\s*(?:조금|좀|많이|많|심|있)',
         r'(?:모공|주름|수염).{0,12}끼(?:어요|네요|더|고|는)']),
}
COMPILED = {key: tuple([re.compile(p) for p in patterns] for patterns in pair) for key, pair in PATTERNS.items()}
HYPOTHETICAL = re.compile(r'원하|원했|바랄|바라|좋겠|기대|예정|구매\s*전|후기.{0,12}(?:보니|읽)|'
                            r'많이\s*바르면|잘못\s*바르면|두껍게.{0,10}바르면|잘해준다면|(?:티가\s*날|들뜰|뭉칠)\s*수|'
                            r'스러워야|웠다면|부담스러울까|남성분들.{0,20}(?:안\s*꾸미|말성|망설)|어색했|거짓말|'
                            r'메이크업\s*제품을\s*바르면|사용하지\s*않으면|들뜨면')
DOUBLE_NEGATION = re.compile(r'(?:않|없|안\s*묻|안\s*나).{0,14}(?:아니|않|없)')


def extract_wear(parts):
    result = {key: {'positive': [], 'negative': []} for key in WEAR_ATTRIBUTES}
    for original in parts:
        # A sentence may describe both favourable and unfavourable wear.
        for part in re.split(r'[,;]|(?:했|었|았|였|이)?는데|\s(?:다만|대신)\s', original):
            text = re.sub(r'\s+', ' ', part).strip()
            if not text or HYPOTHETICAL.search(text) or DOUBLE_NEGATION.search(text):
                continue
            if re.search(r'(?:다른\s*(?:제품|쿠션)|타사|기존|예전|바꿔|바꾸|갈아|그건|그\s*제품|비비크림\s*같은)', text) and not re.search(r'보다|비해', text):
                continue
            if re.search(r'(?:티가?\s*나|들뜨|뭉치).{0,24}(?:구매|구입|사봤|샀)', text):
                continue
            if re.search(r'(?:들뜨는|들뜬|뭉치는)\s*피부', text):
                continue
            for key, (good_patterns, bad_patterns) in COMPILED.items():
                if key == 'transfer_resistance' and re.search(r'손에|손을|케이스|용기', text) and not re.search(r'마스크|옷|흰티|셔츠|휴지|핸드폰|베개|문질', text):
                    continue
                if key == 'naturalness' and re.search(r'자연스러.{0,12}(?:않|없|아니)', text):
                    good = []
                else:
                    good = [m.span() for rx in good_patterns for m in rx.finditer(text)
                            if not re.search(r'(?:지\s*않|는\s*건\s*아니|지는\s*않)', text[m.end():m.end() + 10])]
                # A negated bad root is already represented by a positive span.
                bad = [m.span() for rx in bad_patterns for m in rx.finditer(text)
                       if not any(a <= m.start() < b or m.start() <= a < m.end() for a, b in good)
                       and not re.search(r'없|않|적|아니|느끼지\s*못|못\s*느', text[m.end():m.end() + 22])]
                # '부자연스러워요' contains '자연스러워': never count both.
                if key == 'naturalness' and re.search(r'부자연스러(?:워|웠)|(?<!부)자연스럽지\s*않', text):
                    good = []
                    bad = [(0, len(text))]
                if key == 'smoothness' and re.search(r'하얗|밝|피부색|피부톤|목이랑', text):
                    # Colour mismatch is not evidence of physical creasing.
                    good = [span for span in good if re.search(r'들뜨|들뜸|뭉치|뭉침|끼임|끼지', text[span[0]:span[1]])]
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
