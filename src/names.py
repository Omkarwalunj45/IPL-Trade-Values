"""Single source of truth for player-name canonicalisation.

Every dataset in this project spells some players differently.  Ball-by-ball
data uses one form ("Phil Salt"), the auction file uses the fuller registered
name ("Philip Salt"), and the salary file uses a third ("Rasikh Dar").  A merge
on the raw string silently drops those players instead of failing loudly, so
every load point routes names through here first.

Two separate problems are handled:

  _canon()  fixes mechanical damage -- mojibake apostrophes, non-breaking
            spaces, doubled internal spaces, trailing whitespace.  These are
            invisible on screen and defeat an exact dict lookup, so they are
            repaired BEFORE the alias map is consulted.

  ALIAS     maps genuine spelling variants onto the canonical form used by
            ipl_df__4_.parquet / war_final.parquet / final_pwar.csv.

Names that merely LOOK similar are deliberately absent.  Avinash Singh is not
Akash Singh, Tom Curran is not Sam Curran, Harpreet Brar is not Harpreet Singh.
Each of those pairs appears simultaneously in the auction file, which is how we
know they are separate registrations.
"""

import re

# Mojibake: a UTF-8 right single quote (U+2019) decoded as latin-1 becomes
# these three characters.  It appears in war_final.parquet and ipl_df__4_.parquet.
_MOJI = '\u00e2\u20ac\u2122'


def _canon(x):
    """Repair encoding damage and normalise whitespace in a player name."""
    if not isinstance(x, str):
        return x
    x = x.replace(_MOJI, "'").replace('\u2019', "'")   # curly / broken apostrophe -> ASCII
    x = x.replace('\u00c2', ' ').replace('\u00a0', ' ')  # stray  and non-breaking space
    return re.sub(r'\s+', ' ', x).strip()               # collapse doubles, trim ends


ALIAS = {
    'Abhinav Manohar Sadarangani': 'Abhinav Manohar',
    'Abhishek Porel':              'Abishek Porel',
    'Ajay Mandal':                 'Ajay Jadav Mandal',
    'Akshat Raghuvanshi':          'Akshat Raghuwanshi',
    'Allah Ghazanfar':             'AM Ghazanfar',
    'Auqib Nabi Dar':              'Auqib Nabi',
    'Digvesh Singh Rathi':         'Digvesh Rathi',
    'Dilshan Madhushanka':         'Dilshan Madushanka',
    'Donavon Ferreira':            'Donovan Ferreira',
    'Gurnoor Singh Brar':          'Gurnoor Brar',
    'Harnoor Singh Pannu':         'Harnoor Singh',
    'Harpreet Bhatia':             'Harpreet Singh',
    'Harpreet Singh Bhatia':       'Harpreet Singh',
    'Joshua Little':               'Josh Little',
    'KC Kariappa':                 'KC Cariappa',
    'Kanishk Chauhan':             'Kanishk Chouhan',
    'Kunal Rathore':               'Kunal Singh Rathore',
    'Lhuan-Dre Pretorius':         'Lhuan-dre Pretorius',
    'Mayank Agarawal':             'Mayank Agarwal',
    'Mitch Owen':                  'Mitchell Owen',
    'Mohammed Nabi':               'Mohammad Nabi',
    'Mohd Arshad Khan':            'Arshad Khan',
    'Mohd. Arshad Khan':           'Arshad Khan',
    'N Jagadeesan':                'Narayan Jagadeesan',
    'Nitish Reddy':                'Nitish Kumar Reddy',
    'Onkar Tarmale':               'Onkar Tukaram Tarmale',
    'Philip Salt':                 'Phil Salt',
    'Philip Dean Salt':            'Phil Salt',
    'Pravin Dubey':                'Praveen Dubey',
    'RS Hangargekar':              'Rajvardhan Hangargekar',
    'R Sai Kishore':               'Sai Kishore',
    'Ravisrinivasan Sai Kishore':  'Sai Kishore',
    'Rasikh Dar':                  'Rasikh Salam',
    'Rasikh Dar Salam':            'Rasikh Salam',
    'Rasikh Salam Dar':            'Rasikh Salam',
    'Shahrukh Khan':               'M Shahrukh Khan',
    'Smaran Ravichandran':         'Ravichandran Smaran',
    'Swastik Chhikara':            'Swastik Chikara',
    'Vaibhav Suryavanshi':         'Vaibhav Sooryavanshi',
    'Varun Chakaravarthy':         'Varun Chakravarthy',
    'Vidhwath Kaverappa':          'Vidwath Kaverappa',
    'Vyshak Vijaykumar':           'Vijaykumar Vyshak',
    'William ORourke':             "Will O'Rourke",
    'Yash Punja':                  'Yash Raj Punja',
    'Yudhvir Singh Charak':        'Yudhvir Singh',
    'Zak Foulkes':                 'Zakary Foulkes',
}


def one(x):
    """Canonicalise a single player name."""
    c = _canon(x)
    return ALIAS.get(c, c)


def fix(s):
    """Canonicalise a pandas Series of player names.

    Use in place of `.str.strip().replace(ALIAS)` -- it additionally repairs the
    encoding and whitespace damage that `.str.strip()` cannot see.
    """
    return s.map(one)
