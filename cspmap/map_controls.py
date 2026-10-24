"""A small domain-specific provider selector on top of Leaflet controls."""

from html import escape
from pathlib import Path

from branca.element import Element, MacroElement, Template


class ProviderControl(MacroElement):
    """Keep provider filtering consistent across points, routes, and match lines."""

    _template = Template("""
    {% macro script(this, kwargs) %}
    (function () {
        const map = {{this._parent.get_name()}};
        const entries = [
            {% for entry in this.entries %}
            {owner: {{entry.owner}}, parent: {{entry.parent}},
             layer: {{entry.layer}}, pointCount: {{entry.point_count}}},
            {% endfor %}
        ];
        const selection = new ProviderSelection(
            {{this.owners | tojson}}, entries, function () { map.closePopup(); }
        );
        const control = L.control({position: 'topleft'});
        control.onAdd = function () {
            const panel = L.DomUtil.create('div', 'leaflet-bar');
            panel.style.cssText = 'background:white;padding:10px;max-width:260px';
            panel.innerHTML = {{this.markup | tojson}};
            L.DomEvent.disableClickPropagation(panel);
            L.DomEvent.disableScrollPropagation(panel);
            const search = panel.querySelector('input');
            const choice = panel.querySelector('select');
            const status = panel.querySelector('[role="status"]');
            function update() {
                const result = selection.apply(search.value, choice.value);
                status.textContent = result.records.toLocaleString() +
                    ' selected splitters · ' + result.providers + ' providers';
            }
            L.DomEvent.on(search, 'input', update);
            L.DomEvent.on(choice, 'change', update);
            update();
            return panel;
        };
        control.addTo(map);
    })();
    {% endmacro %}
    """)

    def __init__(self, owners, entries):
        super().__init__()
        self._name = "ProviderControl"
        self.owners = owners
        self.entries = entries
        options = ['<option value="">All providers</option>']
        options.extend(
            f'<option value="{index}">{escape(owner or "Missing CSP ID")}</option>'
            for index, owner in enumerate(owners)
        )
        self.markup = (
            '<strong>Provider</strong><br>'
            '<select aria-label="Select provider" style="width:100%">'
            + "".join(options)
            + '</select><details style="margin-top:6px">'
            '<summary style="cursor:pointer;font-size:11px">Search provider IDs'
            '</summary><input type="search" aria-label="Search provider" '
            'placeholder="Enter part of an ID" style="width:100%;margin:6px 0">'
            '</details><div role="status" style="margin-top:6px;font-size:11px"></div>'
            '<div style="font-size:11px">Dark outlines = needs review</div>'
        )

    def render(self, **kwargs):
        source = Path(__file__).with_name("web") / "provider_filter.js"
        self.get_root().header.add_child(
            Element(f"<script>\n{source.read_text(encoding='utf-8')}\n</script>"),
            name="provider_filter",
        )
        super().render(**kwargs)
