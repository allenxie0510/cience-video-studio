#!/usr/bin/env python3
"""Validate sentence clips and build a sample-accurate video timeline. Stdlib only."""
import argparse
import json
import math
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

RATE = 48000


def number(value, name, low=0):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < low:
        raise ValueError(f'{name} must be a finite number >= {low}')
    return value


def stamp(seconds):
    ms = round(seconds * 1000)
    return f'{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}'


def prepare(args):
    source = args.lesson.resolve()
    lesson = json.loads(source.read_text())
    segments = lesson.get('segments')
    if not isinstance(segments, list) or not segments:
        raise ValueError('segments must be a nonempty list')
    ids = set()
    for s in segments:
        if not isinstance(s, dict):
            raise ValueError('Every segment must be an object')
        sid = s.get('id')
        if not isinstance(sid, str) or not sid.strip() or sid in ids:
            raise ValueError('Every segment needs a unique nonempty string id')
        ids.add(sid)
        if not isinstance(s.get('narration'), str) or not s['narration'].strip():
            raise ValueError(f'{sid}: narration is empty')
        number(s.get('tail', .25), f'{sid}.tail')
    audio_flags = [bool(s.get('audio')) for s in segments]
    voiced = all(audio_flags)
    if any(audio_flags) and not voiced:
        raise ValueError('Mixed voiced/unvoiced segments are not allowed')
    if not voiced and not args.draft:
        raise ValueError('Missing audio: use --draft only for explicitly silent previews')
    if voiced and not shutil.which('ffmpeg'):
        raise ValueError('ffmpeg is required for audio decoding')
    out = args.out.resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError(f'Output must be an empty directory: {out}')
    out.mkdir(parents=True, exist_ok=True)
    timeline, subtitles, cursor = [], [], 0
    # All validation/decoding happens in a temporary directory before publishing files.
    with tempfile.TemporaryDirectory(prefix='science-video-') as td:
        temp = Path(td)
        track = wave.open(str(temp / 'narration.wav'), 'wb') if voiced else None
        try:
            if track:
                track.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
            for index, s in enumerate(segments, 1):
                tail_frames = round(s.get('tail', .25) * RATE)
                if voiced:
                    audio = (source.parent / s['audio']).resolve()
                    if not audio.is_file():
                        raise ValueError(f'Missing audio for {s["id"]}: {audio}')
                    pcm = temp / f'{index}.wav'
                    subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-n', '-i', str(audio),
                                    '-vn', '-ar', str(RATE), '-ac', '1', '-c:a', 'pcm_s16le', str(pcm)], check=True)
                    with wave.open(str(pcm), 'rb') as clip:
                        speech_frames = clip.getnframes()
                        if speech_frames <= 0:
                            raise ValueError(f'{s["id"]}: empty audio')
                        while chunk := clip.readframes(RATE):
                            track.writeframesraw(chunk)
                    track.writeframesraw(b'\0\0' * tail_frames)
                else:
                    total = number(s.get('draft_duration'), f'{s["id"]}.draft_duration', .01)
                    speech_frames = round(total * RATE) - tail_frames
                    if speech_frames <= 0:
                        raise ValueError(f'{s["id"]}: tail must be shorter than draft_duration')
                start, speech_end, end = cursor / RATE, (cursor + speech_frames) / RATE, (cursor + speech_frames + tail_frames) / RATE
                timeline.append({**s, 'start': start, 'speech_end': speech_end, 'end': end})
                subtitles.append(f'{index}\n{stamp(start)} --> {stamp(speech_end)}\n{s["narration"].strip()}\n')
                cursor += speech_frames + tail_frames
        finally:
            if track:
                track.close()
        result = {'title': lesson.get('title', ''), 'mode': 'voiced' if voiced else 'silent-draft',
                  'duration': cursor / RATE, 'sample_rate': RATE, 'segments': timeline}
        (out / 'timeline.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        (out / 'captions.srt').write_text('\n'.join(subtitles), encoding='utf-8')
        if voiced:
            shutil.copy2(temp / 'narration.wav', out / 'narration.wav')
    print(json.dumps({'output': str(out), 'mode': result['mode'], 'duration': result['duration'], 'segments': len(segments)}, ensure_ascii=False))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest='command', required=True)
    commands.add_parser('doctor', help='Print executable availability; no credentials read')
    preview = commands.add_parser('preview', help='Bind a 3-scene gear demo timeline into the supplied HTML template')
    preview.add_argument('timeline', type=Path)
    preview.add_argument('--out', type=Path, required=True)
    prep = commands.add_parser('prepare', help='Build measured timeline, SRT and optionally WAV')
    prep.add_argument('lesson', type=Path)
    prep.add_argument('--out', type=Path, required=True)
    prep.add_argument('--draft', action='store_true')
    args = p.parse_args()
    try:
        if args.command == 'doctor':
            print(json.dumps({name: shutil.which(name) for name in ['node', 'ffmpeg', 'ffprobe', 'ego-browser']}, ensure_ascii=False, indent=2))
        elif args.command == 'preview':
            data = json.loads(args.timeline.read_text())
            number(data.get('duration'), 'duration', .01)
            segments = data.get('segments', [])
            if not segments or any(s.get('scene') not in [0, 1, 2] for s in segments):
                raise ValueError('Gear demo requires scene 0, 1 or 2 on each segment; other topics need their own renderer')
            cursor = 0
            for s in segments:
                start = number(s.get('start'), 'start')
                end = number(s.get('end'), 'end')
                if abs(start - cursor) > .0001 or end <= start or not isinstance(s.get('narration'), str):
                    raise ValueError('Timeline segments must be contiguous, increasing and have narration')
                cursor = end
            if abs(cursor - data['duration']) > .0001:
                raise ValueError('Timeline duration must match final end')
            if args.out.exists():
                raise ValueError('Refusing to overwrite preview')
            template = (Path(__file__).resolve().parent.parent / 'assets/style-preview.html').read_text()
            payload = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c')
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(template.replace('/*TIMELINE*/ null', payload))
            print(json.dumps({'preview': str(args.out.resolve()), 'duration': data['duration']}, ensure_ascii=False))
        else:
            prepare(args)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        p.exit(1, f'Error: {exc}\n')


if __name__ == '__main__':
    main()
