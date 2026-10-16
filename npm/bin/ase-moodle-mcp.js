#!/usr/bin/env node
'use strict';

// Fara argumente: server MCP. Cu argumente: CLI-ul (ca ase-moodle), vezi mcp_server.main.
require('../lib/run').launch('mcp', process.argv.slice(2));
