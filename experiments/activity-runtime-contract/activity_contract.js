/* Experimental A2 only. Bridges one declarative activity profile to Blockly and AST runtime preflight.
 * No product/runtime code is modified. */
(function(root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.WebeeBlocksActivityRuntimeContract = factory();
})(typeof self !== 'undefined' ? self : this, function() {
  'use strict';
  function fail(msg){throw new Error('activity contract: '+msg);}
  function own(o,k){return Object.prototype.hasOwnProperty.call(o,k);}
  function workspaceTypes(ws){return ws.getAllBlocks(false).map(b=>b.type);}
  function preflightWorkspace(profile,ws){const allowed=new Set(profile.toolbox);const types=workspaceTypes(ws);for(const type of types)if(!allowed.has(type))fail('block forbidden by profile: '+type);return types;}
  function applyFieldBounds(profile,ws){const defs=profile.fieldBounds||{};for(const block of ws.getAllBlocks(false)){for(const key of Object.keys(defs)){const parts=key.split('.');if(parts[0]!==block.type)continue;const field=block.getField(parts[1]);if(!field||typeof field.setConstraints!=='function')fail('field bound target unavailable: '+key);const b=defs[key];field.setConstraints(b.min,b.max,b.step);}}
  }
  function collectAst(ast){const blocks=new Set(),ranges=new Set();function expr(e){if(!e)return;if(e.kind==='range')ranges.add(e.direction);if(e.left)expr(e.left);if(e.right)expr(e.right);}function seq(items){for(const s of items||[]){blocks.add(s.kind);if(s.kind==='if'){expr(s.condition);seq(s.then);seq(s.else);}if(s.kind==='repeat')seq(s.body);}}seq(ast&&ast.program);return{blocks,ranges};}
  function checkBounds(profile,ast){const bounds=profile.astBounds||{};function bounded(name,value){if(!own(bounds,name))return;const b=bounds[name];if(value<b.min||value>b.max)fail(name+' outside profile bounds: '+value);}function seq(items){for(const s of items||[]){if(s.kind==='takeoff')bounded('takeoff.height_m',s.height_m);if(s.kind==='move')bounded('move.distance_m',s.distance_m);if(s.kind==='repeat'){bounded('repeat.count',s.count);seq(s.body);}if(s.kind==='if'){seq(s.then);seq(s.else);}}}seq(ast.program);}
  function preflightAst(profile,ast){const facts=collectAst(ast);const kinds=new Set(profile.runtime.allowedStatementKinds||[]);for(const kind of facts.blocks)if(!kinds.has(kind))fail('AST statement forbidden by profile: '+kind);const dirs=new Set(profile.runtime.rangeDirections||[]);for(const d of facts.ranges)if(!dirs.has(d))fail('range capability unavailable in profile: '+d);checkBounds(profile,ast);return facts;}
  function toolboxXml(profile){return '<xml>'+profile.toolbox.map(type=>'<block type="'+type+'"></block>').join('')+'</xml>';}
  function execute(profile,ws,compiler,interpreter,backend){preflightWorkspace(profile,ws);applyFieldBounds(profile,ws);const ast=compiler.compileWorkspace(ws);preflightAst(profile,ast);interpreter.run(ast,backend);return ast;}
  return{preflightWorkspace,applyFieldBounds,preflightAst,toolboxXml,execute};
});
