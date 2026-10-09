# Third-party notices

## Operator Memory (BSD-3-Clause)

The A2 `doc_catalog` arm's guidance prompt (`prompts/doc_catalog_guidance.md`)
is adapted from **Operator Memory** by Kevin Liao @ Aerovato Research:

- Upstream: https://github.com/aerovato/operator-memory
- Adapted file: `packages/core/src/prompts/preamble.ts` (plus the catalog
  template in `packages/core/src/templates/catalog.ts`)
- Upstream commit pinned at adaptation time (2026-10-09):
  `85fed0adb6cf9bfaefd4d9199c10d11490cf74a5`
- License: BSD-3-Clause (reproduced below, from the upstream `LICENSE` file at
  that commit)

```
BSD 3-Clause License

Copyright (c) 2026, Kevin Liao @ Aerovato Research

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its
   contributors may be used to endorse or promote products derived from
   this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

The adaptation condenses the multi-partition preamble to the single-partition
catalog arm used in this benchmark and carries a header comment naming this
notice in each adapted file under `prompts/`.
