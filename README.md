# 78_sampler

This tool renders a spinning-record video from an audio track and an image: it
finds the round label in the image, crops it onto a rotating vinyl disc (with
`grooves/` and `shine/` overlay masks), and muxes it together with the audio
into an `.mp4`.

It can pull records automatically from the [Great 78 Project](https://archive.org/details/georgeblood)
on the Internet Archive, **or** render your own local mp3s and images. Finished
videos are saved locally (the original Twitter/X posting step has been removed).

## Requirements

- Python 3 with the packages in `requirements.txt` (`pip install -r requirements.txt`)
- [`ffmpeg`](https://ffmpeg.org/) available on your `PATH`

## Usage

### Internet Archive (default)

Render a random record from the George Blood collection:

```
python seventyeight.py
```

Render a specific Internet Archive item by identifier:

```
python seventyeight.py -i <internet_archive_id>
```

### Your own files (single)

```
python seventyeight.py --audio mysong.mp3 --image cover.jpg
```

By default the video is written next to the audio file (`mysong.mp4`). Use
`-o/--output` to choose a path.

### Your own files (batch)

Render every mp3 in a folder, pairing each with a same-named image
(`song.mp3` -> `song.jpg`/`song.png`/...):

```
python seventyeight.py --batch path/to/folder
```

Write the results somewhere else with `--outdir`, and supply a fallback image
for any mp3 that has no matching image:

```
python seventyeight.py --batch path/to/folder --outdir path/to/output --image default_label.jpg
```

### Options

| Flag | Description |
| --- | --- |
| `-a, --audio` | Local mp3 to render (single-file mode) |
| `-g, --image` | Local image to spin; also the fallback image in batch mode |
| `-b, --batch` | Folder of mp3s to render in bulk |
| `--outdir` | Output folder for batch mode (default: next to each mp3) |
| `-i, --id` | Internet Archive identifier to download |
| `-o, --output` | Output video path (single-file / IA modes) |
| `-m, --maxlength` | Max video length in seconds (default 140; `0` = full track) |
| `-r, --rpm` | Spin speed of the disc (default 12.5) |
| `-k, --keep` | Keep intermediate files |
| `-q, --quiet` | Suppress progress output |

> **Note on your own images:** the spinning effect works best with square art or
> an actual record label. If no circular label is detected in your image, the
> tool automatically spins the whole (square-cropped) image instead of failing.

## Updating the George Blood item list

The `internetarchive` module provides a CLI that can regenerate `georgeblood.txt`.
The collection contains 300,000+ items and grows over time:

```
ia search collection:georgeblood --itemlist > georgeblood.txt
```

To exclude items you never want, keep an `exclude.txt` of strings and filter:

```
ia search collection:georgeblood --itemlist | grep -iv -f exclude.txt > georgeblood.txt
```
