// Run: gjs tests/map_smoke.js
// One provider entry now controls its entire network subgroup (routes, snaps, nodes).
const Gio = imports.gi.Gio;
const ByteArray = imports.byteArray;
const [, bytes] = Gio.File.new_for_path('cspmap/web/provider_filter.js').load_contents(null);
const source = ByteArray.toString(bytes);

function run(name, assertions, owners = ['alpha', 'beta', '']) {
    const visible = new Set();
    const network = {
        addLayer(layer) { visible.add(layer); },
        removeLayer(layer) { visible.delete(layer); },
    };
    const entries = owners.map((owner, index) => ({
        owner: index, parent: network, layer: 'whole-network-' + index, pointCount: 1,
    }));
    let closed = 0;
    function assert(condition, message) { if (!condition) throw Error(name + ': ' + message); }
    eval(source + '\nconst selection = new ProviderSelection(owners, entries, () => closed++);\n' + assertions);
    print('PASS ' + name);
}

run('Search filters connected routes and splitter nodes as one provider subgroup', `
    const result = selection.apply('beta', '');
    assert(visible.size === 1 && visible.has('whole-network-1'), 'Selected network');
    assert(result.records === 1 && result.providers === 1, 'Selected counts');
`);
run('Blank ownership remains selectable', `
    const result = selection.apply('', '2');
    assert(visible.has('whole-network-2') && visible.size === 1, 'Missing CSP network');
    assert(result.records === 1 && result.providers === 0, 'Missing CSP count');
`);
run('Changing selection closes old map popups', `
    selection.apply('', '0'); selection.apply('', '1');
    assert(closed === 2, 'Close old popup on both changes');
    assert(!visible.has('whole-network-0') && visible.has('whole-network-1'), 'Hide old group');
`);
run('Search and dropdown intersect correctly', `
    const result = selection.apply('beta', '0');
    assert(result.records === 0 && visible.size === 0, 'Conflicting criteria select none');
`);
run('Clearing a filter restores groups without duplication', `
    selection.apply('beta', ''); selection.apply('', ''); selection.apply('', '');
    assert(visible.size === 3, 'Restore all three provider networks');
`);
run('Empty source has zero counts', `
    const result = selection.apply('', '');
    assert(result.records === 0 && result.providers === 0, 'Empty source');
`, []);
