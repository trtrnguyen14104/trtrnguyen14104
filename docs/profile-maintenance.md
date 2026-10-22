# Profile maintenance

The profile banner is rendered from `animations/space-hi-there.json`, using the
Lottie SVG renderer so image layers, masks, and vector paths retain their original
appearance. The GIF loops indefinitely at 851×623, 25 frames per second, with the
original 20-second timing.

To regenerate it, install Node.js and FFmpeg (available on PATH), then run:

```sh
npm ci
npx playwright install chromium
npm run animation:gif
```

To export a separate banner with the dark background panel removed, run:

```sh
npm run animation:gif:transparent
```

This writes `animations/hi_im_nguyen_transparent.gif` by removing only the source
animation's `Background` solid layer. It retains the current space banner's
851×623 canvas, 20-second loop and 25 frames per second.

The contact illustration is rendered from `animations/contact_me_alien.json`.
It preserves the original six-second timing at 20 frames per second, exported at
192×341 and displayed at 96 pixels wide to the left of the contact badges.
Regenerate it with the same dependencies:

```sh
npm run animation:contact
```

`scripts/update-metrics.py` generates four self-contained SVGs. Its layout follows
the two-column isometric-calendar and languages arrangement in the reference.
It uses Python's standard library and public GitHub data, so a personal access
token and third-party image hosting are unnecessary.

```sh
python scripts/update-metrics.py
```

The full-year and half-year calendars use GitHub's contribution calendar and its
daily counts. "Most used" aggregates GitHub language byte counts across public
repositories owned by this account, excluding forks. "Recently used" sums added
and deleted code lines in public push comparisons from the last 14 days, grouping
known source-code extensions. It measures changes in those pushes, which can also
include collaborators' commits; it is not Lowlighter's in-depth per-author analysis.
Binary files, documentation, and unrecognized extensions are excluded from recent
code statistics. GitHub limits the public events feed and comparison results
(300 changed files per push); the recent SVG indicates when that file cap is hit.

The workflow runs daily around 07:00 Vietnam time, on relevant pushes to `main`,
and manually through **Actions → Update profile metrics → Run workflow**. GitHub
may delay scheduled runs. It commits only `assets/metrics`, using the automatic
`GITHUB_TOKEN`. Fetch failures stop generation before replacing the existing SVGs.

To show these changes on the GitHub profile, push this repository's `main` branch.
