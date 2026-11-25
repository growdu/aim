#!/usr/bin/env bash
# 从静态底板渲染 8 秒 Ken Burns 片段；若 audio/ 下存在成品音轨则一并封装
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
AIM_ROOT="$(cd "$HERE/../.." && pwd)"

# 底板名 / 成片名带角色 slug（仓库既有约定）。
# slug 取模型里的 `person`：产出的文件名跟配 slug 之前一模一样，
# 素材不用改名、脚本不用重跑。
SLUG="$(PYTHONPATH="$AIM_ROOT" python3 -c \
  'from aimkit.model import load; print(load().person)')"
BRAND="$AIM_ROOT/models/$SLUG/assets/brand"
mkdir -p "$BRAND/video"

render() {
  local input="$1" output="$2" audio="$3"
  local tmp="$output.tmp.mp4"
  ffmpeg -y -loop 1 -i "$input" -t 8 \
    -vf "scale=2200:1238:force_original_aspect_ratio=increase,crop=2200:1238,zoompan=z='min(zoom+0.00025,1.06)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1920x1080:fps=30,fade=t=in:st=0:d=0.7,fade=t=out:st=7.3:d=0.7,format=yuv420p" \
    -an -c:v libx264 -preset medium -crf 19 -movflags +faststart "$tmp"
  if [ -f "$audio" ]; then
    ffmpeg -y -i "$tmp" -i "$audio" -map 0:v:0 -map 1:a:0 \
      -c:v copy -c:a aac -b:a 192k -ar 48000 -ac 2 -shortest -movflags +faststart "$output"
    rm -f "$tmp"
  else
    mv "$tmp" "$output"
  fi
}

render "$BRAND/assets/plates/${SLUG}_intro_1080p.png" "$BRAND/video/${SLUG}_intro_8s_1080p.mp4" "$BRAND/audio/intro_mix.wav"
render "$BRAND/assets/plates/${SLUG}_outro_1080p.png" "$BRAND/video/${SLUG}_outro_8s_1080p.mp4" "$BRAND/audio/outro_mix.wav"
echo "Rendered ${SLUG} intro/outro."
