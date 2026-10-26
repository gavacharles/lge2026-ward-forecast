"""Community types: voting districts grouped by how they voted, as a stand-in for demographics.

Census 2022 ward profiles (population group, language) are not published in a machine-readable
form, so wards are grouped by their party mix in a baseline national election instead. In South
Africa party mix tracks language and population group closely (e.g. IFP/MK = isiZulu-speaking,
PA + DA = coloured communities, FF+ + DA = white Afrikaans-speaking), so the groups behave like
demographic strata for swing.
"""
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

FEATURES = ["ANC", "DA", "EFF", "IFP", "FFP", "PA", "MK", "OTH"]
K = 8


def shares(votes, election, keys):
    """Party shares per key (vd -> key mapping DataFrame [vd, key])."""
    v = votes[votes.election == election].merge(keys, on="vd")
    v["party"] = v.party.where(v.party.isin(FEATURES), "OTH")
    t = v.pivot_table(index="key", columns="party", values="votes", aggfunc="sum", fill_value=0)
    t = t.reindex(columns=FEATURES, fill_value=0)
    n = t.sum(axis=1)
    return t.div(n.replace(0, np.nan), axis=0).fillna(0), n


class CommunityTypes:
    def fit(self, votes, election, seed=7):
        vds = votes[votes.election == election][["vd"]].drop_duplicates().assign(key=lambda d: d.vd)
        X, n = shares(votes, election, vds)
        X = X[n > 50]
        self.km = KMeans(K, n_init=10, random_state=seed).fit(np.sqrt(X.values), sample_weight=n[n > 50].values)
        self.centres = pd.DataFrame(self.km.cluster_centers_ ** 2, columns=FEATURES)
        self.labels = [self._name(r) for r in self.centres.itertuples(index=False)]
        return self

    @staticmethod
    def _name(c):
        top = sorted(((v, k) for k, v in c._asdict().items()), reverse=True)[:2]
        return " / ".join(f"{k} {v:.0%}" for v, k in top)

    def assign(self, votes, election, keys):
        """Community type per key (e.g. ward), from its voting districts' baseline results."""
        X, n = shares(votes, election, keys)
        return pd.Series(self.km.predict(np.sqrt(X.values)), index=X.index)
