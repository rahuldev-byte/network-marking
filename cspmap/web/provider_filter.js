"use strict";

// Domain filtering only. Folium/Leaflet owns map rendering and interactions.
class ProviderSelection {
    constructor(owners, entries, closePopup) {
        this.owners = owners;
        this.entries = entries;
        this.closePopup = closePopup;
    }

    apply(query, choice) {
        const text = query.trim().toLowerCase();
        const active = this.owners.map((owner, index) => (
            (choice === "" || Number(choice) === index) &&
            (owner || "Missing CSP ID").toLowerCase().includes(text)
        ));
        let records = 0;
        this.closePopup();
        for (const entry of this.entries) {
            if (active[entry.owner]) {
                entry.parent.addLayer(entry.layer);
                records += entry.pointCount;
            } else {
                entry.parent.removeLayer(entry.layer);
            }
        }
        return {
            records,
            providers: this.owners.filter((owner, index) => owner && active[index]).length,
        };
    }
}
