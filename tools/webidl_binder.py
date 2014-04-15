
import os, sys

import shared

sys.path.append(shared.path_from_root('third_party'))
sys.path.append(shared.path_from_root('third_party', 'ply'))

import WebIDL

input_file = sys.argv[1]
output_base = sys.argv[2]

p = WebIDL.Parser()
p.parse(open(input_file).read())
data = p.finish()

interfaces = {}
implements = {}

for thing in data:
  if isinstance(thing, WebIDL.IDLInterface):
    interfaces[thing.identifier.name] = thing
  elif isinstance(thing, WebIDL.IDLImplementsStatement):
    implements.setdefault(thing.implementor.identifier.name, []).append(thing.implementee.identifier.name)

print interfaces
print implements

gen_c = open(output_base + '.cpp', 'w')
gen_js = open(output_base + '.js', 'w')

gen_c.write('extern "C" {\n')

gen_js.write('''
// Bindings utilities

var Object__cache = {}; // we do it this way so we do not modify |Object|
function wrapPointer(ptr, __class__) {
  var cache = Object__cache;
  var ret = cache[ptr];
  if (ret) return ret;
  __class__ = __class__ || Object;
  ret = Object.create(__class__.prototype);
  ret.ptr = ptr;
  ret.__class__ = __class__;
  return cache[ptr] = ret;
}
Module['wrapPointer'] = wrapPointer;

function castObject(obj, __class__) {
  return wrapPointer(obj.ptr, __class__);
}
Module['castObject'] = castObject;

Module['NULL'] = wrapPointer(0);

function destroy(obj) {
  if (!obj['__destroy__']) throw 'Error: Cannot destroy object. (Did you create it yourself?)';
  obj['__destroy__']();
  // Remove from cache, so the object can be GC'd and refs added onto it released
  delete Object__cache[obj.ptr];
}
Module['destroy'] = destroy;

function compare(obj1, obj2) {
  return obj1.ptr === obj2.ptr;
}
Module['compare'] = compare;

function getPointer(obj) {
  return obj.ptr;
}
Module['getPointer'] = getPointer;

function getClass(obj) {
  return obj.__class__;
}
Module['getClass'] = getClass;

// Converts a value into a C-style string.
function ensureString(value) {
  if (typeof value == 'number') return value;
  return allocate(intArrayFromString(value), 'i8', ALLOC_STACK);
}

''')

def render_function(self_name, bindings_name, min_args, max_args, call_prefix):
  print >> sys.stderr, 'renderfunc', name, min_args, max_args
  args = ['arg%d' % i for i in range(max_args)]
  body = ''
  for i in range(min_args, max_args):
    body += '  if (arg%d === undefined) { %s_emscripten_bind_%s_%d(%s)%s }\n' % (i, call_prefix, bindings_name, i, ','.join(args[:i]), '' if 'return ' in call_prefix else '; return')
  body += '  %s_emscripten_bind_%s_%d(%s);\n' % (call_prefix, bindings_name, max_args, ','.join(args))
  return r'''function%s(%s) {
%s
}''' % ((' ' + self_name) if self_name is not None else '', ','.join(args), body[:-1])

for name, interface in interfaces.iteritems():
  gen_js.write('\n// ' + name + '\n')
  # Constructor
  min_args = 0
  max_args = 0
  cons = interface.getExtendedAttribute('Constructor')
  if type(cons) == list:
    args_list = cons[0]
    max_args = len(args_list)
    for i in range(len(args_list)):
      arg = args_list[i]
      if arg.optional:
        break
      min_args = i+1
  parent = '{}'
  if name in implements:
    assert len(implements[name]) == 1, 'cannot handle multiple inheritance yet'
    parent = 'Object.create(%s)' % implements[name][0]
  gen_js.write(r'''
%s
%s.prototype = %s;
''' % (render_function(name, name, min_args, max_args, 'this.ptr = '), name, parent))
  # Methods
  for m in interface.members:
    #print dir(m)
    gen_js.write(r'''
%s.%s = %s;
''' % (name, m.identifier.name, render_function(None, m.identifier.name, min(m.allowedArgCounts), max(m.allowedArgCounts), '' if m.signatures()[0][0].name == 'Void' else 'return ')))

gen_js.write('\n');

gen_c.close()
gen_js.close()
