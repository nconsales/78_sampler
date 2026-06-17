#!/usr/bin/env python3

import argparse
import io
import os
import glob
import random
import shutil
import subprocess
import sys

import internetarchive as ia
import cv2
import numpy as np

from colorthief import ColorThief
from mutagen.mp3 import MP3
from PIL import Image, ImageDraw, ImageOps

IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff')

def get_items_list():
    with open('georgeblood.txt', 'r') as f:
        items = [item.strip() for item in f.readlines()]
    return items

def get_item(items):
    return random.choice(items)

def get_image(files):
    images = [f for f in files if f.format == 'Item Image']
    photo = max(images, key=lambda i: i.size)
    return photo

def get_audio(files):
    mp3s = [f for f in files if f.format == 'VBR MP3']
    track = min(mp3s, key=lambda s: len(s.name))
    return track

def get_label_circle(fullsize_path):
    fullsize = Image.open(fullsize_path)
    fullsize_dimensions = fullsize.size

    ratio = fullsize_dimensions[0]/640

    crop = ImageOps.fit(fullsize, (640,640))
    filename = ''.join(['640_' + os.path.basename(fullsize_path)])
    crop.save(filename)

    src = cv2.imread(filename)
    blur = cv2.medianBlur(src, 5)
    gray = cv2.cvtColor(blur, cv2.COLOR_RGBA2GRAY)

    circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, 1, 200,
                               param1=150, param2=70, minRadius=150, maxRadius=320)

    os.remove(filename)

    if circles is not None:
        circles = np.round(circles[0,:]).astype('int')
        x, y, r = [int(val * ratio) for val in max(circles.tolist(), key=lambda c: c[2])]

        return x, y, r

    else:
        return None

def crop_label(imagepath, x, y, r):
    r += 20

    fullsize = Image.open(imagepath)
    label_crop = fullsize.crop((x - r, y - r, x + r, y + r))

    return label_crop

def get_label_crop(image_path, quiet=False):
    """Locate the round record label in an image and return a square crop of it.

    If no circular label can be detected (common for arbitrary user-supplied
    images), fall back to a centered square crop of the whole image so the
    spinning effect still works instead of failing."""
    try:
        circle = get_label_circle(image_path)
    except Exception:
        circle = None

    if circle is not None:
        x, y, r = circle
        return crop_label(image_path, x, y, r)

    if not quiet:
        print("  no record label detected; spinning the full image")
    img = Image.open(image_path).convert('RGB')
    side = min(img.size)
    return ImageOps.fit(img, (side, side))

def get_color(image, cleanup=True):
    # Feed ColorThief an in-memory buffer rather than a temp file on disk.
    # ColorThief holds the file handle open, which on Windows prevents the
    # temp file from being deleted (PermissionError / WinError 32).
    buf = io.BytesIO()
    image.convert('RGB').save(buf, format='JPEG')
    buf.seek(0)
    colorthief = ColorThief(buf)
    palette = colorthief.get_palette(color_count=2, quality=1)
    buf.close()
    for color in palette:
        if not all(channel < 64 for channel in color):
            dominant = color
            break
    else:
        dominant = (255,252,233)

    return dominant

def render_record_frames(label_crop, bg_color, size=(720,720), degrees_per_frame=3,
                         max_time=140, directory="temp"):
    label_crop = ImageOps.fit(label_crop, (400,400))
    label_mask = Image.new('L', (400,400))
    draw = ImageDraw.Draw(label_mask)
    draw.ellipse((0,0,400,400), fill=255)

    recimg = Image.new('RGB', size, 0)
    recimg.paste(label_crop, box=(160,160), mask=label_mask)

    mat = Image.new('L', size, color=255)
    draw = ImageDraw.Draw(mat)
    draw.ellipse((36,36,684,684), fill=0)

    angle = 0
    index = 0
    grooves = []
    shines = []

    while index <= 25 * max_time and (angle % 360 or angle == 0 or grooves or shines):
        rot = recimg.rotate(-angle)
        rot.paste(bg_color, mask=mat)
        if not grooves:
            grooves = sorted(glob.glob('grooves/*'), reverse=True)
        if not shines:
            shines = sorted(glob.glob('shine/*'), reverse=True)

        groove_mask = ImageOps.invert(Image.open(grooves.pop(0)).convert(mode='L'))
        shine_mask = ImageOps.invert(Image.open(shines.pop(0)).convert(mode='L'))

        rot.paste(bg_color, mask=groove_mask)
        rot.paste(bg_color, mask=shine_mask)

        filename = 'img{:04d}.jpg'.format(index)
        rot.save(os.path.join(directory, filename))
        index += 1
        angle += degrees_per_frame

def render_video(image_directory, audio_file, max_time=140, output_file='merge.mp4'):
    audio = MP3(audio_file)

    if max_time == 0 or audio.info.length < max_time:
        timeout = audio.info.length
        fade = False
    else:
        timeout = max_time
        fade = True

    command = ['ffmpeg', '-y', '-hide_banner', '-loglevel', 'panic']
    command.extend(['-i', audio_file, '-loop', '1',
                    '-i', '{}/img%04d.jpg'.format(image_directory)])
    if fade:
        command.extend(['-af','afade=t=out:st={}:d=3'.format(str(max_time-2))])
    command.extend(['-strict', '-2', '-ss', '0', '-to', str(timeout), output_file])

    subprocess.run(command)

def make_video(audio_path, image_path, output_file, maxlength=140, rpm=12.5,
               cleanup=True, quiet=False):
    """Render a spinning-record video from a local audio file and image."""
    if os.path.exists('temp'):
        shutil.rmtree('temp')
    os.makedirs('temp')

    if not quiet:
        print("finding label")
    label_crop = get_label_crop(image_path, quiet=quiet)
    bg_color = get_color(label_crop, cleanup)

    seconds_per_rotation = 60/rpm
    frames_per_rotation = seconds_per_rotation * 25
    degrees_per_frame = max(1, int(360/frames_per_rotation))

    if not quiet:
        print("rendering spinning record frames")
    render_record_frames(label_crop, bg_color,
                         degrees_per_frame=degrees_per_frame, max_time=maxlength)

    if not quiet:
        print("rendering video")
    render_video('temp', audio_path, max_time=maxlength, output_file=output_file)

    if cleanup and os.path.exists('temp'):
        shutil.rmtree('temp')

    if not quiet:
        print("saved", output_file)


def run_ia(ia_id=None, cleanup=True, quiet=False, maxlength=140, rpm=12.5,
           output_file=None):
    """Pull a record from the Internet Archive (Great 78 Project) and render it."""
    if ia_id is None:
        items = get_items_list()
        ia_id = get_item(items)

    item = ia.get_item(ia_id)

    files = list(item.get_files(formats=['VBR MP3', 'Item Image']))
    photo = get_image(files)
    track = get_audio(files)

    title = item.metadata.get('title', '')
    date = item.metadata.get('date', '')

    date = ''.join(['(', date.split('-')[0], ')']) if date else ''
    title = ' '.join([title, date]) if date else title

    artists = item.metadata.get('creator', '')
    artists = artists[0] if type(artists) is list else artists

    url = "https://archive.org/details/" + item.identifier

    if not quiet:
        print("downloading", title)

    track.download(track.name)
    photo.download(photo.name)

    if output_file is None:
        output_file = item.identifier + '.mp4'

    make_video(track.name, photo.name, output_file,
               maxlength=maxlength, rpm=rpm, cleanup=cleanup, quiet=quiet)

    if cleanup:
        if os.path.exists(track.name):
            os.remove(track.name)
        if os.path.exists(photo.name):
            os.remove(photo.name)

    status = " ".join([title.lower() + ' - ' + str(artists).lower(), url])
    print(status)


def run_local(audio_path, image_path, output_file=None, maxlength=140, rpm=12.5,
              cleanup=True, quiet=False):
    """Render a video from a single local mp3 + image."""
    if not os.path.exists(audio_path):
        sys.exit('audio file not found: ' + audio_path)
    if not os.path.exists(image_path):
        sys.exit('image file not found: ' + image_path)

    if output_file is None:
        stem = os.path.splitext(os.path.basename(audio_path))[0]
        output_file = os.path.join(os.path.dirname(audio_path) or '.', stem + '.mp4')

    make_video(audio_path, image_path, output_file,
               maxlength=maxlength, rpm=rpm, cleanup=cleanup, quiet=quiet)


def find_image_for(audio_path, default_image=None):
    """Find an image sitting next to an mp3 with the same base name."""
    stem = os.path.splitext(audio_path)[0]
    for ext in IMAGE_EXTS:
        for candidate in (stem + ext, stem + ext.upper()):
            if os.path.exists(candidate):
                return candidate
    return default_image


def run_batch(folder, default_image=None, outdir=None, maxlength=140, rpm=12.5,
              cleanup=True, quiet=False):
    """Render a video for every mp3 in a folder, pairing each with an image."""
    if not os.path.isdir(folder):
        sys.exit('not a folder: ' + folder)

    # Collect mp3s, de-duplicating case-insensitively so we don't process a
    # file twice on case-insensitive filesystems (e.g. Windows, where both
    # '*.mp3' and '*.MP3' match the same files).
    seen = set()
    mp3s = []
    for pattern in ('*.mp3', '*.MP3'):
        for p in glob.glob(os.path.join(folder, pattern)):
            key = os.path.normcase(os.path.abspath(p))
            if key not in seen:
                seen.add(key)
                mp3s.append(p)
    mp3s.sort()
    if not mp3s:
        sys.exit('no .mp3 files found in ' + folder)

    if outdir:
        os.makedirs(outdir, exist_ok=True)

    succeeded = 0
    for audio_path in mp3s:
        image_path = find_image_for(audio_path, default_image)
        if image_path is None:
            print('skipping (no matching image, and no --image fallback):', audio_path)
            continue

        stem = os.path.splitext(os.path.basename(audio_path))[0]
        out = os.path.join(outdir or folder, stem + '.mp4')

        if not quiet:
            print('processing', os.path.basename(audio_path), '->', out)
        try:
            make_video(audio_path, image_path, out,
                       maxlength=maxlength, rpm=rpm, cleanup=cleanup, quiet=quiet)
            succeeded += 1
        except Exception as e:
            print('  failed:', os.path.basename(audio_path), '-', e)

    print('batch done: {}/{} rendered'.format(succeeded, len(mp3s)))


def main():
    parser = argparse.ArgumentParser(
        description="Render spinning-record videos from the Internet Archive "
                    "or from your own local mp3s and images.")

    # Local single-file mode
    parser.add_argument('-a', '--audio', action='store', default=None,
                        help="path to a local mp3 to render (use with --image)")
    parser.add_argument('-g', '--image', action='store', default=None,
                        help="path to a local image; the record label/art to spin. "
                             "In --batch mode, used as a fallback when no same-named "
                             "image is found next to an mp3")

    # Local batch mode
    parser.add_argument('-b', '--batch', action='store', default=None,
                        help="path to a folder of mp3s to render in bulk")
    parser.add_argument('--outdir', action='store', default=None,
                        help="folder to write batch output into (default: next to each mp3)")

    # Internet Archive mode (default)
    parser.add_argument('-i', '--id', action='store', default=None,
                        help="explicitly provide an Internet Archive identifier to download")

    # Shared options
    parser.add_argument('-o', '--output', action='store', default=None,
                        help="output video path (single-file / IA modes)")
    parser.add_argument('-k', '--keep', action='store_true',
                        help="keep intermediate files after completion")
    parser.add_argument('-q', '--quiet', action='store_true',
                        help="suppress progress output")
    parser.add_argument('-m', '--maxlength', action='store', type=int, default=140,
                        help="max length of the video in seconds (default 140; 0 = full track)")
    parser.add_argument('-r', '--rpm', action='store', type=float, default=12.5,
                        help="revolutions per minute of the spinning disc (default 12.5)")

    args = parser.parse_args()
    cleanup = not args.keep

    # Resolve user-supplied paths to absolute *before* we chdir into the script
    # directory (which is required so grooves/, shine/ and georgeblood.txt resolve).
    def _abs(p):
        return os.path.abspath(p) if p else p

    audio = _abs(args.audio)
    image = _abs(args.image)
    batch = _abs(args.batch)
    outdir = _abs(args.outdir)
    output = _abs(args.output)

    abspath = os.path.abspath(__file__)
    dname = os.path.dirname(abspath)
    os.chdir(dname)

    if batch:
        run_batch(batch, default_image=image, outdir=outdir,
                  maxlength=args.maxlength, rpm=args.rpm,
                  cleanup=cleanup, quiet=args.quiet)
    elif audio:
        if not image:
            sys.exit('--image is required when using --audio')
        run_local(audio, image, output_file=output,
                  maxlength=args.maxlength, rpm=args.rpm,
                  cleanup=cleanup, quiet=args.quiet)
    else:
        run_ia(ia_id=args.id, cleanup=cleanup, quiet=args.quiet,
               maxlength=args.maxlength, rpm=args.rpm, output_file=output)


if __name__ == '__main__':
    main()
