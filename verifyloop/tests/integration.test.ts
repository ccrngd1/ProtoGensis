import { describe, it, expect } from 'vitest';
import { writeFileSync, mkdirSync, rmSync } from 'fs';
import { join } from 'path';
import { parseSpec } from '../src/spec/parser.js';
import { generateGuards } from '../src/generator/index.js';
import { verify } from '../src/gate/index.js';
import { runVerificationLoop } from '../src/loop/index.js';

const TEST_DIR = '/tmp/verifyloop-integration-test';

describe('Integration Tests', () => {
  beforeEach(() => {
    mkdirSync(TEST_DIR, { recursive: true });
  });

  afterEach(() => {
    rmSync(TEST_DIR, { recursive: true, force: true });
  });

  it('should complete full workflow: spec → generate → verify bad code → verify good code', () => {
    // Step 1: Create spec
    const specPath = join(TEST_DIR, 'test.spec.yaml');
    const specContent = `
version: "1.0"
invariants:
  - name: simple-auth
    description: "Simple authentication"
    chain:
      - type: Unauthenticated
        constructor: createUnauthenticated
        description: "Unauthenticated request"
        fields:
          userId: string
      - type: Authenticated
        constructor: authenticate
        requires: Unauthenticated
        description: "Authenticated request"
        fields:
          userId: string
          token: string
    protected_functions:
      - secureQuery
`;
    writeFileSync(specPath, specContent);

    // Step 2: Parse spec
    const spec = parseSpec(specPath);
    expect(spec.invariants).toHaveLength(1);
    expect(spec.invariants[0].name).toBe('simple-auth');

    // Step 3: Generate guards
    const guardsDir = join(TEST_DIR, 'guards');
    generateGuards(spec.invariants, { outputDir: guardsDir });

    // Step 4: Create bad code (should fail)
    const badCodePath = join(TEST_DIR, 'bad.ts');
    writeFileSync(badCodePath, `
      import { secureQuery } from './guards/simple-auth.js';

      // This should fail: passing wrong type (not authenticated)
      secureQuery({ userId: "123", token: "token" });
    `);

    const badResult = verify({
      targetPath: badCodePath,
      invariants: spec.invariants,
    });

    expect(badResult.success).toBe(false);
    expect(badResult.errors.length).toBeGreaterThan(0);

    const guardError = badResult.errors.find(e => e.is_guard_related);
    expect(guardError).toBeDefined();
    expect(guardError?.invariant).toBe('simple-auth');

    // Step 5: Create good code (should pass)
    const goodCodePath = join(TEST_DIR, 'good.ts');
    writeFileSync(goodCodePath, `
      import {
        createUnauthenticated,
        authenticate,
        secureQuery,
        type Unauthenticated,
        type Authenticated,
      } from './guards/simple-auth.js';

      // This should pass: proper chain
      const unauth: Unauthenticated = createUnauthenticated({ userId: "123" });
      const auth: Authenticated = authenticate(unauth, "token");
      secureQuery(auth);
    `);

    const goodResult = verify({
      targetPath: goodCodePath,
      invariants: spec.invariants,
    });

    expect(goodResult.success).toBe(true);
    expect(goodResult.errors).toHaveLength(0);
  });

  it('should handle multi-step chain correctly', () => {
    const specPath = join(TEST_DIR, 'multi.spec.yaml');
    const specContent = `
version: "1.0"
invariants:
  - name: four-step
    description: "Four step chain"
    chain:
      - type: Step1
        constructor: step1
        description: "Step 1"
      - type: Step2
        constructor: step2
        requires: Step1
        description: "Step 2"
      - type: Step3
        constructor: step3
        requires: Step2
        description: "Step 3"
      - type: Step4
        constructor: step4
        requires: Step3
        description: "Step 4"
    protected_functions:
      - finalFunc
`;
    writeFileSync(specPath, specContent);

    const spec = parseSpec(specPath);
    const guardsDir = join(TEST_DIR, 'guards-multi');
    generateGuards(spec.invariants, { outputDir: guardsDir });

    // Code that skips a step (should fail)
    const skipStepPath = join(TEST_DIR, 'skip.ts');
    writeFileSync(skipStepPath, `
      import { step1, step2, step4, finalFunc } from './guards-multi/four-step.js';

      const s1 = step1();
      const s2 = step2(s1);
      // Skip step3!
      const s4 = step4(s2); // This should fail
      finalFunc(s4);
    `);

    const skipResult = verify({
      targetPath: skipStepPath,
      invariants: spec.invariants,
    });

    expect(skipResult.success).toBe(false);

    // Code with complete chain (should pass)
    const completePath = join(TEST_DIR, 'complete.ts');
    writeFileSync(completePath, `
      import { step1, step2, step3, step4, finalFunc } from './guards-multi/four-step.js';

      const s1 = step1();
      const s2 = step2(s1);
      const s3 = step3(s2);
      const s4 = step4(s3);
      finalFunc(s4);
    `);

    const completeResult = verify({
      targetPath: completePath,
      invariants: spec.invariants,
    });

    expect(completeResult.success).toBe(true);
  });

  it('should run full verification loop', async () => {
    const specPath = join(TEST_DIR, 'loop.spec.yaml');
    const specContent = `
version: "1.0"
invariants:
  - name: loop-test
    description: "Loop test"
    chain:
      - type: Safe
        constructor: makeSafe
        description: "Make safe"
    protected_functions:
      - safeFunc
    settings:
      max_retries: 3
      error_budget: none
`;
    writeFileSync(specPath, specContent);

    const spec = parseSpec(specPath);
    const guardsDir = join(TEST_DIR, 'guards-loop');
    generateGuards(spec.invariants, { outputDir: guardsDir });

    // Valid code
    const codePath = join(TEST_DIR, 'loop-code.ts');
    writeFileSync(codePath, `
      import { makeSafe, safeFunc } from './guards-loop/loop-test.js';

      const safe = makeSafe();
      safeFunc(safe);
    `);

    const result = await runVerificationLoop({
      targetPath: codePath,
      invariants: spec.invariants,
      maxRetries: 3,
    });

    expect(result.status).toBe('PASS');
    expect(result.attempts).toHaveLength(1);
  });

  it('should handle multiple invariants', () => {
    const specPath = join(TEST_DIR, 'multi-inv.spec.yaml');
    const specContent = `
version: "1.0"
invariants:
  - name: auth
    description: "Auth"
    chain:
      - type: Authed
        constructor: auth
        description: "Auth"
    protected_functions:
      - authFunc

  - name: validation
    description: "Validation"
    chain:
      - type: Validated
        constructor: validate
        description: "Validate"
    protected_functions:
      - validFunc
`;
    writeFileSync(specPath, specContent);

    const spec = parseSpec(specPath);
    expect(spec.invariants).toHaveLength(2);

    const guardsDir = join(TEST_DIR, 'guards-multi-inv');
    generateGuards(spec.invariants, { outputDir: guardsDir });

    // Code using both guards
    const codePath = join(TEST_DIR, 'multi-inv-code.ts');
    writeFileSync(codePath, `
      import { auth, authFunc } from './guards-multi-inv/auth.js';
      import { validate, validFunc } from './guards-multi-inv/validation.js';

      const authed = auth();
      authFunc(authed);

      const validated = validate();
      validFunc(validated);
    `);

    const result = verify({
      targetPath: codePath,
      invariants: spec.invariants,
    });

    expect(result.success).toBe(true);
  });
});
