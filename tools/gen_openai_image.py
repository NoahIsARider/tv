#!/usr/bin/env python
"""Generate an image through the OpenAI Images API (gpt-image-2).

    python tools/gen_openai_image.py prompt.txt out.png [--size 1024x1024]
                                                    [--ref a.png] [--ref b.png]

Uses OPENAI_API_KEY from the environment or ~/AppData/Local/hermes/.env and
goes through the local proxy, because api.openai.com is only reachable there.
With one or more --ref it posts to /v1/images/edits, otherwise to
/v1/images/generations.
"""
import base64
import json
import os
import subprocess
import sys

PROXY = "http://127.0.0.1:7890"
ENV = os.path.expanduser("~/AppData/Local/hermes/.env")
MODEL = os.environ.get("IMG_MODEL", "gpt-image-2")


def key():
    if os.environ.get("OPENAI_API_KEY"):
        return os.environ["OPENAI_API_KEY"]
    for line in open(ENV, encoding="utf-8", errors="ignore"):
        if line.startswith("OPENAI_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit("no OPENAI_API_KEY")


def main():
    args = sys.argv[1:]
    prompt_file, out = args[0], args[1]
    size, refs, quality = "1024x1024", [], "high"
    it = iter(args[2:])
    for flag in it:
        if flag == "--size":
            size = next(it)
        elif flag == "--quality":
            quality = next(it)
        elif flag == "--ref":
            refs.append(next(it))
    prompt = open(prompt_file, encoding="utf-8").read().strip()

    if refs:
        cmd = ["curl", "-sS", "-x", PROXY, "--max-time", "600",
               "-H", "Authorization: Bearer " + key(),
               "-F", "model=" + MODEL,
               "-F", "prompt=" + prompt,
               "-F", "size=" + size,
               "-F", "quality=" + quality]
        for r in refs:
            cmd += ["-F", "image[]=@" + os.path.abspath(r)]
        cmd.append("https://api.openai.com/v1/images/edits")
    else:
        body = {"model": MODEL, "prompt": prompt, "size": size,
                "quality": quality, "n": 1}
        cmd = ["curl", "-sS", "-x", PROXY, "--max-time", "600",
               "-H", "Authorization: Bearer " + key(),
               "-H", "Content-Type: application/json",
               "-d", json.dumps(body),
               "https://api.openai.com/v1/images/generations"]

    raw = subprocess.run(cmd, capture_output=True).stdout
    try:
        data = json.loads(raw)
    except Exception:
        print("BAD RESPONSE", raw[:400])
        sys.exit(1)
    if "error" in data:
        print("API ERROR", json.dumps(data["error"])[:400])
        sys.exit(1)
    item = data["data"][0]
    if item.get("b64_json"):
        blob = base64.b64decode(item["b64_json"])
    elif item.get("url"):
        blob = subprocess.run(["curl", "-sS", "-x", PROXY, "--max-time", "300",
                               item["url"]], capture_output=True).stdout
    else:
        print("NO IMAGE", str(data)[:300])
        sys.exit(1)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, "wb").write(blob)
    from PIL import Image
    print("SAVED", out, len(blob), Image.open(out).size)


if __name__ == "__main__":
    main()
