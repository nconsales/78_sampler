# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single-script Python tool (`seventyeight.py`) that renders a spinning-record video (`.mp4`) from an audio track and an image. It either pulls a random/specified 78rpm record from the Internet Archive's Great 78 Project (George Blood collection) or renders local audio+image files. There is no build system, linter, or test suite — the whole tool is one file.

## Running

Requires Python 3, `pip install -r requirements.txt`, and `ffmpeg`/`ffprobe` on PATH.

```
python seventyeight.py                          # random record from the Internet Archive
python seventyeight.py -i <ia_identifier>       # specific IA item
python seventyeight.py -a song.mp3 -g cover.jpg # local single file
python seventyeight.py -a song.mp3 --images a.jpg b.jpg  # alternate labels each spin
python seventyeight.py -b folder/ [--outdir out/] [-g fallback.jpg]  # batch: every mp3 in folder
```

Useful flags while developing: `-k/--keep` keeps the intermediate `temp/` frames, `-m/--maxlength 10` makes renders fast (default 140s, `0` = full track), `-q/--quiet` suppresses progress output.

## How the pipeline works

`main()` resolves user paths to absolute, then **chdirs to the script directory** — `grooves/`, `shine/`, `georgeblood.txt`, and the `temp/` frame directory are all resolved relative to the script, so any new path handling must convert user input to absolute paths *before* that chdir (see `_abs` in `main()`).

Render flow, whichever mode dispatches into it:

1. **Label detection** (`get_label_circle` → `get_label_crop`): downscale to 640px, OpenCV `HoughCircles` finds the round record label, crop it (plus a 20px margin) from the full-size image. If no circle is found, fall back to a centered square crop of the whole image — never fail on arbitrary user images.
2. **Background color** (`get_color`): ColorThief picks a dominant palette color from the label (fed an in-memory buffer, not a temp file, to avoid Windows file-lock issues); near-black colors are skipped.
3. **Frame rendering** (`render_record_frames` / `render_alternating_frames`): the label is masked onto a black disc, rotated `degrees_per_frame` per frame at 25 fps (derived from `--rpm`), and each frame is composited with cycling `grooves/*` and `shine/*` PNG overlay masks, then written as `temp/imgNNNN.jpg`. The alternating variant swaps which label is on the disc every full 360° rotation.
4. **Muxing** (`render_video`): ffmpeg loops the frame sequence against the audio; if the track is longer than `--maxlength` it trims and adds a 3-second audio fade-out. Audio duration comes from `ffprobe` (`get_audio_duration`), so any ffmpeg-readable format works, not just mp3.

Entry points per mode: `run_ia` (Internet Archive: picks the largest 'Item Image' and the shortest-named 'VBR MP3' from the item), `run_local`, `run_alternating`, and `run_batch` (pairs each mp3 with a same-named image via `find_image_for`, case-insensitively de-duplicated for Windows).

## Data files

- `georgeblood.txt` — the IA item list (~300k identifiers, 27 MB). Regenerate with `ia search collection:georgeblood --itemlist > georgeblood.txt`, optionally filtered through `grep -iv -f exclude.txt` (exclude.txt is gitignored).
- `grooves/` and `shine/` — numbered PNG mask sequences overlaid per frame; they are consumed in reverse-sorted order and recycled when exhausted.

## Gotchas

- Frame rendering and the `temp/` directory happen in the script directory and `temp/` is deleted at start and end of every render — concurrent renders from the same checkout will clobber each other.
- Output artifacts (`*.mp4`, `*.mp3`, `*.jpg`) are gitignored; don't commit rendered media.
- The former Twitter/X posting step has been removed; finished videos are only saved locally.
