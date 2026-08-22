# Articles

The Articles tab reads this folder. It never contacts Substack at runtime.

## How it works

`tools/substack_import.py` is a **one-off tool you run on your own laptop**, not
something the website runs. It turns your Substack posts into files:

    content/articles/<slug>.json      text, headings, figures, formulas
    content/articles/images/*.jpg     cover images and every in-body figure

Those files are the website's content. Streamlit Cloud just reads them.

## Publishing a new article

1. Publish on Substack as normal.
2. On your laptop, from the repo root:

       python tools/substack_import.py

   New posts get imported. Existing ones are left alone (add `--force` to
   re-import everything from scratch).
3. Commit and push:

       git add content/articles
       git commit -m "articles"
       git push

Streamlit redeploys and the article is live. **Nothing needs to run on the
server** — no build step, no cron, no extra requirements. If you never run the
importer again, the site keeps serving whatever is committed.

## Editing an article on the site

Open its `.json` and change any of these; the importer will not overwrite your
edits unless you pass `--force`:

| field | what it does |
|---|---|
| `order` | integer pins the card to that position; `null` = sort by likes |
| `likes` | the sort key, pulled from Substack reactions |
| `category` | small kicker above the card title; blank hides it |
| `description` | blurb on the card (defaults to the Substack subtitle) |
| `cover` | filename in `images/` used as the card thumbnail |

Block types inside `blocks`: `H` big heading, `h` small heading, `t` paragraph
(markdown), `i` image + caption, `q` quote, `f` LaTeX, `r` divider, `c` contact
button.

## Setting the running order

`content/articles/order.json` is a plain list of slugs, top of the page first.
Move lines around to reorder the tab. Anything not listed falls to the bottom
and sorts by likes. The importer writes this file once and then never touches
it again unless you pass `--reorder`.

## An article Substack does not list

The importer prints an inventory of every post Substack reports before it
starts. If a piece is not on that list, no importer can reach it through the
API. Import it directly instead:

    python tools/substack_import.py --add https://theunseengame.substack.com/p/its-slug

Then open the resulting json and fix `title`, `date`, `date_sort` and `likes`
by hand, and add its slug to `order.json`.

## Excluding a post

Edit the `EXCLUDE` list at the top of `tools/substack_import.py` (matched
against title and subtitle), then delete the stray `.json` if it was already
imported.
