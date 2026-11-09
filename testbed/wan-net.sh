#!/usr/bin/env bash
# WAN emulation for the live pipelining testbed, on the lab machine.
#
# Builds an isolated network of n namespaces (st-n1 .. st-nN, address 10.77.0.i/24 on eth0),
# joined by a bridge that lives in its own namespace (st-hub). Nothing is created or changed in
# the host's network namespace. Each node delays its outgoing packets per destination with netem
# (half the round trip each way), from an RTT matrix (testbed/rtt-7.tsv).
#
# WAN_JITTER_PCT (jitter as % of each one-way delay), WAN_LOSS_PCT (packet loss %) and WAN_RATE
# (bandwidth per link, e.g. 100mbit; default 10gbit) make the links less ideal.
# WAN_WATCHERS lists, for each extra non-validating node, the validator it sits next to (2 ms):
# with "1 2 3 4" and n = 7, nodes 8..11 are watchers next to validators 1..4.
# Needs sudo for ip and tc only.
# Usage: wan-net.sh up [rtt.tsv] [n] [scale]   scale multiplies every delay (0 = no delay)
#        wan-net.sh delay [rtt.tsv] [n] [scale] change the delays of a running network
#        wan-net.sh down
#        wan-net.sh show
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
RTT="${2:-$HERE/rtt-7.tsv}"
N="${3:-7}"
SCALE="${4:-1}"
IP="sudo -n /usr/sbin/ip"
TC="sudo -n /usr/sbin/tc"

TWINS=(${WAN_WATCHERS:-})
TOTAL=$((N + ${#TWINS[@]}))
place() { # the validator whose place node i takes (itself, or a watcher's twin)
    if [ "$1" -gt "$N" ]; then echo "${TWINS[$(($1 - N - 1))]}"; else echo "$1"; fi
}

rtt() { # rtt <i> <j>: RTT in ms between nodes i and j
    local a b
    a=$(place "$1"); b=$(place "$2")
    if [ "$a" = "$b" ]; then echo 2; return; fi
    awk -F'\t' -v i="$a" -v j="$b" '!/^#/ && $1 == i { print $(2 + j) }' "$RTT"
}

set_delays() {
    for i in $(seq 1 "$TOTAL"); do
        ns="st-n$i"
        $TC -n "$ns" qdisc del dev eth0 root 2>/dev/null || true
        $TC -n "$ns" qdisc add dev eth0 root handle 1: htb default 99 r2q 10000
        $TC -n "$ns" class add dev eth0 parent 1: classid 1:99 htb rate 10gbit
        for j in $(seq 1 "$TOTAL"); do
            [ "$i" = "$j" ] && continue
            oneway=$(awk -v r="$(rtt "$i" "$j")" -v s="$SCALE" 'BEGIN { printf "%.1f", r * s / 2 }')
            jitter=$(awk -v o="$oneway" -v p="${WAN_JITTER_PCT:-0}" 'BEGIN { printf "%.1f", o * p / 100 }')
            $TC -n "$ns" class add dev eth0 parent 1: classid "1:$j" htb rate "${WAN_RATE:-10gbit}"
            $TC -n "$ns" qdisc add dev eth0 parent "1:$j" handle "$((10 + j)):" \
                netem delay "${oneway}ms" "${jitter}ms" loss "${WAN_LOSS_PCT:-0}%" limit 100000
            $TC -n "$ns" filter add dev eth0 parent 1: protocol ip prio 1 u32 \
                match ip dst "10.77.0.$j/32" flowid "1:$j"
        done
    done
}

case "${1:-}" in
up)
    $IP netns add st-hub
    $IP -n st-hub link set lo up
    $IP -n st-hub link add br0 type bridge
    $IP -n st-hub link set br0 up
    for i in $(seq 1 "$TOTAL"); do
        ns="st-n$i"
        $IP netns add "$ns"
        $IP -n "$ns" link set lo up
        $IP -n "$ns" link add eth0 type veth peer name "p$i" netns st-hub
        $IP -n st-hub link set "p$i" master br0
        $IP -n st-hub link set "p$i" up
        $IP -n "$ns" addr add "10.77.0.$i/24" dev eth0
        $IP -n "$ns" link set eth0 up
    done
    set_delays
    ;;
delay)
    set_delays
    ;;
down)
    for ns in $($IP netns list | awk '/^st-/ { print $1 }'); do
        $IP netns del "$ns"
    done
    ;;
show)
    $IP netns list
    for ns in $($IP netns list | awk '/^st-n/ { print $1 }' | sort -V); do
        echo "== $ns"
        $TC -n "$ns" qdisc show dev eth0 | grep netem || true
    done
    ;;
*)
    sed -n 2,14p "$0"
    exit 1
    ;;
esac
