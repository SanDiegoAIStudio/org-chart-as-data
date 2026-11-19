Teams often record who does what in a slide, a wiki page, a README and a pinned message, and those copies drift apart. This repository is one source file plus a script that checks the facts and writes the views people read. Run the check in a hook or a CI step, and a view edited by hand fails it before that edit becomes the version everyone trusts.

# What you get

- `org.json` holds the teams, who heads each, how each is measured, and what each owns.
- `render.py` checks those facts, writes the views, and fails when a view on disk no longer matches.
- `ROSTER.md` is the roster. `OWNERS.md` is the list of owned things. The roster is also placed in this page.
- `examples/pre-commit` and `examples/pre-push` run the check where edits are committed and pushed.
- `sh examples/demo.sh` walks the cycle on a throwaway copy and removes that copy when it exits.

# Quick start

From this folder, run:

```
sh examples/demo.sh
```

A clean run prints seven parts and exits 0:

```
(1) render
unchanged ROSTER.md
unchanged OWNERS.md
unchanged README.md (block roster)
rendered 3 outputs from org.json (0 changed)
exit 0
(2) check
views match org.json (3 outputs)
exit 0
(3) hand edit
DRIFT: ROSTER.md line 7 differs
  on disk:  | Build | Ava | working software a customer used this month | the mobile app, the release checklist 
  expected: | Build | Ada | working software a customer used this month | the mobile app, the release checklist 
1 of 3 outputs out of date. Change org.json, then run: python3 render.py
exit 1
(4) render after the hand edit
wrote ROSTER.md
unchanged OWNERS.md
unchanged README.md (block roster)
rendered 3 outputs from org.json (1 changed)
exit 0
views match org.json (3 outputs)
exit 0
(5) block edits
views match org.json (3 outputs)
exit 0
DRIFT: README.md line 83 differs
  on disk:  | Built | Ada | working software a customer used this month | the mobile app, the release checklist 
  expected: | Build | Ada | working software a customer used this month | the mobile app, the release checklist 
1 of 3 outputs out of date. Change org.json, then run: python3 render.py
exit 1
unchanged ROSTER.md
unchanged OWNERS.md
wrote README.md (block roster)
rendered 3 outputs from org.json (1 changed)
exit 0
(6) shared head
RULE: Ada heads both Build and Sell
1 rules broken in org.json; nothing was written
exit 1
(7) missing org.json
could not check: org.json is missing
exit 2
```

# The pattern

One source file. `org.json` is the only place the facts live. Edit that file, then run `python3 render.py`.

Rendered views that say at the top that they are generated. A whole file such as `ROSTER.md` starts with a line that tells the reader to change `org.json` and run `python3 render.py`. A block inside a page you already keep carries a shorter notice between its markers.

A check that fails when a view was edited by hand. `python3 render.py --check` compares every output with the source, writes nothing, and exits with a failing status when a view differs. The last line names how many outputs are out of date.

# The example org

Ada, Ben and Cy, and every team and owned thing below, are invented.

<!-- org:roster:begin -->
<!-- Generated from org.json. Edits between these two markers are overwritten. -->
| Team | Head | Measured by | Owns |
| --- | --- | --- | --- |
| Build | Ada | working software a customer used this month | the mobile app, the release checklist |
| Sell | Ben | new customers who signed | the price list, the proposal template |
| Run | Cy | backups that were restored in a drill | the nightly backup, the status page |
<!-- org:roster:end -->

# Make it yours

| Field | Where | What it holds |
| --- | --- | --- |
| `org` | top | Organisation name, used in the titles |
| `people` | top | List of names |
| `teams` | top | List of teams |
| `outputs` | top | List of views to write |
| `allow_shared_heads` | top | `true` or `false`. Default `false` when the field is left out |
| `name` | team | Team name |
| `head` | team | Person who heads the team |
| `measured_by` | team | Sentence the team is measured by |
| `members` | team | Optional list of names on the team |
| `owns` | team | Optional list of things the team owns |
| `view` | output | `roster`, `owners`, or a view you add (see Add your own view) |
| `file` | output | Path relative to the folder that holds `render.py` |
| `block` | output | Optional marker name of letters, digits and dashes. Leave it out to write the whole file |

To add a team, add the person to `people` if they are not already listed, then add an object to `teams` with `name`, `head`, `measured_by` and, when you want them, `members` and `owns`. Run `python3 render.py`.

To add an output, add an object to `outputs` with `view` set to `roster` or `owners` and `file` set to a path inside this folder. Run `python3 render.py`. The file is created whole: a generated line, a blank line, a title, a blank line, and the view. The roster's title is `# Roster: ORG` and the owners view's title is `# Who owns what: ORG`, where ORG is the `org` field. Folders on the way to the file are created. A file that already exists keeps its permissions, and a new file gets the permissions your umask gives new files. An output that names a folder stops the render and the check with `could not render: FILE is a folder` or `could not check: FILE is a folder`, exit 2. When a file cannot be written, the render prints `could not render: FILE could not be written (REASON)` and exits 2. Each changed file is first written to a temp file in its own folder, and the temp files are renamed into place only after all of them were written.

To put a view inside a page you already keep, paste these two lines into that page. Each marker stands alone on its line:

```
<!-- org:roster:begin -->
<!-- org:roster:end -->
```

Then add an output whose `file` is that page and whose `block` is `roster`. Run `python3 render.py`. Only the bytes between the markers are replaced. The check compares that block, so the rest of the page is free to edit.

The roster is a table in the order of `org.json`. The Members column is left out when no team has members, and the Owns column is left out when no team owns anything. Several members, or several owned things, are joined with a comma and a space. A `|` inside a value is written `\|`. The owners view lists every owned thing in alphabetical order, without regard to letter case, one line each: `- THING: TEAM (HEAD)`.

# The rules it keeps

A broken rule prints `RULE: ` and a plain sentence, one line for each break, not only the first. The last line is a count, then `nothing was written`, or `nothing was checked` when you passed `--check`. Nothing is written. The count line uses the word `rules` for any count.

| RULE line | What it means | What to do |
| --- | --- | --- |
| `there is no team` | `teams` is empty | Add at least one team |
| `a team has an empty name` | A team has no name | Set `name` |
| `has an empty head` | A team has no head | Set `head` to a person |
| `has an empty measured_by` | A team has no measure | Write `measured_by` |
| `the team name NAME is used more than once` | Two teams share a name | Rename one |
| `NAME is listed more than once in people` | The same name is listed twice | List each person once |
| `has head NAME, who is not in people` | The head is not in `people` | Add that name to `people` |
| `has member NAME, who is not in people` | The member is not in `people` | Add that name to `people` |
| `NAME heads both A and B`, or `NAME heads A, B, C` for three or more | One person heads more than one team | Give each team but one another head, or set `allow_shared_heads` to `true` |
| `NAME heads no team and is a member of none` | A person is on no team | Make them a head or a member |
| `THING is owned by both A and B` | Two teams own the same thing, ignoring letter case | Leave the thing with one team |
| `holds a line break` | A value contains a line break | Keep the value on one line |
| `is not text`, `is not a list`, `is not an object`, `is not true or false` | A value has the wrong kind. `org` and each name in `people` are text. `people`, `teams`, `outputs`, `members` and `owns` are lists. Each team and each output is an object. `allow_shared_heads` is `true` or `false` | Give the value that kind |
| `has an empty member`, `has an empty owned thing`, `an output has an empty file` | A team's `members` or `owns` holds an entry that is empty or is not text, or an output has no `file` | Fill it in or remove it |
| `has an invalid block name` | A `block` is empty or holds something other than letters, digits and dashes | Rename the block in the output and in both markers |
| `has an unknown field FIELD` | A field name is not one this tool knows, and the line names where it was found | Rename or remove the field |
| `names an unknown view NAME` | The output names a view that is not in the `VIEWS` table of `render.py` | Use `roster`, `owners` or a view you added |
| `is outside the root` | The path is absolute or contains `..` | Use a path inside the folder |
| `would overwrite org.json` or `would overwrite render.py` | The output names the source or the tool, in any letter case | Pick another file name |
| `is listed twice` | The same output is listed twice | List it once |
| `is written whole and also as a block` | One file is both a whole view and a block | Pick one |

# Put the check where edits happen

The pre-commit hook runs `python3 render.py --check` on the working copy and exits with that command's status. Copy `examples/pre-commit` to `.git/hooks/pre-commit` and mark the copy executable.

The pre-push hook reads the lines git passes on standard input (`LOCAL_REF LOCAL_SHA REMOTE_REF REMOTE_SHA`). For each line that pushes a branch and is not a delete, it extracts that commit into a temp folder and runs that commit's own `render.py` with `--check`. A working copy that was put right can hide a wrong commit, and an unfinished edit in the working copy can block a commit that is fine. The hook checks the commit being pushed, and it refuses the push, naming the ref, when the check does not exit 0. It removes each temp folder once that commit is checked, and the one in use when it stops early. Copy `examples/pre-push` to `.git/hooks/pre-push` and mark the copy executable.

A CI step is one line: `python3 render.py --check`

Two more options. `python3 render.py --view NAME` prints that view's text on standard output after the rules pass and writes nothing; once `org.json` has loaded, a name that is not a view prints `usage: unknown view NAME` on standard error and exits 2. `--root DIR` reads `org.json` from DIR and writes or checks the outputs there, in place of the folder that holds `render.py`; the pre-push hook uses it to check a commit it extracted. Any other argument prints a one-line usage message on standard error and exits 2.

# Add your own view

Adding a view is one function that takes the org and returns text, plus one entry in the `VIEWS` table near the top of `render.py`:

```python
def view_openings(org):
    lines = ["# Openings"]
    for team in org["teams"]:
        head = team["head"]
        line = team["name"] + " (head " + head + ")"
        lines.append(line)
    body = "\n".join(lines)
    return body + "\n"

VIEWS["openings"] = view_openings
```

Point an output at it with `"view": "openings"`. The function runs only after the rules pass. Run `python3 render.py`.

A whole file of a view you add holds the generated line, a blank line, and then the function's text. The tool adds no title of its own to that file, so the function writes its own heading, as `# Openings` does here.

# Tests

```
python3 -m unittest discover -s tests -v
python3 tests/mutate.py
```

The first command runs 58 tests. The hook tests need git and are skipped without it. They copy this folder's `render.py`, `org.json`, `ROSTER.md`, `OWNERS.md` and `README.md` into a temporary repository and change the example's `Ada`. The demo and its test change the example's names too, and one test looks for the roster block in this README. Those tests expect the example org: run them before you replace it with your own.

`python3 tests/mutate.py` first runs each test file it uses, `tests/test_rules.py`, `tests/test_render.py` and `tests/test_check.py`, on an unchanged copy of `render.py`, and exits 2 when one fails. It then plants one bug at a time in a throwaway copy and runs the test file named for that bug. A bug counts as caught when that run reports at least one failure or error. It prints one line per bug and ends with `caught 46 of 46`. It exits 0 when every bug was caught and 1 when one was not, and for a bug that was not caught it keeps the test output in a temporary folder and prints its path. A row whose old text is not found exactly once stops it with exit 2 before any bug is planted. It took under two minutes on the Mac it was tested on.

# Limits

- One `org.json`, with no includes.
- Names are plain text, so two people with the same name need something to tell them apart.
- An empty name in `people` is ignored, and a second empty name is reported as listed more than once.
- It models team heads, members and owned things, and not reporting lines between people.
- Views are Markdown.
- The two marker lines must each stand alone on a line.
- The check compares bytes. In a file written whole, changed line ends or a dropped final newline read as drift, and `python3 render.py` puts the file back. In a page with a block, changed line ends inside the block read as drift and the render puts them back, but marker lines that end in a carriage return are not found: the check prints `DRIFT: FILE has no org:NAME block` and the render stops with `could not render: FILE has no org:NAME block` until those line ends are plain newlines again.
- The pre-push hook needs git and tar, extracts the whole commit, which is slow on a very large repository, checks the newest commit of each pushed branch and skips tags and deletes.
- The hooks are examples you copy into each clone, and `git commit --no-verify` or `git push --no-verify` skips them. A CI step that runs the check on every push catches a commit that skipped them.
- Who changed what and when is git's job.
- A symbolic link inside the folder is followed when it is a folder on the way to an output, so an output can land outside the folder, and an output file that is itself a symbolic link is replaced by a plain file.
- An output written whole replaces the file it names. Pointed at a page you wrote by hand, it replaces that page, also when the page is not UTF-8 text, so put a view inside a page you keep with a block.
- The pre-push hook extracts each commit with `git archive`, which leaves out paths marked `export-ignore` in `.gitattributes`. An output marked that way reads as missing, and the push is refused.

It needs a POSIX system: paths are split on `/`, and the demo and the hooks are `sh` scripts. It was tested on macOS with Python 3.9 and Python 3.14.

# License

MIT. The full text is in `LICENSE`.

# Built at San Diego AI Studio

This tool comes out of San Diego AI Studio, the builders' community in San Diego, where builders show the systems they run. More projects: https://sandiegoaistudio.com/projects
