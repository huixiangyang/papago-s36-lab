#!/dev/s36-archive/busybox sh
# 固定的只读录像清单，不执行 URL 参数，不读取录像目录以外的文件。
set -eu
B=/dev/s36-archive/busybox
fail() {
    printf 'Status: 503 Service Unavailable\r\nContent-Type: text/plain\r\nContent-Length: 17\r\n\r\nCard unavailable\n'
    exit 0
}
[ "${REQUEST_METHOD:-}" = GET ] || {
    printf 'Status: 405 Method Not Allowed\r\nAllow: GET\r\nContent-Length: 0\r\n\r\n'
    exit 0
}
$B awk '$2 == "/app/sd" && $3 == "vfat" {found=1} END {exit !found}' /proc/mounts || fail
[ -d /app/sd/PAPAGO/VIDEO ] && [ -r /app/sd/PAPAGO/VIDEO ] || fail
set -- /app/sd/PAPAGO/VIDEO
[ ! -d /app/sd/PAPAGO/EMERGENCY ] || set -- "$@" /app/sd/PAPAGO/EMERGENCY
rows=$($B find "$@" -maxdepth 1 -type f -name '*.MP4' -exec "$B" stat -c '%s %n' {} +) || fail
body=$(printf '%s\n' "$rows" | $B awk '
BEGIN { printf "{\"version\":1,\"files\":["; comma="" }
NF == 2 && $1 ~ /^[0-9]+$/ && $2 ~ /^\/app\/sd\/PAPAGO\/(VIDEO|EMERGENCY)\/[0-9_]+\.MP4$/ {
    split($2, part, "/");
    printf "%s{\"folder\":\"%s\",\"name\":\"%s\",\"size_bytes\":%s}", comma, part[5], part[6], $1;
    comma=",";
}
END { printf "]}" }
') || fail
printf 'Content-Type: application/json\r\nCache-Control: no-store\r\nContent-Length: %s\r\n\r\n%s' "${#body}" "$body"
