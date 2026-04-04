# Sample Clip Staging

Keep development footage local. This directory is for user-owned or openly licensed verification clips and should stay out of version control unless you later add a small explicitly licensed fixture set.

## Suggested Layout

```text
data/samples/
  known-good.mp4
  known-bad-occlusion.mp4
  known-unsupported.mp4
  manifest.json
  results/
```

## Manifest Template

Create `data/samples/manifest.json` with entries like this:

```json
[
  {
    "id": "known-good",
    "filename": "known-good.mp4",
    "source": "user-owned",
    "notes": "Single climber on a fixed board angle"
  },
  {
    "id": "known-bad-occlusion",
    "filename": "known-bad-occlusion.mp4",
    "source": "user-owned",
    "notes": "Hands disappear behind volumes for long stretches"
  },
  {
    "id": "known-unsupported",
    "filename": "known-unsupported.mp4",
    "source": "open-license",
    "notes": "Multiple people visible in frame"
  }
]
```

You can copy the starting template from `data/samples/manifest.template.json`.

## Licensing Rule

Only use clips that you own or that clearly permit reuse. If the source license is ambiguous, do not use the clip.

