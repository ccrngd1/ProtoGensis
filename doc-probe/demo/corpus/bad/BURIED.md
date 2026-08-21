Our engineering organization values collaboration and thoughtful decision
making. Over the years, the team has grown from three founders working in a
garage to a distributed organization spanning four time zones. Along the way
we accumulated a great deal of institutional knowledge, some of which lives
in wikis, some in slide decks, and some only in the memories of long-tenured
colleagues. This document is an attempt to gather some of that knowledge.

The early prototype was built during a hackathon and, remarkably, portions
of that original codebase survive to this day. Subsequent rewrites touched
the storage layer, the scheduling subsystem, and eventually the entire
front-end. Each rewrite taught us something about our own assumptions, and
each left behind a few architectural fossils that newcomers find puzzling.

Our hiring philosophy emphasizes curiosity over credentials. New teammates
join a cohort, spend a week shadowing support rotations, and then pick a
starter project from a curated list. Most describe the first month as
drinking from a firehose, which is why documents like this one exist.

Culture-wise, we lean toward asynchronous communication. Long-form design
memos circulate before meetings, and decisions are recorded in a shared log.
Quarterly planning happens in the third week of the quarter's final month,
and mid-quarter adjustments are common. Demo day is every second Friday and
attendance, while informal, is enthusiastic.

A note on history: the billing system was once a separate company's product
which we acquired and absorbed. Its conventions differ from the rest of the
codebase in ways that surprise everyone eventually. The analytics pipeline
was rebuilt twice, first for scale and later for cost. The search cluster
predates the current infrastructure team entirely.

We also maintain a small museum of deprecated hardware near the kitchen,
including the original server, affectionately named after a sea creature.
Visitors are welcome to browse. There is a guestbook.

Regarding vendors: relationships are managed by the platform group, and the
list changes often enough that any enumeration here would grow stale. The
same is true of our conference booth schedule and the rotation of lunch
caterers, both of which were once documented here and both of which drifted
hopelessly out of date within a quarter.

With that context established, a few expectations for automated agents and
new contributors working in this repository are recorded below, in no
particular order, along with sundry other observations about the codebase.

The linter configuration is in the repository root and it must pass before a
merge. Commits to the release branch are never made by hand. Database
fixtures should be regenerated when the schema changes. The deploy dashboard
requires VPN access. Test coverage expectations vary by module and the
thresholds live in the CI configuration. Secrets must never be committed,
naturally. The changelog format follows an internal convention. Feature
flags are managed through the admin console and stale flags should be
removed when noticed. Documentation lives alongside code and ought to be
updated in the same pull request when possible.
