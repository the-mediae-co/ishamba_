import functools
import itertools
import os
from collections import Counter
from typing import Tuple, Iterable, Set
import numpy as np
import pandas as pd
import scipy.sparse
from sklearn.feature_extraction.text import TfidfVectorizer

from fuzzywuzzy import process as fuzz_process

from world.models import get_county_names_and_ids


class Matcher:

    default_remove_regexp = "'"
    default_to_space_regexp = r'[^\w]+'

    def __init__(
        self,
        ngram_range: Tuple[int, int],
        df: pd.DataFrame,
        counties: Iterable[str],
        county_school_matrix: scipy.sparse.spmatrix = None,
        remove_regexp=default_remove_regexp,
        to_space_regexp=default_to_space_regexp,
        stop_words: Iterable[str] = None,
    ):
        self.df = df
        self.remove_regexp = remove_regexp
        self.to_space_regexp = to_space_regexp
        self.stop_words = set(stop_words) if stop_words else {}
        self.vectorizer = TfidfVectorizer(analyzer='char_wb', ngram_range=ngram_range)
        counties = np.array(counties)
        self.counties_name_to_id = {county_name: i for i, county_name in enumerate(counties)}
        corpus = self._clean(df['name'])
        self.X = self.vectorizer.fit_transform(corpus)
        if county_school_matrix is None:
            county_school_matrix = scipy.sparse.csr_matrix(
                df.county.to_numpy()[np.newaxis, :] == counties[:, np.newaxis])
        self.county_school_matrix = county_school_matrix

    @staticmethod
    def clean(
            s: pd.Series,
            remove_regexp=default_remove_regexp,
            to_space_regexp=default_to_space_regexp,
            stop_words: Set[str] = None
    ) -> pd.Series:
        if remove_regexp:
            s = s.str.replace(remove_regexp, '', regex=True)
        if to_space_regexp:
            s = s.str.replace(to_space_regexp, ' ', regex=True)
        s = s.str.lower().str.strip()
        if stop_words:
            s = s.str.split().apply(
                lambda l: [x for x in l if x not in stop_words]
            ).apply(
                lambda l: ' '.join(l)
            )
        return s

    def _clean(self, s: pd.Series):
        return self.clean(
            s,
            remove_regexp=self.remove_regexp,
            to_space_regexp=self.to_space_regexp,
            stop_words=self.stop_words
        )

    def _match(self, vals: Iterable[str], counties: Iterable[str] = None):
        if not isinstance(vals, pd.Series):
            vals = pd.Series(vals)
        if counties is not None and not isinstance(counties, pd.Series):
            counties = pd.Series(counties)
        y = self.vectorizer.transform(self._clean(vals))
        ret: scipy.sparse.spmatrix = self.X.dot(y.transpose())
        if counties is not None:
            county_ids = [self.counties_name_to_id[county_name] for county_name in counties]
            ret = ret.multiply(self.county_school_matrix[county_ids].transpose())
        return ret.toarray()

    def match_many(
            self,
            vals: Iterable[str],
            n=5,
            counties: Iterable[str] = None
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Searches for multiple school names, returning n top matches for each of them.
        The return value is a tuple of three 2-dim ndarrays: ids, scores, and names.
        Each of the arrays has a shape (n, len(vals)), with each column corresponding to
        one of the searched-for vals, and each row to one of the matches returned for that
        val.

        If counties arg is passed in, it must be an Iterable of the same length as vals, with desired
        county names corresponding to those used to train the model.
        """
        res = self._match(vals, counties)
        ind = res.argsort(axis=0)[:-(n+1):-1, :]
        return ind, np.take_along_axis(res, ind, axis=0), self.df['name'].to_numpy()[ind]

    def match_df(
            self,
            val: str,
            n=5,
            distance_from: Tuple[int, int] = None,
            county: str = None
    ) -> pd.DataFrame:
        """
        Searches for a single school name and returns nice dataframe with top n matches.
        The distance shown is distance in km from the top match, or from the `distance_from`
        geopoint provided as (lat, long) tuple.
        """
        res = self._match([val], [county] if county is not None else None)
        res = res[:, 0]
        ind: np.ndarray = res.argsort()[-n:]
        ind = ind[::-1]
        df: pd.DataFrame = self.df.iloc[ind].copy()
        df['score'] = res[ind]
        return df


# We use the matcher as a singleton, and instantiate it lazily.
@functools.lru_cache(maxsize=1)
def get_matcher() -> Matcher:
    df_schools = pd.read_csv(f'{os.path.dirname(__file__)}/data/schools/kenya_schools.csv').fillna('')
    names = Matcher.clean(df_schools.name)
    c = Counter(itertools.chain.from_iterable([s.split() for s in names]))
    # count as stop word anything that shows up more than 100 times
    stop_words, _ = zip(*itertools.takewhile(lambda t: t[1] > 100, c.most_common()))
    stop_words = set(stop_words)
    # add few more things which are not that common, but still not useful to match on
    stop_words.update(['and', 'schools'])

    # The first dimension of this matrix is county index. We'll use names of counties from ishamba
    # database, but we need to order them according to how the matrix was computed, rather than
    # according to their database pks.
    df_counties = pd.read_csv(f'{os.path.dirname(__file__)}/data/schools/kenya_counties.csv')
    my_counties = [name for name, _ in get_county_names_and_ids()]
    my_counties_reordered = [fuzz_process.extractOne(name, my_counties)[0] for name in df_counties.county]
    assert len(set(my_counties_reordered)) == len(df_counties), 'FATAL: counties did not map 1-1'
    county_school_matrix = scipy.sparse.load_npz(f'{os.path.dirname(__file__)}/data/schools/county_school_matrix.npz')
    matcher = Matcher(
        ngram_range=(2, 3),
        df=df_schools,
        counties=my_counties_reordered,
        county_school_matrix=county_school_matrix,
        stop_words=stop_words
    )
    return matcher
