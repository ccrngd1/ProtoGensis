#!/usr/bin/env node

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import { existsSync } from 'fs';
import { resolve } from 'path';
import { parseSpec } from '../spec/parser.js';
import { generateGuards } from '../generator/index.js';
import { verify } from '../gate/index.js';
import type { RetryAttempt } from '../loop/types.js';

// Global state for loop status
let currentLoopState: {
  active: boolean;
  retryCount: number;
  errorHistory: RetryAttempt[];
} = {
  active: false,
  retryCount: 0,
  errorHistory: [],
};

const server = new Server(
  {
    name: 'verifyloop-mcp',
    version: '1.0.0',
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// List available tools
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: 'verify_code',
        description: 'Verify code against VerifyLoop spec. Returns PASS or structured errors.',
        inputSchema: {
          type: 'object',
          properties: {
            path: {
              type: 'string',
              description: 'Path to the code file or directory to verify',
            },
            spec: {
              type: 'string',
              description: 'Path to the VerifyLoop spec file (optional, defaults to verifyloop.spec.yaml)',
            },
            tsconfig: {
              type: 'string',
              description: 'Path to tsconfig.json (optional)',
            },
          },
          required: ['path'],
        },
      },
      {
        name: 'generate_guards',
        description: 'Generate or regenerate guard files from spec',
        inputSchema: {
          type: 'object',
          properties: {
            spec: {
              type: 'string',
              description: 'Path to the VerifyLoop spec file (optional, defaults to verifyloop.spec.yaml)',
            },
            output: {
              type: 'string',
              description: 'Output directory for guards (optional, defaults to ./guards)',
            },
          },
        },
      },
      {
        name: 'verify_loop_status',
        description: 'Get current retry count and error history for active verification loop',
        inputSchema: {
          type: 'object',
          properties: {},
        },
      },
    ],
  };
});

// Handle tool calls
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      case 'verify_code': {
        const targetPath = resolve((args as { path: string }).path);
        const specPath = resolve((args as { spec?: string }).spec || 'verifyloop.spec.yaml');
        const tsconfigPath = (args as { tsconfig?: string }).tsconfig
          ? resolve((args as { tsconfig: string }).tsconfig)
          : undefined;

        if (!existsSync(targetPath)) {
          return {
            content: [
              {
                type: 'text',
                text: JSON.stringify({
                  success: false,
                  error: `Target path not found: ${targetPath}`,
                }, null, 2),
              },
            ],
          };
        }

        if (!existsSync(specPath)) {
          return {
            content: [
              {
                type: 'text',
                text: JSON.stringify({
                  success: false,
                  error: `Spec file not found: ${specPath}`,
                }, null, 2),
              },
            ],
          };
        }

        const spec = parseSpec(specPath);
        const result = verify({
          targetPath,
          invariants: spec.invariants,
          tsconfigPath,
        });

        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify({
                success: result.success,
                errors: result.errors,
                warnings: result.warnings,
              }, null, 2),
            },
          ],
        };
      }

      case 'generate_guards': {
        const specPath = resolve((args as { spec?: string })?.spec || 'verifyloop.spec.yaml');
        const outputDir = resolve((args as { output?: string })?.output || './guards');

        if (!existsSync(specPath)) {
          return {
            content: [
              {
                type: 'text',
                text: JSON.stringify({
                  success: false,
                  error: `Spec file not found: ${specPath}`,
                }, null, 2),
              },
            ],
          };
        }

        const spec = parseSpec(specPath);
        generateGuards(spec.invariants, { outputDir });

        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify({
                success: true,
                message: `Generated ${spec.invariants.length} guard(s) to ${outputDir}`,
                invariants: spec.invariants.map(inv => inv.name),
              }, null, 2),
            },
          ],
        };
      }

      case 'verify_loop_status': {
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify({
                active: currentLoopState.active,
                retryCount: currentLoopState.retryCount,
                errorHistory: currentLoopState.errorHistory.map(attempt => ({
                  attempt: attempt.attempt,
                  timestamp: attempt.timestamp,
                  errorCount: attempt.errorCount,
                  errors: attempt.errors.map(e => ({
                    file: e.file,
                    line: e.line,
                    invariant: e.invariant,
                    violation: e.violation,
                  })),
                })),
              }, null, 2),
            },
          ],
        };
      }

      default:
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify({
                success: false,
                error: `Unknown tool: ${name}`,
              }, null, 2),
            },
          ],
        };
    }
  } catch (error) {
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            success: false,
            error: error instanceof Error ? error.message : String(error),
          }, null, 2),
        },
      ],
    };
  }
});

// Start the server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('VerifyLoop MCP server running on stdio');
}

main().catch((error) => {
  console.error('Server error:', error);
  process.exit(1);
});
