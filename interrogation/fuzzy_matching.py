"""
Tools for fuzzy-matching short customer input (handful of words) against a pre-configured list of terms (typically
one to three words). Allows for customer entering more than one term at once.
"""
import itertools
import re
from typing import List, NamedTuple, Iterable, Dict, Tuple

from Levenshtein import ratio as lratio


def get_all_ngrams(text: str) -> Iterable[str]:
    """Returns generator over all 1-, 2-, and 3-grams of words from the text"""
    lst = text.split(' ')
    for i in range(0, len(lst)):
        for j in range(i+1, min(len(lst) + 1, i+4)):
            yield ' '.join(lst[i:j])


class Slice(NamedTuple):
    """Helper class to represent a slice of the string. Python does have a built-in slice object,
    but this little class was convenient so we could add overlap() and len() methods.
    """
    l: int
    r: int

    def overlap(self, s: 'Slice') -> bool:
        return self.r > s.l and self.l < s.r

    def len(self):
        return self.r - self.l


class Match(NamedTuple):
    choice: str     # which choice was matched
    score: float    # how good was match
    slice: Slice    # what slice of query string was matched


def get_non_overlaps(lst: Iterable[Slice]) -> Iterable[List[Slice]]:
    """
    Given a list of slices, returns an iterable over all non-empty sorted lists of non-overlapping slices from
    the original list.
    """
    lst = sorted(lst)
    yield from _get_non_overlaps([], lst)


def _get_non_overlaps(curr: List[Slice], remain: List[Slice]) -> Iterable[List[Slice]]:
    if curr:
        yield curr
    for i, s in enumerate(remain, 1):
        yield from _get_non_overlaps(curr + [s], [s1 for s1 in remain[i:] if not s1.overlap(s)])


def get_match(query: str, choice: str) -> Match:
    if len(query) < len(choice) + 2 or ' ' not in query:
        return Match(choice=choice, score=lratio(query, choice), slice=Slice(0, len(query)))
    # we'll do partial matching of the query, but only using contiguous sequences of full words
    matches = []
    for partial_query in get_all_ngrams(query):
        start = query.find(partial_query)
        matches.append(Match(
            choice=choice,
            score=lratio(partial_query, choice),
            slice=Slice(start, start + len(partial_query))
        ))
    return max(matches, key=lambda m: m.score)


def best_matches(query: str, choices: List[str], cutoff=0.7, max_matches=10) -> List[Match]:
    matches = [get_match(query, choice) for choice in choices]
    matches = [m for m in matches if m.score >= cutoff]
    return sorted(matches, reverse=False, key=lambda m: m.score)[:max_matches]


def find_choices(query: str, choices: List[str], cutoff=0.7, max_matches=10) -> Tuple[List[str], int]:
    """Given a query string and a list of terms (choices), uses fuzzy matching against query word n-grams to find
    the best combination of choices present in the query string without overlapping.

    Returns tuple (choices, unmatched), where 'choices' is the list of choices found, and 'unmatched' is number
    of non-space characters in the query string unexplained by the found choices. Note that spelling mistakes
    don't count as unexplained characters - only full unexplained words count.

    >>> find_choices('one two three fourteen', ['two', 'one too', 'forteen'])
    (['one too', 'forteen'], 5)

    """
    matches: Dict[Slice, Match] = {}
    # construct dict Slice -> Match, picking the best match if multiple exist for the same Slice of the query string
    for match in best_matches(query, choices, cutoff=cutoff, max_matches=max_matches):
        if match.slice not in matches or matches[match.slice].score < match.score:
            matches[match.slice] = match
    if not matches:
        return [], len([c for c in query if c != ''])

    def calc_score(lst: List[Slice]):
        return sum(m.score * m.slice.len() for m in [matches[s] for s in lst])

    _, best = max(
        (calc_score(slice_lst), slice_lst) for slice_lst in get_non_overlaps(matches.keys())
    )
    best.sort(key=lambda sl: sl.l)
    # count all non-space characters falling outside of matched slices
    unmatched = sum([
        len([c for c in query[prev_sl.r:curr_sl.l] if c != ' '])
        for prev_sl, curr_sl in zip([Slice(-1, 0)] + best, best + [Slice(len(query), -1)])
    ])
    return [matches[sl].choice for sl in best], unmatched


def find_choices_raw(
    query: str,
    choices: List[str],
    cutoff=0.7,
    max_matches=10,
    replace_regexp=r'[^\w,]+'
) -> Tuple[List[str], int]:
    """
    Like find_choices() above, except that query is raw text which is pre-processed and split before using
    find_choices(). The pre-processing is based on observations from real farmer input: we replace all non-word
    characters with spaces, split on comma and word "and", trim all access spaces, and then search for
    choice words in each of the segments after splitting.

    >>> find_choices_raw('kale.&-+beans and maize', ['kale', 'beans', 'maize', 'and', 'bananas'])
    (['beans', 'kale', 'maize'], 0)
    """
    query_parts = re.sub(replace_regexp, ' ', query).lower().replace(' and ', ',').split(',')
    query_parts = [qp.strip() for qp in query_parts]
    choices_lst, unmatched_lst = zip(
        *[find_choices(q, choices, cutoff=cutoff, max_matches=max_matches) for q in query_parts])
    return sorted(set(itertools.chain(*choices_lst))), sum(unmatched_lst)
