/**
 * VerifyLoop - Typed guard surfaces for AI coding agents
 *
 * Generate type-safe verification loops that make security invariants
 * physically unbreakable at compile time.
 */

export { parseSpec, SpecParseError } from './spec/parser.js';
export type {
  VerifyLoopSpec,
  Invariant,
  ChainStep,
  Settings,
  BrandStyle,
  ErrorBudgetStrategy,
} from './spec/types.js';

export { generateGuards, type GeneratorOptions } from './generator/index.js';

export {
  verify,
  type VerificationGateOptions,
  type VerificationError,
  type VerificationResult,
} from './gate/index.js';

export {
  runVerificationLoop,
  type LoopOptions,
  type LoopResult,
  type LoopStatus,
  type RetryAttempt,
} from './loop/index.js';
