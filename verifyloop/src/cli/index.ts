#!/usr/bin/env node

import { Command } from 'commander';
import { existsSync, watchFile, unwatchFile } from 'fs';
import { resolve } from 'path';
import { parseSpec } from '../spec/parser.js';
import { generateGuards } from '../generator/index.js';
import { verify } from '../gate/index.js';
import { runVerificationLoop } from '../loop/index.js';
import type { RetryAttempt } from '../loop/types.js';

const program = new Command();

program
  .name('verifyloop')
  .description('Generate typed guard surfaces and run deterministic verification loops')
  .version('1.0.0');

// Generate command
program
  .command('generate')
  .description('Generate guard files from spec')
  .option('-s, --spec <path>', 'Path to spec file', 'verifyloop.spec.yaml')
  .option('-o, --output <path>', 'Output directory for guards', './guards')
  .action(async (options) => {
    try {
      const specPath = resolve(options.spec);
      const outputDir = resolve(options.output);

      if (!existsSync(specPath)) {
        console.error(`Error: Spec file not found at ${specPath}`);
        process.exit(1);
      }

      console.log(`Reading spec from ${specPath}...`);
      const spec = parseSpec(specPath);

      console.log(`Generating guards to ${outputDir}...`);
      generateGuards(spec.invariants, { outputDir });

      console.log(`✓ Generated ${spec.invariants.length} guard(s) successfully`);
      for (const invariant of spec.invariants) {
        console.log(`  - ${invariant.name}`);
      }
    } catch (error) {
      console.error('Error:', error instanceof Error ? error.message : error);
      process.exit(1);
    }
  });

// Check command
program
  .command('check <path>')
  .description('Run verification on target path')
  .option('-s, --spec <path>', 'Path to spec file', 'verifyloop.spec.yaml')
  .option('-t, --tsconfig <path>', 'Path to tsconfig.json')
  .action(async (targetPath, options) => {
    try {
      const specPath = resolve(options.spec);
      const target = resolve(targetPath);

      if (!existsSync(specPath)) {
        console.error(`Error: Spec file not found at ${specPath}`);
        process.exit(1);
      }

      if (!existsSync(target)) {
        console.error(`Error: Target path not found at ${target}`);
        process.exit(1);
      }

      const spec = parseSpec(specPath);

      console.log(`Verifying ${target}...`);
      const result = verify({
        targetPath: target,
        invariants: spec.invariants,
        tsconfigPath: options.tsconfig,
      });

      if (result.success) {
        console.log('✓ Verification passed');
        if (result.warnings.length > 0) {
          console.log(`\n⚠ ${result.warnings.length} warning(s):`);
          for (const warning of result.warnings) {
            console.log(`  ${warning.file}:${warning.line} - ${warning.violation}`);
          }
        }
      } else {
        console.log(`✗ Verification failed with ${result.errors.length} error(s):\n`);
        for (const error of result.errors) {
          console.log(`${error.file}:${error.line}`);
          console.log(`  Invariant: ${error.invariant || 'N/A'}`);
          console.log(`  Violation: ${error.violation}`);
          if (error.hint) {
            console.log(`  Hint: ${error.hint}`);
          }
          console.log();
        }
        process.exit(1);
      }
    } catch (error) {
      console.error('Error:', error instanceof Error ? error.message : error);
      process.exit(1);
    }
  });

// Loop command
program
  .command('loop')
  .description('Run verification loop with retries')
  .requiredOption('-p, --path <path>', 'Target path to verify')
  .option('-s, --spec <path>', 'Path to spec file', 'verifyloop.spec.yaml')
  .option('-m, --max-retries <number>', 'Maximum number of retries', '5')
  .option('-e, --error-budget <strategy>', 'Error budget strategy (increasing|decreasing|none)', 'none')
  .option('-t, --tsconfig <path>', 'Path to tsconfig.json')
  .option('-w, --watch', 'Watch mode (re-run on file changes)')
  .action(async (options) => {
    try {
      const specPath = resolve(options.spec);
      const targetPath = resolve(options.path);

      if (!existsSync(specPath)) {
        console.error(`Error: Spec file not found at ${specPath}`);
        process.exit(1);
      }

      if (!existsSync(targetPath)) {
        console.error(`Error: Target path not found at ${targetPath}`);
        process.exit(1);
      }

      const spec = parseSpec(specPath);
      const maxRetries = parseInt(options.maxRetries, 10);

      const runLoop = async () => {
        console.log(`\nRunning verification loop on ${targetPath}...`);
        console.log(`Max retries: ${maxRetries}, Error budget: ${options.errorBudget}\n`);

        const result = await runVerificationLoop({
          targetPath,
          invariants: spec.invariants,
          maxRetries,
          errorBudget: options.errorBudget,
          tsconfigPath: options.tsconfig,
          onRetry: (attempt: RetryAttempt) => {
            console.log(`\nAttempt ${attempt.attempt}: ${attempt.errorCount} error(s)`);
            for (const error of attempt.errors) {
              console.log(`  ${error.file}:${error.line} - ${error.violation}`);
            }
          },
        });

        console.log(`\n${'='.repeat(60)}`);
        console.log(`Status: ${result.status}`);
        console.log(`Message: ${result.message}`);
        console.log(`Total attempts: ${result.attempts.length}`);
        console.log(`Final error count: ${result.finalErrorCount}`);
        console.log('='.repeat(60));

        if (result.status !== 'PASS') {
          if (!options.watch) {
            process.exit(1);
          }
        }
      };

      await runLoop();

      if (options.watch) {
        console.log('\nWatching for changes... (Press Ctrl+C to exit)');
        watchFile(targetPath, { interval: 1000 }, async () => {
          console.log('\nFile changed, re-running verification...');
          await runLoop();
        });

        // Keep process alive
        process.on('SIGINT', () => {
          unwatchFile(targetPath);
          console.log('\nStopping watch mode...');
          process.exit(0);
        });
      }
    } catch (error) {
      console.error('Error:', error instanceof Error ? error.message : error);
      process.exit(1);
    }
  });

program.parse();
