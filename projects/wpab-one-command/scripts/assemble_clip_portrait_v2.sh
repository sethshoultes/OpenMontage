#!/bin/sh
# Piece 3 portrait v2: terminal only. Crops from the 2160x1500 take are stacked at 1:1 scale
# (48 px type), split between words: command after "npx", Ready line after "on ".
# usage: assemble_clip_portrait_v2.sh <wide-take.mp4> <out.mp4> <seconds>
IN=$1; OUT=$2; DUR=${3:-16.5}
BG=0x161616
nice ffmpeg -v error -y -threads 2 -t "$DUR" -i "$IN" -filter_complex "
color=c=$BG:s=1080x1920:r=25:d=$DUR[bg];
[0:v]split=5[a][b][c][d][e];
[a]crop=420:60:40:40[c1];
[b]crop=960:60:480:40[c2];
[c]crop=780:55:40:380[p];
[d]crop=907:60:40:780[r1];
[e]crop=990:60:947:780[r2];
[bg][c1]overlay=60:420[t1];[t1][c2]overlay=60:490[t2];[t2][p]overlay=60:640[t3];
[t3][r1]overlay=60:800[t4];[t4][r2]overlay=60:870,fade=t=in:d=0.4,fade=t=out:st=$(echo "$DUR-0.5"|bc):d=0.5,format=yuv420p[v]
" -map "[v]" -c:v libx264 -crf 16 -preset medium -movflags +faststart "$OUT"
