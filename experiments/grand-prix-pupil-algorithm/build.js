'use strict';
// Grand Prix U sans murs — ALGORITHME EXPÉRIMENTAL, NON QUALIFIÉ.
// Pure Blockly JSON built from ordinary student-editable blocks.
// Restores pupil-visible per-side H memory after a differential repeated-echo refutation.
// Count only after rear evidence; keep ambiguous sensor measurements in fault state.
// No seed, world plan, oracle, GPS, hidden telemetry or mission-specific block.
function build() {
  let next = 0;
  const names = ['côté', 'portes', 'distance', 'état',
                 'avant', 'bas', 'gauche', 'droite', 'arrière', 'H passé'];
  const vid = name => 'gp-pupil-v2-' + names.indexOf(name);
  const B = (type, fields = {}, inputs = {}, extraState) => {
    const b = {type, id: 'gp-pupil-v2-b-' + (++next)};
    if (Object.keys(fields).length) b.fields = fields;
    if (extraState) b.extraState = extraState;
    const connections = Object.entries(inputs).filter(([, v]) => v);
    if (connections.length)
      b.inputs = Object.fromEntries(connections.map(([k, v]) => [k, {block: v}]));
    return b;
  };
  const S = items => {
    const a = items.filter(Boolean);
    a.forEach((b, i) => {if (i < a.length - 1) b.next = {block: a[i + 1]};});
    return a[0];
  };
  const N = n => B('math_number', {NUM: n});
  const V = name => B('variables_get', {VAR: {id: vid(name)}});
  const R = direction => B('webeeblocks_v2_range', {DIRECTION: direction});
  const A = (op, a, b) => B('math_arithmetic', {OP: op}, {A: a, B: typeof b === 'number' ? N(b) : b});
  const C = (op, a, b) => B('logic_compare', {OP: op}, {A: a, B: typeof b === 'number' ? N(b) : b});
  const And = (a, b) => B('logic_operation', {OP: 'AND'}, {A: a, B: b});
  const Or = (a, b) => B('logic_operation', {OP: 'OR'}, {A: a, B: b});
  const G = (op, name, value) => C(op, V(name), value);
  const Between = (get, lo, hi) => And(C('GTE', get(), lo), C('LTE', get(), hi));
  const Set = (name, x) => B('variables_set', {VAR: {id: vid(name)}},
                              {VALUE: typeof x === 'number' ? N(x) : x});
  const Add = (name, delta) => B('math_change', {VAR: {id: vid(name)}}, {DELTA: N(delta)});
  const M = (distance, direction = 'forward') =>
    B('webeeblocks_v2_move', {DIRECTION: direction, DISTANCE: distance});
  const Adv = distance => [M(distance), Add('distance', Math.round(distance * 10))];
  const Z = direction => B('webeeblocks_v2_vertical', {DIRECTION: direction, DISTANCE: 0.4});
  const If = (cond, yes, no = []) => B('controls_if', {},
                 {IF0: cond, DO0: S(yes), ELSE: S(no)}, no.length ? {hasElse: true} : undefined);
  const Until = (cond, body, limit = 25) =>
    B('controls_whileUntil', {MODE: 'UNTIL', MAX_ITERATIONS: limit},
      {BOOL: cond, DO: S(body)});
  const Fault = () => [Set('état', 2)];

  // At low altitude, both lateral RANGE readings are local H-post echoes,
  // not global wall-position measurements. The check may still be falsified.
  const Center = [If(C('LT', V('gauche'), A('MINUS', V('droite'), 0.06)),
                 [M(0.1, 'right')],
                 [If(C('LT', V('droite'), A('MINUS', V('gauche'), 0.06)),
                   [M(0.1, 'left')])])];
  const Passage = [M(0.2), Set('gauche', R('left')), Set('droite', R('right')),
    If(And(And(C('GT', A('ADD', V('gauche'), V('droite')), 0.45),
               C('LT', A('ADD', V('gauche'), V('droite')), 0.75)),
           G('GT', 'bas', 0.6)),
       [...Center, M(0.4), M(0.2), Add('distance', 8), Z('up'), Set('arrière', R('back')),
        If(Between(() => V('arrière'), 0.30, 0.65),
           [Add('portes', 1), Set('H passé', 1)], Fault())], Fault())];
  const ChosenPose = [
    If(G('EQ', 'portes', 2), [M(0.4, 'left'), M(0.1, 'left')]),
    If(G('EQ', 'portes', 3), [M(0.4, 'right'), M(0.1, 'right')]),
    Set('état', 1)];
  // The interpreter already rejects exhausted bounded loops before exiting.
  // After a confirmed approach, reject an impossible pupil-observed H count.
  const Closed = [Set('avant', R('front')),
    Until(Between(() => V('avant'), 0.63, 0.73),
          [If(G('GT', 'avant', 0.73), [M(0.1)], [M(0.1, 'back')]),
           Set('avant', R('front'))], 6),
    If(Between(() => V('portes'), 1, 3), ChosenPose, Fault())];
  const Observe = [Z('down'), Set('bas', R('front')),
    If(And(G('EQ', 'H passé', 0), C('GT', V('bas'), A('ADD', V('avant'), 0.3))), Passage,
       [If(And(G('EQ', 'côté', 3),
             Between(() => V('bas'), A('MINUS', V('avant'), 0.08),
                                     A('ADD', V('avant'), 0.08))),
          Closed, Fault())])];
  const NearOpen = And(G('GTE', 'avant', 0.30), G('EQ', 'H passé', 0));
  const NearFinal = G('EQ', 'côté', 3);
  const Stride = [If(And(G('LT', 'côté', 3), G('GTE', 'distance', 17)),
                     Adv(0.1),
                     [If(G('GT', 'avant', 0.75), Adv(0.4), Adv(0.1))])];
  const Step = [Set('avant', R('front')),
    If(And(G('LT', 'côté', 3), G('GTE', 'distance', 21)), [Set('état', 1)], [
      If(And(G('EQ', 'côté', 3), G('GTE', 'distance', 24)), Fault(), [
        If(And(G('LTE', 'avant', 0.4), Or(NearOpen, NearFinal)), [B('procedures_callnoreturn', {}, {}, {name: 'observer et décider'})], Stride)
      ])
    ])];
  const OneSide = [Set('distance', 0), Set('H passé', 0), Set('état', 0),
    Until(C('NEQ', V('état'), 0), Step),
    If(And(G('LT', 'côté', 3), G('EQ', 'état', 1)),
       [B('webeeblocks_v2_turn', {DIRECTION: 'left', ANGLE: 90})]),
    Add('côté', 1)];
  const main = [B('webeeblocks_v2_takeoff', {HEIGHT: 0.4}), Z('up'),
    Set('côté', 1), Set('portes', 0), Set('état', 0),
    B('controls_repeat_ext', {}, {TIMES: N(3),
       DO: S([If(C('NEQ', V('état'), 2), OneSide)])}),
    B('webeeblocks_v2_land')];
  const flow = S(main); flow.x = 10; flow.y = 10;
  const definition = B('procedures_defnoreturn', {NAME: 'observer et décider'}, {STACK: S(Observe)});
  definition.x = 550; definition.y = 80;
  return {format: 'webeeblocks-project', version: 1,
    activity: {id: 'progression-grand-prix-u-v1', semantics: 'webeeblocks-ast-v1'},
    workspace: {blocks: {languageVersion: 0, blocks: [flow, definition]},
                variables: names.map((name, i) => ({name, id: vid(name)}))}};
}

// Pupil-visible staging with the per-side H memory restored.
// The two ordinary Blockly procedures make passage and final landing navigable.
// Neither procedure inspects hidden state or introduces an interpreter primitive.
function buildModular() {
  const project = build(), roots = project.workspace.blocks.blocks;
  const observer = roots[1].inputs.STACK.block.next.block.next.block;
  const finalCase = observer.inputs.ELSE.block;
  const opened = observer.inputs.DO0.block;
  const closed = finalCase.inputs.DO0.block;
  const call = (name, id) => ({
    type: 'procedures_callnoreturn', id: 'gp-pupil-v2-b-' + id, extraState: {name}
  });
  const definition = (name, id, body, x, y) => ({
    type: 'procedures_defnoreturn', id: 'gp-pupil-v2-b-' + id,
    fields: {NAME: name}, inputs: {STACK: {block: body}}, x, y
  });
  observer.inputs.DO0.block = call('franchir et confirmer le H', 229);
  finalCase.inputs.DO0.block = call('approcher le H fermé et poser', 230);
  roots.push(definition('franchir et confirmer le H', 231, opened, 1110, 80));
  roots.push(definition('approcher le H fermé et poser', 232, closed, 1110, 1110));
  return project;
}


function buildClassroom() {
  const project = buildModular(), roots=project.workspace.blocks.blocks;
  let p=roots[0];
  while(p && p.type!=='controls_repeat_ext')p=p.next?.block;
  if(!p || !p.inputs?.DO?.block)throw Error('side repeat not found');
  const side=p.inputs.DO.block;
  p.inputs.DO.block={type:'procedures_callnoreturn',id:'gp-pupil-v2-b-233',
    extraState:{name:'parcourir un côté'}};
  roots.push({type:'procedures_defnoreturn',id:'gp-pupil-v2-b-234',
    fields:{NAME:'parcourir un côté'},inputs:{STACK:{block:side}},x:970,y:20});
  roots[0].x=20;roots[0].y=20;
  roots[1].x=2620;roots[1].y=20;
  roots[2].x=2620;roots[2].y=740;
  roots[3].x=20;roots[3].y=550;
  return project;
}

module.exports = {build: buildClassroom, originalBuild: build, guardedBuild: buildModular};
if (require.main === module) {
  const fs = require('fs'), path = require('path');
  const file = path.join(__dirname, 'Grand-Prix-sans-murs-algorithme-candidat.wbb');
  fs.writeFileSync(file, JSON.stringify(buildClassroom(), null, 2) + '\n');
  console.log('WROTE ' + file);
}
