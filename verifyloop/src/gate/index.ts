import { execSync } from 'child_process';
import { existsSync } from 'fs';
import { join } from 'path';
import type { Invariant } from '../spec/types.js';
import type { VerificationError, VerificationResult } from './types.js';

export interface VerificationGateOptions {
  targetPath: string;
  invariants: Invariant[];
  tsconfigPath?: string;
}

export function verify(options: VerificationGateOptions): VerificationResult {
  const { targetPath, invariants, tsconfigPath } = options;

  // Build tsc command
  const tscArgs = ['--noEmit', '--pretty', 'false'];

  if (tsconfigPath) {
    if (!existsSync(tsconfigPath)) {
      throw new Error(`tsconfig.json not found at ${tsconfigPath}`);
    }
    tscArgs.push('--project', tsconfigPath);
  }

  if (existsSync(targetPath)) {
    // If targetPath is a file or directory
    tscArgs.push(targetPath);
  }

  const command = `tsc ${tscArgs.join(' ')}`;

  let output = '';
  let exitCode = 0;

  try {
    execSync(command, {
      encoding: 'utf-8',
      stdio: 'pipe',
    });
  } catch (error: unknown) {
    if (error && typeof error === 'object' && 'stdout' in error) {
      output = (error as { stdout: string }).stdout;
      exitCode = 1;
    } else {
      throw error;
    }
  }

  if (exitCode === 0) {
    return {
      success: true,
      errors: [],
      warnings: [],
    };
  }

  // Parse tsc output
  const errors = parseTscOutput(output, invariants);

  // Separate guard-related errors from warnings
  const guardErrors = errors.filter(e => e.is_guard_related);
  const warnings = errors.filter(e => !e.is_guard_related);

  return {
    success: guardErrors.length === 0,
    errors: guardErrors,
    warnings,
  };
}

function parseTscOutput(output: string, invariants: Invariant[]): VerificationError[] {
  const errors: VerificationError[] = [];
  const lines = output.split('\n');

  // TypeScript error format: file.ts(line,col): error TS####: message
  const errorPattern = /^(.+?)\((\d+),(\d+)\):\s+error\s+TS\d+:\s+(.+)$/;

  for (const line of lines) {
    const match = line.match(errorPattern);
    if (match) {
      const [, file, lineNum, colNum, message] = match;

      const error: VerificationError = {
        file: file.trim(),
        line: parseInt(lineNum, 10),
        column: parseInt(colNum, 10),
        violation: message.trim(),
        is_guard_related: false,
      };

      // Check if error is related to any guard
      const matchedInvariant = findMatchingInvariant(message, invariants);
      if (matchedInvariant) {
        error.is_guard_related = true;
        error.invariant = matchedInvariant.name;
        error.hint = generateHint(message, matchedInvariant);
        error.guard_definition = generateGuardDefinition(matchedInvariant);
      }

      errors.push(error);
    }
  }

  return errors;
}

function findMatchingInvariant(errorMessage: string, invariants: Invariant[]): Invariant | undefined {
  // Look for type names from invariant chains in the error message
  for (const invariant of invariants) {
    for (const step of invariant.chain) {
      if (errorMessage.includes(step.type)) {
        return invariant;
      }
    }

    // Also check protected function names
    for (const fnName of invariant.protected_functions) {
      if (errorMessage.includes(fnName)) {
        return invariant;
      }
    }
  }

  return undefined;
}

function generateHint(errorMessage: string, invariant: Invariant): string {
  // Generate a hint based on the chain structure
  const constructorChain = invariant.chain.map(step => step.constructor).join('(');
  const closingParens = ')'.repeat(invariant.chain.length - 1);

  // Find what type is expected
  const lastType = invariant.chain[invariant.chain.length - 1].type;

  return `Use ${constructorChain}input${closingParens} to construct ${lastType}`;
}

function generateGuardDefinition(invariant: Invariant): string {
  const lines: string[] = [];

  lines.push(`Guard: ${invariant.name}`);
  lines.push(`Description: ${invariant.description}`);
  lines.push(`Chain:`);

  for (let i = 0; i < invariant.chain.length; i++) {
    const step = invariant.chain[i];
    const arrow = i < invariant.chain.length - 1 ? ' → ' : '';
    lines.push(`  ${step.type}${arrow}`);
  }

  return lines.join('\n');
}

export { VerificationError, VerificationResult } from './types.js';
