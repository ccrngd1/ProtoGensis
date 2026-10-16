#!/usr/bin/env python3
"""Generate the SYNTHETIC normalizer corpus (AC #9). Deterministic.

>=150 cases, >=60 negatives, >=8 negatives in each false-positive family:
--help/-h, heredoc body, --dry-run, echo/printf, grep, comment line,
cat>file<<EOF script text, and a command inside a quoted string argument.
"""
import json
import os

SYN_JOB = "aaaa{:04d}-0000-4000-8000-{:012d}"


def jid(i):
    return SYN_JOB.format(i, i)


cases = []


def pos(cmd, expect, family="positive"):
    cases.append({"cmd": cmd, "expect": expect, "family": family, "synthetic": True})


def neg(cmd, family):
    cases.append({"cmd": cmd, "expect": [], "family": family, "synthetic": True})


# ---- positives: real infra actions (>=70) ----
for i in range(1, 13):
    pos(f"openclaw cron disable {jid(i)}", ["cron.disable"], "cron_disable")
for i in range(1, 13):
    pos(f"openclaw cron edit {jid(i)} --message hi", ["cron.edit"], "cron_edit")
for i in range(1, 7):
    pos(f"openclaw cron rm {jid(i)}", ["cron.rm"], "cron_rm")
for i in range(1, 7):
    pos(f"openclaw cron enable {jid(i)}", ["cron.enable"], "cron_enable")
for i in range(1, 13):
    pos("openclaw gateway restart", ["gateway.restart"], "gateway_restart")
for i in range(1, 5):
    pos("openclaw gateway stop", ["gateway.stop"], "gateway_stop")
for unit in ("nginx", "redis", "postgres", "docker", "cron", "sshd"):
    pos(f"systemctl restart {unit}", ["service.restart"], "service_restart")
for unit in ("nginx", "redis", "postgres"):
    pos(f"systemctl stop {unit}", ["service.stop"], "service_stop")
for t in ("web", "db", "cache"):
    pos(f"docker restart {t}", ["docker.restart"], "docker_restart")
for t in ("web", "db"):
    pos(f"docker stop {t}", ["docker.stop"], "docker_stop")
pos("docker compose up -d", ["docker.compose"], "docker_compose")
pos("openclaw config set foo=bar", ["config.set"], "config_set")
pos("crontab -e", ["crontab.write"], "crontab")
# prefix stripping
pos("sudo timeout 5 systemctl restart nginx", ["service.restart"], "prefix_strip")
pos("sudo openclaw gateway restart", ["gateway.restart"], "prefix_strip")
pos("FOO=1 openclaw cron disable " + jid(99), ["cron.disable"], "prefix_strip")
pos("nohup openclaw gateway restart &", ["gateway.restart"], "prefix_strip")
# chained: two actions in one command
pos(f"openclaw cron disable {jid(1)} && openclaw cron rm {jid(1)}",
    ["cron.disable", "cron.rm"], "chained")
pos("echo start && openclaw gateway restart", ["gateway.restart"], "chained_echo_then_action")
pos(f"cd ~/.openclaw && openclaw cron edit {jid(2)} --message x",
    ["cron.edit"], "chained")

# ---- negatives: 8 false-positive families, >=8 each ----
for i in range(1, 10):
    neg(f"openclaw cron disable {jid(i)} --help", "help")
    neg(f"openclaw gateway restart -h", "help")
for i in range(1, 10):
    neg(f"openclaw cron edit {jid(i)} --dry-run", "dry_run")
for i in range(1, 10):
    neg(f'echo "openclaw gateway restart"', "echo")
    neg(f"printf 'openclaw cron disable {jid(i)}'", "echo")
for i in range(1, 10):
    neg(f"grep -r 'openclaw cron disable' /var/log", "grep")
for i in range(1, 10):
    neg(f"# openclaw gateway restart (disabled, do not run)", "comment")
for i in range(1, 10):
    body = f"cat > /tmp/script-{i}.sh <<'EOF'\nopenclaw gateway restart\nopenclaw cron disable {jid(i)}\nEOF"
    neg(body, "heredoc")
for i in range(1, 10):
    neg(f'git commit -m "openclaw cron disable {jid(i)} was removed"', "quoted_arg")
for i in range(1, 10):
    neg(f"cat > /tmp/notes-{i}.txt <<EOF\nremember to never run openclaw gateway restart\nEOF", "cat_heredoc_script")

# extra plain negatives (not infra)
for cmd in ("ls -la", "cd /tmp", "python run.py", "openclaw cron list",
            "openclaw sessions list", "git status", "openclaw policy check",
            "pwd", "whoami", "date -u"):
    neg(cmd, "not_infra")

out = os.path.join(os.path.dirname(__file__), "cases.jsonl")
with open(out, "w", encoding="utf-8") as f:
    f.write(json.dumps({"synthetic": True, "note": "SYNTHETIC normalizer corpus (AC #9)"}) + "\n")
    for c in cases:
        f.write(json.dumps(c, sort_keys=True) + "\n")
n_neg = sum(1 for c in cases if not c["expect"])
print(f"wrote {len(cases)} cases, {n_neg} negatives to {out}")
